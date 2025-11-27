import logging
import os
import re
from telegram import Update, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
from collections import defaultdict
import aiohttp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y")
PROVIDER_TOKEN = ""  # Empty for Stars payments
USERBOT_API_URL = os.environ.get("USERBOT_API_URL", "http://localhost:8080")

# Store user balances
user_balances = defaultdict(float)

# Store pending group payments
pending_group_payments = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command in bot DM"""
    user = update.effective_user
    user_id = user.id
    
    # Check if this is a group payment start
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        
        # Handle balance check
        if arg == "balance":
            balance = user_balances[user_id]
            await update.message.reply_html(
                f"💰 <b>Your Balance</b>\n\n"
                f"⭐ Stars: <b>{balance}</b>\n"
                f"💵 USD: <b>${balance * 0.0179:.2f}</b>"
            )
            return
        
        # Handle group payment
        if arg.startswith("grouppay_"):
            await handle_group_payment_start(update, context, arg)
            return
    
    # Regular start message
    balance = user_balances[user_id]
    
    welcome_text = (
        f"🐱 <b>Welcome to Lenrao Game Bot</b>\n\n"
        f"⭐️ This bot handles payments for group games\n\n"
        f"💰 Your Balance: <b>{balance} ⭐</b>\n\n"
        f"<b>Commands:</b>\n"
        f"/balance - Check balance\n"
        f"/deposit - Add Stars\n"
        f"/withdraw - Withdraw Stars\n"
        f"/profile - View profile\n"
        f"/history - Game history\n\n"
        f"💡 To play games, use the bot in authorized groups!"
    )
    
    await update.message.reply_html(welcome_text)

async def handle_group_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str):
    """Handle payment initiation from group"""
    user = update.effective_user
    user_id = user.id
    
    # Parse payment data: grouppay_<chat_id>_<user_id>_<game_type>_<bet_amount>_<rounds>_<throws>
    parts = arg.split("_")
    if len(parts) != 7:
        await update.message.reply_html("❌ Invalid payment link!")
        return
    
    try:
        chat_id = int(parts[1])
        expected_user_id = int(parts[2])
        game_type = parts[3]
        bet_amount = int(parts[4])
        rounds = int(parts[5])
        throws = int(parts[6])
        
        # Verify user
        if user_id != expected_user_id:
            await update.message.reply_html("❌ This payment link is not for you!")
            return
        
        # Store pending payment
        payment_key = f"{chat_id}_{user_id}"
        pending_group_payments[payment_key] = {
            'chat_id': chat_id,
            'user_id': user_id,
            'game_type': game_type,
            'bet_amount': bet_amount,
            'rounds': rounds,
            'throws': throws
        }
        
        game_names = {
            'dice': '🎲 Dice',
            'bowl': '🎳 Bowling',
            'arrow': '🎯 Darts',
            'football': '⚽ Football',
            'basket': '🏀 Basketball'
        }
        
        # Send invoice
        title = f"Group Game Payment"
        description = f"{game_names.get(game_type, 'Game')} - {bet_amount} Stars"
        payload = f"grouppay_{chat_id}_{user_id}_{game_type}_{bet_amount}_{rounds}_{throws}"
        prices = [LabeledPrice("Game Bet", bet_amount)]
        
        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="XTR",
            prices=prices
        )
        
        await update.message.reply_html(
            f"💳 <b>Payment Invoice Sent</b>\n\n"
            f"🎮 Game: {game_names.get(game_type, 'Unknown')}\n"
            f"💰 Amount: <b>{bet_amount} ⭐</b>\n"
            f"🔄 Rounds: <b>{rounds}</b>\n"
            f"🎯 Throws: <b>{throws}</b>\n\n"
            f"Complete the payment to start playing!"
        )
        
    except (ValueError, IndexError) as e:
        logger.error(f"Payment parsing error: {e}")
        await update.message.reply_html("❌ Invalid payment data!")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check balance"""
    user_id = update.effective_user.id
    balance = user_balances[user_id]
    
    await update.message.reply_html(
        f"💰 <b>Your Balance</b>\n\n"
        f"⭐ Stars: <b>{balance}</b>\n"
        f"💵 USD: <b>${balance * 0.0179:.2f}</b>"
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout for Stars payment"""
    query = update.pre_checkout_query
    
    # Always approve - Stars payments are handled by Telegram
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment"""
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    
    amount = payment.total_amount
    payload = payment.invoice_payload
    
    # Check if this is a group game payment
    if payload.startswith("grouppay_"):
        await handle_group_payment_success(update, context, payload, amount)
    else:
        # Regular deposit
        user_balances[user_id] += amount
        await update.message.reply_html(
            f"✅ <b>Payment Successful!</b>\n\n"
            f"💰 Added: <b>{amount} ⭐</b>\n"
            f"💳 New Balance: <b>{user_balances[user_id]} ⭐</b>"
        )

async def handle_group_payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str, amount: int):
    """Handle successful group game payment"""
    user = update.effective_user
    user_id = user.id
    
    # Parse payload
    parts = payload.split("_")
    try:
        chat_id = int(parts[1])
        payment_user_id = int(parts[2])
        game_type = parts[3]
        bet_amount = int(parts[4])
        rounds = int(parts[5])
        throws = int(parts[6])
        
        if user_id != payment_user_id:
            await update.message.reply_html("❌ Payment verification failed!")
            return
        
        # Deduct from user balance or add to balance
        user_balances[user_id] += amount - bet_amount  # Add payment, deduct bet
        
        # Send confirmation to user
        await update.message.reply_html(
            f"✅ <b>Payment Confirmed!</b>\n\n"
            f"💰 Paid: <b>{bet_amount} ⭐</b>\n"
            f"💳 Balance: <b>{user_balances[user_id]} ⭐</b>\n\n"
            f"🎮 Game starting in group..."
        )
        
        # Notify userbot to start game (you'll need to implement this)
        # This could be via HTTP webhook, bot DM, or direct database
        
        # For now, we'll send a message to a channel/group that userbot monitors
        # Or use an HTTP endpoint if you set up a simple API for the userbot
        
        # Example: Send command to userbot via Saved Messages
        try:
            await context.bot.send_message(
                chat_id=user_id,  # Send to yourself/admin
                text=f"/confirm_payment {chat_id} {user_id} {game_type} {bet_amount} {rounds} {throws}"
            )
        except Exception as e:
            logger.error(f"Failed to notify userbot: {e}")
        
    except (ValueError, IndexError) as e:
        logger.error(f"Payment success parsing error: {e}")
        await update.message.reply_html("❌ Payment processing error!")

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit command"""
    await update.message.reply_html(
        "💳 <b>Deposit Stars</b>\n\n"
        "Use /custom <amount> to deposit\n"
        "Example: /custom 100\n\n"
        "Min: 1 ⭐ | Max: 2500 ⭐"
    )

async def custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Custom deposit amount"""
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "💳 <b>Custom Deposit</b>\n\n"
            "Usage: /custom <amount>\n"
            "Example: /custom 150\n\n"
            "Min: 1 ⭐ | Max: 2500 ⭐"
        )
        return
    
    try:
        amount = int(context.args[0])
        
        if amount < 1:
            await update.message.reply_html("❌ Minimum deposit: 1 ⭐")
            return
        
        if amount > 2500:
            await update.message.reply_html("❌ Maximum deposit: 2500 ⭐")
            return
        
        user_id = update.effective_user.id
        title = f"Deposit {amount} Stars"
        description = f"Add {amount} ⭐ to balance"
        payload = f"deposit_{amount}_{user_id}"
        prices = [LabeledPrice("Stars", amount)]
        
        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="XTR",
            prices=prices
        )
    except ValueError:
        await update.message.reply_html("❌ Invalid amount!")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View profile"""
    user = update.effective_user
    user_id = user.id
    balance = user_balances[user_id]
    
    await update.message.reply_html(
        f"📢 <b>Profile</b>\n\n"
        f"ℹ️ User ID: <code>{user_id}</code>\n"
        f"👤 Username: @{user.username or 'N/A'}\n"
        f"💰 Balance: <b>{balance} ⭐</b>\n"
        f"💵 USD: <b>${balance * 0.0179:.2f}</b>"
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View game history"""
    await update.message.reply_html(
        "📊 <b>Game History</b>\n\n"
        "Coming soon..."
    )

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Withdraw command"""
    await update.message.reply_html(
        "💎 <b>Withdraw Stars</b>\n\n"
        "Coming soon..."
    )

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("custom", custom_deposit))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    
    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    logger.info("Main bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
