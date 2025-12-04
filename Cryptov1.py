"""
Crypto Deposit Telegram Bot using FF.io (FixedFloat) API
=========================================================
Features:
- /depo and /deposit commands to initiate deposits
- Inline button selection for main cryptocurrencies
- Auto-generated deposit addresses
- Automatic deposit tracking
- Success notifications

Author: Claude AI Assistant
"""

import os
import hmac
import json
import hashlib
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

# ============================================================================
# CONFIGURATION - Replace with your actual credentials
# ============================================================================

# Telegram Bot Token (Get from @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536336722:AAFE-buesnalNNyFg371JzhO8qbRWeH5cZw")

# FF.io API Credentials (Get from https://ff.io/user/apikey)
FF_API_KEY = os.getenv("FF_API_KEY", "cA0Nl1Dks2CQMNu29h4PAAnOoAZtS5YF5vOrN6u4")
FF_API_SECRET = os.getenv("FF_API_SECRET", "6CBTRdPuhCHq5ZvDulA7prGqd2V9RScfoAwM51Sr")

# Your receiving wallet address (where deposits will be converted/sent)
# You need to set this for each currency you want to receive
RECEIVING_WALLETS = {
    "USDTBSC": os.getenv("USDT_BEP20_WALLET", "0x8dC68DcdF509a14497358e8C3FDB79ED673Ee248"),
    "USDTTRC": os.getenv("USDT_TRC20_WALLET", ""),
    "USDTERC": os.getenv("USDT_ERC20_WALLET", ""),
    "BTC": os.getenv("BTC_WALLET", ""),
    "ETH": os.getenv("ETH_WALLET", ""),
    "LTC": os.getenv("LTC_WALLET", ""),
    "DOGE": os.getenv("DOGE_WALLET", ""),
    "TRX": os.getenv("TRX_WALLET", ""),
    "BNB": os.getenv("BNB_WALLET", ""),
    "SOL": os.getenv("SOL_WALLET", ""),
    "XRP": os.getenv("XRP_WALLET", ""),
}

# Default receiving currency (what you want to receive after conversion)
DEFAULT_RECEIVE_CURRENCY = "USDTBSC"

# Deposit tracking interval in seconds
TRACKING_INTERVAL = 30

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================================
# MAIN COINS CONFIGURATION
# ============================================================================

MAIN_COINS = [
    {"code": "BTC", "name": "Bitcoin", "emoji": "🟠"},
    {"code": "ETH", "name": "Ethereum", "emoji": "💎"},
    {"code": "USDTTRC", "name": "USDT (TRC20)", "emoji": "💵"},
    {"code": "USDTERC", "name": "USDT (ERC20)", "emoji": "💵"},
    {"code": "LTC", "name": "Litecoin", "emoji": "⚪"},
    {"code": "BNB", "name": "BNB (BSC)", "emoji": "🟡"},
    {"code": "SOL", "name": "Solana", "emoji": "🟣"},
    {"code": "DOGE", "name": "Dogecoin", "emoji": "🐕"},
    {"code": "TRX", "name": "TRON", "emoji": "🔴"},
    {"code": "XRP", "name": "Ripple", "emoji": "⚫"},
    {"code": "MATIC", "name": "Polygon", "emoji": "🟣"},
    {"code": "ADA", "name": "Cardano", "emoji": "🔵"},
]

# ============================================================================
# CONVERSATION STATES
# ============================================================================

SELECTING_COIN, ENTERING_AMOUNT, CONFIRMING_DEPOSIT = range(3)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class DepositOrder:
    """Represents a deposit order"""
    user_id: int
    chat_id: int
    order_id: str
    token: str
    from_currency: str
    to_currency: str
    deposit_address: str
    deposit_tag: Optional[str]
    expected_amount: str
    receive_amount: str
    status: str
    created_at: datetime = field(default_factory=datetime.now)
    
# In-memory storage for active deposits (use database in production)
active_deposits: Dict[str, DepositOrder] = {}
user_deposits: Dict[int, list] = {}

# ============================================================================
# FF.IO API CLASS
# ============================================================================

class FixedFloatAPI:
    """FixedFloat API wrapper for crypto exchange operations"""
    
    BASE_URL = "https://ff.io/api/v2"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign(self, data: str) -> str:
        """Generate HMAC SHA256 signature"""
        return hmac.new(
            key=self.api_secret.encode(),
            msg=data.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
    
    def _request(self, method: str, params: dict = None) -> dict:
        """Make API request to FixedFloat"""
        url = f"{self.BASE_URL}/{method}"
        
        if params is None:
            params = {}
        
        data = json.dumps(params) if params else "{}"
        
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-API-KEY": self.api_key,
            "X-API-SIGN": self._sign(data)
        }
        
        try:
            response = requests.post(url, data=data, headers=headers, timeout=30)
            result = response.json()
            
            if result.get("code") == 0:
                return {"success": True, "data": result.get("data")}
            else:
                return {
                    "success": False,
                    "error": result.get("msg", "Unknown error"),
                    "code": result.get("code")
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_currencies(self) -> dict:
        """Get list of available currencies"""
        return self._request("ccies")
    
    def get_price(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
        direction: str = "from",
        order_type: str = "float"
    ) -> dict:
        """Get exchange rate for a currency pair"""
        params = {
            "fromCcy": from_currency,
            "toCcy": to_currency,
            "amount": amount,
            "direction": direction,
            "type": order_type
        }
        return self._request("price", params)
    
    def create_order(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
        to_address: str,
        tag: str = None,
        direction: str = "from",
        order_type: str = "float"
    ) -> dict:
        """Create a new exchange order"""
        params = {
            "fromCcy": from_currency,
            "toCcy": to_currency,
            "amount": amount,
            "direction": direction,
            "type": order_type,
            "toAddress": to_address
        }
        
        if tag:
            params["tag"] = tag
        
        return self._request("create", params)
    
    def get_order(self, order_id: str, token: str) -> dict:
        """Get order details"""
        params = {
            "id": order_id,
            "token": token
        }
        return self._request("order", params)
    
    def get_qr_codes(self, order_id: str, token: str) -> dict:
        """Get QR codes for deposit address"""
        params = {
            "id": order_id,
            "token": token
        }
        return self._request("qr", params)


# Initialize API client
ff_api = FixedFloatAPI(FF_API_KEY, FF_API_SECRET)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_status_emoji(status: str) -> str:
    """Get emoji for order status"""
    status_emojis = {
        "NEW": "🆕",
        "PENDING": "⏳",
        "EXCHANGE": "🔄",
        "WITHDRAW": "📤",
        "DONE": "✅",
        "EXPIRED": "⏰",
        "EMERGENCY": "⚠️"
    }
    return status_emojis.get(status, "❓")


def format_deposit_message(order: DepositOrder) -> str:
    """Format deposit details message"""
    message = (
        f"📥 **Deposit Details**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 **Coin:** {order.from_currency}\n"
        f"📊 **Amount to send:** `{order.expected_amount}` {order.from_currency}\n"
        f"💵 **You will receive:** `{order.receive_amount}` {order.to_currency}\n\n"
        f"📍 **Deposit Address:**\n"
        f"`{order.deposit_address}`\n"
    )
    
    if order.deposit_tag:
        message += f"\n🏷️ **Memo/Tag:** `{order.deposit_tag}`\n"
    
    message += (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🔖 **Order ID:** `{order.order_id}`\n"
        f"📊 **Status:** {get_status_emoji(order.status)} {order.status}\n\n"
        f"⚠️ **Important:**\n"
        f"• Send **exact amount** shown above\n"
        f"• Deposit is tracked automatically\n"
        f"• You'll be notified when complete\n"
        f"• Order expires in 30 minutes"
    )
    
    return message


def create_coin_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard with main coins"""
    keyboard = []
    row = []
    
    for i, coin in enumerate(MAIN_COINS):
        button = InlineKeyboardButton(
            f"{coin['emoji']} {coin['code']}",
            callback_data=f"coin_{coin['code']}"
        )
        row.append(button)
        
        # 3 buttons per row
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    # Add remaining buttons
    if row:
        keyboard.append(row)
    
    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)


def create_amount_keyboard(coin_code: str) -> InlineKeyboardMarkup:
    """Create keyboard for amount selection"""
    # Get price info for suggested amounts
    amounts = {
        "BTC": ["0.001", "0.005", "0.01", "0.05"],
        "ETH": ["0.01", "0.05", "0.1", "0.5"],
        "USDTTRC": ["10", "50", "100", "500"],
        "USDTERC": ["10", "50", "100", "500"],
        "LTC": ["0.1", "0.5", "1", "5"],
        "BNB": ["0.05", "0.1", "0.5", "1"],
        "SOL": ["0.5", "1", "5", "10"],
        "DOGE": ["100", "500", "1000", "5000"],
        "TRX": ["50", "100", "500", "1000"],
        "XRP": ["10", "50", "100", "500"],
        "MATIC": ["10", "50", "100", "500"],
        "ADA": ["10", "50", "100", "500"],
    }
    
    suggested = amounts.get(coin_code, ["10", "50", "100", "500"])
    
    keyboard = [
        [
            InlineKeyboardButton(f"{amt} {coin_code}", callback_data=f"amount_{amt}")
            for amt in suggested[:2]
        ],
        [
            InlineKeyboardButton(f"{amt} {coin_code}", callback_data=f"amount_{amt}")
            for amt in suggested[2:]
        ],
        [
            InlineKeyboardButton("💲 Custom Amount", callback_data="amount_custom")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="back_to_coins"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# TELEGRAM BOT HANDLERS
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    welcome_message = (
        f"👋 Welcome, {user.first_name}!\n\n"
        f"🏦 **Crypto Deposit Bot**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"I help you deposit cryptocurrency easily.\n\n"
        f"📌 **Commands:**\n"
        f"• /deposit or /depo - Start a new deposit\n"
        f"• /status - Check your active deposits\n"
        f"• /history - View deposit history\n"
        f"• /help - Get help\n\n"
        f"Ready to make a deposit? Use /deposit to begin!"
    )
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_message = (
        "ℹ️ **How to Deposit**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Use /deposit or /depo command\n"
        "2️⃣ Select the cryptocurrency you want to deposit\n"
        "3️⃣ Choose or enter the amount\n"
        "4️⃣ Send crypto to the provided address\n"
        "5️⃣ Wait for confirmation (auto-tracked)\n"
        "6️⃣ Receive success notification!\n\n"
        "⚠️ **Important Notes:**\n"
        "• Always send the exact amount shown\n"
        "• Include memo/tag if provided\n"
        "• Deposits expire after 30 minutes\n"
        "• Minimum amounts apply per currency\n\n"
        "📞 **Support:** Contact @YourSupport"
    )
    
    await update.message.reply_text(help_message, parse_mode="Markdown")


async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /deposit and /depo commands - Start deposit flow"""
    message = (
        "💰 **New Deposit**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select the cryptocurrency you want to deposit:\n"
    )
    
    await update.message.reply_text(
        message,
        reply_markup=create_coin_keyboard(),
        parse_mode="Markdown"
    )
    
    return SELECTING_COIN


async def coin_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle coin selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Deposit cancelled.")
        return ConversationHandler.END
    
    if query.data == "back_to_coins":
        await query.edit_message_text(
            "💰 **New Deposit**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select the cryptocurrency you want to deposit:",
            reply_markup=create_coin_keyboard(),
            parse_mode="Markdown"
        )
        return SELECTING_COIN
    
    coin_code = query.data.replace("coin_", "")
    context.user_data["selected_coin"] = coin_code
    
    # Get coin info
    coin_info = next((c for c in MAIN_COINS if c["code"] == coin_code), None)
    coin_name = coin_info["name"] if coin_info else coin_code
    
    # Get minimum amount from API
    price_result = ff_api.get_price(coin_code, DEFAULT_RECEIVE_CURRENCY, 0.001)
    min_amount = "Varies"
    if price_result["success"]:
        min_amount = price_result["data"]["from"].get("min", "Varies")
    
    message = (
        f"💰 **Deposit {coin_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 **Minimum:** {min_amount} {coin_code}\n\n"
        f"Select or enter the amount to deposit:"
    )
    
    await query.edit_message_text(
        message,
        reply_markup=create_amount_keyboard(coin_code),
        parse_mode="Markdown"
    )
    
    return ENTERING_AMOUNT


async def amount_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle amount selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Deposit cancelled.")
        return ConversationHandler.END
    
    if query.data == "back_to_coins":
        await query.edit_message_text(
            "💰 **New Deposit**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select the cryptocurrency you want to deposit:",
            reply_markup=create_coin_keyboard(),
            parse_mode="Markdown"
        )
        return SELECTING_COIN
    
    if query.data == "amount_custom":
        coin_code = context.user_data.get("selected_coin")
        await query.edit_message_text(
            f"💰 **Custom Amount**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Please type the amount of {coin_code} you want to deposit:\n\n"
            f"Example: `0.05`",
            parse_mode="Markdown"
        )
        return ENTERING_AMOUNT
    
    # Process selected amount
    amount = query.data.replace("amount_", "")
    context.user_data["selected_amount"] = amount
    
    return await process_deposit(update, context, is_callback=True)


async def custom_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom amount input"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        context.user_data["selected_amount"] = str(amount)
        return await process_deposit(update, context, is_callback=False)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number.\n"
            "Example: `0.05` or `100`",
            parse_mode="Markdown"
        )
        return ENTERING_AMOUNT


async def process_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False) -> int:
    """Process the deposit and create order"""
    coin_code = context.user_data.get("selected_coin")
    amount = context.user_data.get("selected_amount")
    
    if is_callback:
        query = update.callback_query
        message_func = query.edit_message_text
        chat_id = query.message.chat_id
    else:
        message_func = update.message.reply_text
        chat_id = update.message.chat_id
    
    user_id = update.effective_user.id
    
    # Show processing message
    await message_func("⏳ Creating deposit address... Please wait.")
    
    # Get receiving wallet
    to_currency = DEFAULT_RECEIVE_CURRENCY
    to_address = RECEIVING_WALLETS.get(to_currency)
    
    if not to_address or to_address.startswith("YOUR_"):
        # If no receiving wallet configured, use same currency
        to_currency = coin_code
        to_address = RECEIVING_WALLETS.get(coin_code)
        
        if not to_address or to_address.startswith("YOUR_"):
            await context.bot.send_message(
                chat_id,
                "❌ **Error:** Receiving wallet not configured.\n"
                "Please contact administrator.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
    
    # Create order via FF.io API
    order_result = ff_api.create_order(
        from_currency=coin_code,
        to_currency=to_currency,
        amount=float(amount),
        to_address=to_address,
        order_type="float"
    )
    
    if not order_result["success"]:
        error_msg = order_result.get("error", "Unknown error")
        await context.bot.send_message(
            chat_id,
            f"❌ **Error creating deposit:**\n{error_msg}\n\n"
            f"Please try again or contact support.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    order_data = order_result["data"]
    
    # Create deposit order record
    deposit_order = DepositOrder(
        user_id=user_id,
        chat_id=chat_id,
        order_id=order_data["id"],
        token=order_data["token"],
        from_currency=coin_code,
        to_currency=to_currency,
        deposit_address=order_data["from"]["address"],
        deposit_tag=order_data["from"].get("tag"),
        expected_amount=order_data["from"]["amount"],
        receive_amount=order_data["to"]["amount"],
        status=order_data["status"]
    )
    
    # Store deposit
    active_deposits[order_data["id"]] = deposit_order
    if user_id not in user_deposits:
        user_deposits[user_id] = []
    user_deposits[user_id].append(deposit_order)
    
    # Send deposit details
    deposit_message = format_deposit_message(deposit_order)
    
    # Create action buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Copy Address", callback_data=f"copy_{order_data['id']}"),
            InlineKeyboardButton("🔄 Check Status", callback_data=f"check_{order_data['id']}")
        ],
        [
            InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_data['id']}")
        ]
    ])
    
    await context.bot.send_message(
        chat_id,
        deposit_message,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    # Start tracking this deposit
    asyncio.create_task(track_deposit(context.bot, deposit_order))
    
    return ConversationHandler.END


async def track_deposit(bot, order: DepositOrder) -> None:
    """Background task to track deposit status"""
    logger.info(f"Started tracking deposit: {order.order_id}")
    
    while True:
        await asyncio.sleep(TRACKING_INTERVAL)
        
        # Check if order still active
        if order.order_id not in active_deposits:
            logger.info(f"Order {order.order_id} no longer active")
            break
        
        # Get order status from API
        result = ff_api.get_order(order.order_id, order.token)
        
        if not result["success"]:
            logger.error(f"Failed to get order status: {result.get('error')}")
            continue
        
        order_data = result["data"]
        new_status = order_data["status"]
        
        # Check if status changed
        if new_status != order.status:
            old_status = order.status
            order.status = new_status
            
            logger.info(f"Order {order.order_id} status changed: {old_status} -> {new_status}")
            
            # Notify user of status change
            if new_status == "PENDING":
                await bot.send_message(
                    order.chat_id,
                    f"⏳ **Deposit Detected!**\n\n"
                    f"🔖 Order: `{order.order_id}`\n"
                    f"📊 Status: Waiting for confirmations...\n"
                    f"💰 Amount: {order_data['from']['tx'].get('amount', order.expected_amount)} {order.from_currency}",
                    parse_mode="Markdown"
                )
            
            elif new_status == "EXCHANGE":
                await bot.send_message(
                    order.chat_id,
                    f"🔄 **Processing Exchange**\n\n"
                    f"🔖 Order: `{order.order_id}`\n"
                    f"📊 Status: Exchanging your crypto...",
                    parse_mode="Markdown"
                )
            
            elif new_status == "WITHDRAW":
                await bot.send_message(
                    order.chat_id,
                    f"📤 **Sending Funds**\n\n"
                    f"🔖 Order: `{order.order_id}`\n"
                    f"📊 Status: Sending to your wallet...",
                    parse_mode="Markdown"
                )
            
            elif new_status == "DONE":
                # Success notification
                tx_hash = order_data["to"]["tx"].get("id", "N/A")
                received = order_data["to"]["tx"].get("amount", order.receive_amount)
                
                success_message = (
                    f"✅ **Deposit Successful!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🔖 Order: `{order.order_id}`\n"
                    f"💰 Deposited: {order.expected_amount} {order.from_currency}\n"
                    f"💵 Received: {received} {order.to_currency}\n"
                    f"🔗 TX: `{tx_hash[:20]}...`\n\n"
                    f"Thank you for using our service! 🙏"
                )
                
                await bot.send_message(
                    order.chat_id,
                    success_message,
                    parse_mode="Markdown"
                )
                
                # Remove from active deposits
                del active_deposits[order.order_id]
                break
            
            elif new_status == "EXPIRED":
                await bot.send_message(
                    order.chat_id,
                    f"⏰ **Deposit Expired**\n\n"
                    f"🔖 Order: `{order.order_id}`\n"
                    f"📊 Status: Order expired (no payment received)\n\n"
                    f"Please create a new deposit if needed.",
                    parse_mode="Markdown"
                )
                
                # Remove from active deposits
                del active_deposits[order.order_id]
                break
            
            elif new_status == "EMERGENCY":
                emergency_status = order_data.get("emergency", {}).get("status", [])
                
                await bot.send_message(
                    order.chat_id,
                    f"⚠️ **Attention Required**\n\n"
                    f"🔖 Order: `{order.order_id}`\n"
                    f"📊 Status: {', '.join(emergency_status)}\n\n"
                    f"Please contact support for assistance.",
                    parse_mode="Markdown"
                )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - Show active deposits"""
    user_id = update.effective_user.id
    
    user_active = [
        order for order in active_deposits.values()
        if order.user_id == user_id
    ]
    
    if not user_active:
        await update.message.reply_text(
            "📭 **No Active Deposits**\n\n"
            "You don't have any pending deposits.\n"
            "Use /deposit to start a new one!",
            parse_mode="Markdown"
        )
        return
    
    message = f"📊 **Your Active Deposits**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for order in user_active:
        message += (
            f"🔖 **Order:** `{order.order_id}`\n"
            f"💰 {order.expected_amount} {order.from_currency}\n"
            f"📊 Status: {get_status_emoji(order.status)} {order.status}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command - Show deposit history"""
    user_id = update.effective_user.id
    
    user_history = user_deposits.get(user_id, [])
    
    if not user_history:
        await update.message.reply_text(
            "📭 **No Deposit History**\n\n"
            "You haven't made any deposits yet.\n"
            "Use /deposit to start!",
            parse_mode="Markdown"
        )
        return
    
    message = f"📜 **Deposit History**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Show last 10 deposits
    for order in user_history[-10:]:
        message += (
            f"🔖 `{order.order_id}` | "
            f"{order.expected_amount} {order.from_currency} | "
            f"{get_status_emoji(order.status)} {order.status}\n"
        )
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def check_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle check status button"""
    query = update.callback_query
    await query.answer()
    
    order_id = query.data.replace("check_", "")
    
    if order_id not in active_deposits:
        await query.answer("Order not found or completed", show_alert=True)
        return
    
    order = active_deposits[order_id]
    
    # Get latest status from API
    result = ff_api.get_order(order.order_id, order.token)
    
    if result["success"]:
        order_data = result["data"]
        order.status = order_data["status"]
        
        # Update message
        await query.edit_message_text(
            format_deposit_message(order),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📋 Copy Address", callback_data=f"copy_{order_id}"),
                    InlineKeyboardButton("🔄 Check Status", callback_data=f"check_{order_id}")
                ],
                [
                    InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_id}")
                ]
            ]),
            parse_mode="Markdown"
        )
    else:
        await query.answer("Failed to fetch status", show_alert=True)


async def copy_address_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle copy address button"""
    query = update.callback_query
    order_id = query.data.replace("copy_", "")
    
    if order_id not in active_deposits:
        await query.answer("Order not found", show_alert=True)
        return
    
    order = active_deposits[order_id]
    await query.answer(f"Address: {order.deposit_address}", show_alert=True)


async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel order button"""
    query = update.callback_query
    order_id = query.data.replace("cancel_order_", "")
    
    if order_id not in active_deposits:
        await query.answer("Order not found or already completed", show_alert=True)
        return
    
    # Remove from active tracking
    del active_deposits[order_id]
    
    await query.edit_message_text(
        f"❌ **Order Cancelled**\n\n"
        f"🔖 Order `{order_id}` has been cancelled.\n"
        f"Use /deposit to create a new one.",
        parse_mode="Markdown"
    )


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text(
        "❌ Deposit cancelled.\n"
        "Use /deposit to start again."
    )
    return ConversationHandler.END


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Start the bot"""
    # Validate configuration
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ Error: Please set your TELEGRAM_BOT_TOKEN")
        print("   Get it from @BotFather on Telegram")
        return
    
    if FF_API_KEY == "YOUR_FF_API_KEY":
        print("❌ Error: Please set your FF_API_KEY")
        print("   Get it from https://ff.io/user/apikey")
        return
    
    if FF_API_SECRET == "YOUR_FF_API_SECRET":
        print("❌ Error: Please set your FF_API_SECRET")
        print("   Get it from https://ff.io/user/apikey")
        return
    
    print("🚀 Starting Crypto Deposit Bot...")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Conversation handler for deposit flow
    deposit_handler = ConversationHandler(
        entry_points=[
            CommandHandler("deposit", deposit_command),
            CommandHandler("depo", deposit_command),
        ],
        states={
            SELECTING_COIN: [
                CallbackQueryHandler(coin_selected_callback, pattern="^coin_|^cancel$|^back_to_coins$")
            ],
            ENTERING_AMOUNT: [
                CallbackQueryHandler(amount_selected_callback, pattern="^amount_|^cancel$|^back_to_coins$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_amount_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
        ],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(deposit_handler)
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(check_status_callback, pattern="^check_"))
    application.add_handler(CallbackQueryHandler(copy_address_callback, pattern="^copy_"))
    application.add_handler(CallbackQueryHandler(cancel_order_callback, pattern="^cancel_order_"))
    
    # Start polling
    print("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# Import filters for message handler
from telegram.ext import filters

if __name__ == "__main__":
    main()
