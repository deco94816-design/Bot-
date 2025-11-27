import logging
import random
import string
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
from collections import defaultdict
import asyncio
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y")
PROVIDER_TOKEN = ""
ADMIN_ID = 5709159932

user_games = {}
user_balances = defaultdict(int)
game_locks = defaultdict(asyncio.Lock)
user_withdrawals = {}
withdrawal_counter = 26356

STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014

GAME_TYPES = {
    'dice': {'emoji': '🎲', 'name': 'Dice', 'max_value': 6, 'icon': '🎲'},
    'bowl': {'emoji': '🎳', 'name': 'Bowling', 'max_value': 6, 'icon': '🎳'},
    'arrow': {'emoji': '🎯', 'name': 'Darts', 'max_value': 6, 'icon': '🎯'},
    'football': {'emoji': '⚽', 'name': 'Football', 'max_value': 5, 'icon': '🥅'},
    'basket': {'emoji': '🏀', 'name': 'Basketball', 'max_value': 5, 'icon': '🏀'}
}

class Game:
    def __init__(self, user_id, username, bet_amount, rounds, throw_count, game_type):
        self.user_id = user_id
        self.username = username
        self.bet_amount = bet_amount
        self.total_rounds = rounds
        self.throw_count = throw_count
        self.game_type = game_type
        self.current_round = 0
        self.user_score = 0
        self.bot_score = 0
        self.user_results = []
        self.bot_results = []
        self.is_demo = False

def generate_transaction_id():
    chars = string.ascii_letters + string.digits
    return 'stx' + ''.join(random.choice(chars) for _ in range(80))

def is_valid_ton_address(address):
    if not address:
        return False
    ton_pattern = r'^(UQ|EQ|kQ|0Q)[A-Za-z0-9_-]{46}$'
    if re.match(ton_pattern, address):
        return True
    raw_pattern = r'^-?[0-9]+:[a-fA-F0-9]{64}$'
    if re.match(raw_pattern, address):
        return True
    return len(address) >= 48 and len(address) <= 67

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    admin_text = "\n\n🔑 <b>Admin Commands:</b>\n/demo - Test all games without payment" if is_admin else ""
    
    welcome_text = (
        f"🎮 <b>Welcome to Multi-Game Bot, {user.mention_html()}!</b>\n\n"
        f"💰 <b>Commands:</b>\n"
        f"/deposit - Add Stars to balance\n"
        f"/custom <amount> - Custom deposit\n"
        f"/balance - Check balance\n"
        f"/withdraw - Withdraw Stars to TON\n\n"
        f"🎯 <b>Games:</b>\n"
        f"🎲 /dice - Dice Game\n"
        f"🎳 /bowl - Bowling Game\n"
        f"🎯 /arrow - Darts Game\n"
        f"🥅 /football - Football Game\n"
        f"🏀 /basket - Basketball Game"
        f"{admin_text}\n\n"
        f"💎 Play, win, and earn Stars!"
    )
    await update.message.reply_html(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎯 <b>How to Play:</b>\n\n"
        "1️⃣ Deposit Stars using /deposit\n"
        "2️⃣ Choose a game (/dice, /bowl, /arrow, /football, /basket)\n"
        "3️⃣ Select bet amount\n"
        "4️⃣ Choose rounds (1-3)\n"
        "5️⃣ Choose throws (1-3)\n"
        "6️⃣ Send your emojis!\n"
        "7️⃣ Bot responds instantly\n"
        "8️⃣ Higher total wins!\n\n"
        "🏆 Most rounds won = Winner!\n"
        "💎 Winner takes the pot!"
    )
    await update.message.reply_html(help_text)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = user_balances[user_id]
    await update.message.reply_html(
        f"💰 Your balance: <b>{balance} ⭐</b>"
    )

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("10 ⭐", callback_data="deposit_10"),
            InlineKeyboardButton("25 ⭐", callback_data="deposit_25"),
        ],
        [
            InlineKeyboardButton("50 ⭐", callback_data="deposit_50"),
            InlineKeyboardButton("100 ⭐", callback_data="deposit_100"),
        ],
        [
            InlineKeyboardButton("250 ⭐", callback_data="deposit_250"),
            InlineKeyboardButton("500 ⭐", callback_data="deposit_500"),
        ],
        [
            InlineKeyboardButton("💳 Custom Amount", callback_data="deposit_custom"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        "💳 <b>Select deposit amount:</b>",
        reply_markup=reply_markup
    )

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['withdraw_state'] = None
    context.user_data['withdraw_amount'] = None
    context.user_data['withdraw_address'] = None
    
    welcome_text = (
        "✨ <b>Welcome to Stars Withdrawal !</b>\n\n"
        "<b>Withdraw:</b>\n"
        "1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
        "<blockquote>⚙️ <b>Good to know:</b>\n"
        "• When you exchange stars through a channel or bot, Telegram keeps a 15% fee and applies a 21-day hold.\n"
        "• We send TON immediately—factoring in this fee and a small service premium.</blockquote>"
    )
    
    keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "💳 <b>Custom Deposit</b>\n\n"
            "Usage: /custom <amount>\n"
            "Example: /custom 150\n\n"
            "Minimum: 1 ⭐\n"
            "Maximum: 2500 ⭐"
        )
        return
    
    try:
        amount = int(context.args[0])
        
        if amount < 1:
            await update.message.reply_html("❌ Minimum deposit is 1 ⭐")
            return
        
        if amount > 2500:
            await update.message.reply_html("❌ Maximum deposit is 2500 ⭐")
            return
        
        title = f"Deposit {amount} Stars"
        description = f"Add {amount} ⭐ to your game balance"
        payload = f"deposit_{amount}_{update.effective_user.id}"
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
        await update.message.reply_html("❌ Invalid amount! Please enter a number.")
    except Exception as e:
        logger.error(f"Custom deposit error: {e}")
        await update.message.reply_html("❌ An error occurred. Please try again.")

async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    user_id = update.effective_user.id
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await update.message.reply_html(
                "❌ You already have an active game! Finish it first."
            )
            return
        
        balance = user_balances[user_id]
        
        if balance < 1:
            await update.message.reply_html(
                "❌ Insufficient balance! Use /deposit to add Stars.\n"
                f"Your balance: <b>{balance} ⭐</b>"
            )
            return
        
        context.user_data['game_type'] = game_type
        context.user_data['is_demo'] = False
        
        game_info = GAME_TYPES[game_type]
        keyboard = [
            [
                InlineKeyboardButton("10 ⭐", callback_data=f"bet_{game_type}_10"),
                InlineKeyboardButton("25 ⭐", callback_data=f"bet_{game_type}_25"),
            ],
            [
                InlineKeyboardButton("50 ⭐", callback_data=f"bet_{game_type}_50"),
                InlineKeyboardButton("100 ⭐", callback_data=f"bet_{game_type}_100"),
            ],
            [
                InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\n"
            f"Your balance: <b>{balance} ⭐</b>",
            reply_markup=reply_markup
        )

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'dice')

async def bowl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'bowl')

async def arrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'arrow')

async def football_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'football')

async def basket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'basket')

async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_html("❌ This command is only for administrators.")
        return
    
    if user_id in user_games:
        await update.message.reply_html(
            "❌ You already have an active game! Finish it first."
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("🎲 Dice", callback_data="demo_game_dice"),
            InlineKeyboardButton("🎳 Bowl", callback_data="demo_game_bowl"),
        ],
        [
            InlineKeyboardButton("🎯 Arrow", callback_data="demo_game_arrow"),
            InlineKeyboardButton("🥅 Football", callback_data="demo_game_football"),
        ],
        [
            InlineKeyboardButton("🏀 Basketball", callback_data="demo_game_basket"),
        ],
        [
            InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        f"🎮 <b>DEMO MODE</b> 🔑\n\n"
        f"🎯 Choose a game to test:\n"
        f"(No Stars will be deducted)",
        reply_markup=reply_markup
    )

async def send_invoice(query, amount):
    title = f"Deposit {amount} Stars"
    description = f"Add {amount} ⭐ to your game balance"
    payload = f"deposit_{amount}_{query.from_user.id}"
    prices = [LabeledPrice("Stars", amount)]
    
    await query.message.reply_invoice(
        title=title,
        description=description,
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency="XTR",
        prices=prices
    )
    await query.edit_message_text(
        f"💳 Invoice for <b>{amount} ⭐</b> sent!\n"
        f"Complete the payment to add Stars to your balance.",
        parse_mode=ParseMode.HTML
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            await query.edit_message_text(
                "💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                "Example: 100",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "confirm_withdraw":
            global withdrawal_counter
            
            stars_amount = context.user_data.get('withdraw_amount', 0)
            ton_address = context.user_data.get('withdraw_address', '')
            
            balance = user_balances[user_id]
            if balance < stars_amount:
                await query.edit_message_text(
                    "❌ <b>Insufficient balance!</b>\n\n"
                    f"Your balance: {balance} ⭐\n"
                    f"Requested: {stars_amount} ⭐\n\n"
                    "Use /withdraw to try again.",
                    parse_mode=ParseMode.HTML
                )
                context.user_data['withdraw_state'] = None
                return
            
            user_balances[user_id] -= stars_amount
            
            withdrawal_counter += 1
            exchange_id = withdrawal_counter
            
            ton_amount = round(stars_amount * STARS_TO_TON, 8)
            transaction_id = generate_transaction_id()
            
            now = datetime.now()
            created_date = now.strftime("%Y-%m-%d %H:%M")
            hold_until = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
            
            user_withdrawals[user_id] = {
                'exchange_id': exchange_id,
                'stars': stars_amount,
                'ton_amount': ton_amount,
                'address': ton_address,
                'transaction_id': transaction_id,
                'created': created_date,
                'hold_until': hold_until,
                'status': 'on_hold'
            }
            
            receipt_text = (
                f"📄 <b>Stars withdraw exchange #{exchange_id}</b>\n\n"
                f"📊 Exchange status: Processing\n"
                f"⭐️ Stars withdrawal: {stars_amount}\n"
                f"💎 TON amount: {ton_amount}\n\n"
                f"<b>Sale:</b>\n"
                f"🏷 Top-up status: Paid\n"
                f"🗓 Created: {created_date}\n"
                f"🏦 TON address: <code>{ton_address}</code>\n"
                f"🧾 Transaction ID: <code>{transaction_id}</code>\n\n"
                f"💸 Withdrawal status: On hold\n"
                f"💎 TON amount: {ton_amount}\n"
                f"🗓 Withdrawal created: {created_date}\n"
                f"⏳ On hold until: {hold_until}\n"
                f"📝 Reason: Lenrao game rating is negative. Placed on 14-day hold."
            )
            
            await query.edit_message_text(
                receipt_text,
                parse_mode=ParseMode.HTML
            )
            
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            return
        
        if data == "cancel_withdraw":
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            await query.edit_message_text(
                "❌ <b>Withdrawal cancelled.</b>\n\n"
                "Use /withdraw to start again.",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("deposit_"):
            if data == "deposit_custom":
                await query.edit_message_text(
                    "💳 <b>Custom Deposit</b>\n\n"
                    "Please send the amount you want to deposit.\n\n"
                    "Example: Just type <code>150</code>\n\n"
                    "Minimum: 1 ⭐\n"
                    "Maximum: 2500 ⭐",
                    parse_mode=ParseMode.HTML
                )
                context.user_data['waiting_for_custom_amount'] = True
                return
            
            amount = int(data.split("_")[1])
            await send_invoice(query, amount)
            return
        
        if data.startswith("demo_game_"):
            if user_id != ADMIN_ID:
                await query.answer("❌ Admin only!", show_alert=True)
                return
            
            game_type = data.split("_")[2]
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = True
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("10 ⭐", callback_data=f"demo_bet_{game_type}_10"),
                    InlineKeyboardButton("25 ⭐", callback_data=f"demo_bet_{game_type}_25"),
                ],
                [
                    InlineKeyboardButton("50 ⭐", callback_data=f"demo_bet_{game_type}_50"),
                    InlineKeyboardButton("100 ⭐", callback_data=f"demo_bet_{game_type}_100"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data="back_to_demo_menu"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🎮 <b>DEMO: {game_info['name']}</b> 🔑\n\n"
                f"💰 Choose demo bet:\n"
                f"(No Stars will be deducted)",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "back_to_demo_menu":
            keyboard = [
                [
                    InlineKeyboardButton("🎲 Dice", callback_data="demo_game_dice"),
                    InlineKeyboardButton("🎳 Bowl", callback_data="demo_game_bowl"),
                ],
                [
                    InlineKeyboardButton("🎯 Arrow", callback_data="demo_game_arrow"),
                    InlineKeyboardButton("🥅 Football", callback_data="demo_game_football"),
                ],
                [
                    InlineKeyboardButton("🏀 Basketball", callback_data="demo_game_basket"),
                ],
                [
                    InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🎮 <b>DEMO MODE</b> 🔑\n\n"
                f"🎯 Choose a game to test:\n"
                f"(No Stars will be deducted)",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("demo_bet_"):
            if user_id != ADMIN_ID:
                await query.answer("❌ Admin only!", show_alert=True)
                return
            
            parts = data.split("_")
            game_type = parts[2]
            bet_amount = int(parts[3])
            
            context.user_data['bet_amount'] = bet_amount
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = True
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("1 Round", callback_data=f"rounds_{game_type}_1"),
                    InlineKeyboardButton("2 Rounds", callback_data=f"rounds_{game_type}_2"),
                ],
                [
                    InlineKeyboardButton("3 Rounds", callback_data=f"rounds_{game_type}_3"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data=f"demo_game_{game_type}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select rounds:</b> 🔑\n"
                f"Demo Bet: <b>{bet_amount} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("bet_"):
            parts = data.split("_")
            game_type = parts[1]
            bet_amount = int(parts[2])
            balance = user_balances[user_id]
            
            if balance < bet_amount:
                await query.edit_message_text(
                    "❌ Insufficient balance! Use /deposit to add Stars."
                )
                return
            
            context.user_data['bet_amount'] = bet_amount
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = False
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("1 Round", callback_data=f"rounds_{game_type}_1"),
                    InlineKeyboardButton("2 Rounds", callback_data=f"rounds_{game_type}_2"),
                ],
                [
                    InlineKeyboardButton("3 Rounds", callback_data=f"rounds_{game_type}_3"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data=f"back_to_bet_{game_type}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select number of rounds:</b>\n"
                f"Bet: <b>{bet_amount} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("back_to_bet_"):
            game_type = data.split("_")[3]
            balance = user_balances[user_id]
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("10 ⭐", callback_data=f"bet_{game_type}_10"),
                    InlineKeyboardButton("25 ⭐", callback_data=f"bet_{game_type}_25"),
                ],
                [
                    InlineKeyboardButton("50 ⭐", callback_data=f"bet_{game_type}_50"),
                    InlineKeyboardButton("100 ⭐", callback_data=f"bet_{game_type}_100"),
                ],
                [
                    InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                f"💰 Choose your bet:\n"
                f"Your balance: <b>{balance} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("rounds_"):
            parts = data.split("_")
            game_type = parts[1]
            rounds = int(parts[2])
            bet_amount = context.user_data.get('bet_amount', 10)
            is_demo = context.user_data.get('is_demo', False)
            
            context.user_data['rounds'] = rounds
            
            game_info = GAME_TYPES[game_type]
            demo_badge = " 🔑" if is_demo else ""
            
            keyboard = [
                [
                    InlineKeyboardButton(f"1 {game_info['emoji']}", callback_data=f"throws_{game_type}_1"),
                    InlineKeyboardButton(f"2 {game_info['emoji']}{game_info['emoji']}", callback_data=f"throws_{game_type}_2"),
                ],
                [
                    InlineKeyboardButton(f"3 {game_info['emoji']}{game_info['emoji']}{game_info['emoji']}", callback_data=f"throws_{game_type}_3"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data=f"bet_{game_type}_{bet_amount}" if not is_demo else f"demo_bet_{game_type}_{bet_amount}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select number of throws:</b>{demo_badge}\n"
                f"Bet: <b>{bet_amount} ⭐</b>\n"
                f"Rounds: <b>{rounds}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("throws_"):
            async with game_locks[user_id]:
                parts = data.split("_")
                game_type = parts[1]
                throw_count = int(parts[2])
                bet_amount = context.user_data.get('bet_amount', 10)
                rounds = context.user_data.get('rounds', 1)
                is_demo = context.user_data.get('is_demo', False)
                
                if not is_demo:
                    user_balances[user_id] -= bet_amount
                
                game = Game(
                    user_id=user_id,
                    username=query.from_user.first_name,
                    bet_amount=bet_amount,
                    rounds=rounds,
                    throw_count=throw_count,
                    game_type=game_type
                )
                game.is_demo = is_demo
                user_games[user_id] = game
                
                context.user_data['current_round_user_throws'] = []
                context.user_data['current_round_bot_throws'] = []
                
                game_info = GAME_TYPES[game_type]
                demo_text = " 🔑 DEMO MODE" if is_demo else ""
                throw_emoji = game_info['emoji'] * throw_count
                throw_text = f"{throw_emoji} ({throw_count} throw{'s' if throw_count > 1 else ''})"
                
                await query.edit_message_text(
                    f"🎮 <b>{game_info['name']} Started!{demo_text}</b>\n\n"
                    f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                    f"🎯 Rounds: <b>{rounds}</b>\n"
                    f"{game_info['icon']} Throws: <b>{throw_text}</b>\n\n"
                    f"{game_info['emoji']} <b>Send your {throw_count} {game_info['emoji']} now!</b>\n"
                    f"(Send them one by one)",
                    parse_mode=ParseMode.HTML
                )
            return
        
        if data == "cancel_game":
            if user_id in user_games:
                del user_games[user_id]
            await query.edit_message_text(
                "❌ Game cancelled.",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("replay_"):
            async with game_locks[user_id]:
                multiplier = 1 if data == "replay_same" else 2
                
                if user_id not in user_games:
                    await query.answer("❌ No previous game found!", show_alert=True)
                    return
                
                old_game = user_games[user_id]
                new_bet = old_game.bet_amount * multiplier
                balance = user_balances[user_id]
                
                if not old_game.is_demo and balance < new_bet:
                    await query.answer("❌ Insufficient balance!", show_alert=True)
                    return
                
                if not old_game.is_demo:
                    user_balances[user_id] -= new_bet
                
                game = Game(
                    user_id=user_id,
                    username=query.from_user.first_name,
                    bet_amount=new_bet,
                    rounds=old_game.total_rounds,
                    throw_count=old_game.throw_count,
                    game_type=old_game.game_type
                )
                game.is_demo = old_game.is_demo
                user_games[user_id] = game
                
                context.user_data['current_round_user_throws'] = []
                context.user_data['current_round_bot_throws'] = []
                
                game_info = GAME_TYPES[game.game_type]
                demo_text = " 🔑 DEMO MODE" if game.is_demo else ""
                throw_emoji = game_info['emoji'] * game.throw_count
                throw_text = f"{throw_emoji} ({game.throw_count} throw{'s' if game.throw_count > 1 else ''})"
                
                await query.edit_message_text(
                    f"🎮 <b>New {game_info['name']} Started!{demo_text}</b>\n\n"
                    f"💰 Bet: <b>{new_bet} ⭐</b>\n"
                    f"🎯 Rounds: <b>{game.total_rounds}</b>\n"
                    f"{game_info['icon']} Throws: <b>{throw_text}</b>\n\n"
                    f"{game_info['emoji']} <b>Send your {game.throw_count} {game_info['emoji']} now!</b>\n"
                    f"(Send them one by one)",
                    parse_mode=ParseMode.HTML
                )
            return
        
        if data == "check_balance":
            balance = user_balances[user_id]
            await query.answer(f"💰 Your balance: {balance} ⭐", show_alert=True)
            return
            
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    withdraw_state = context.user_data.get('withdraw_state')
    
    if withdraw_state == 'waiting_amount':
        try:
            amount = int(text)
            
            if amount <= 0:
                await update.message.reply_html(
                    "❌ <b>Invalid amount!</b>\n\n"
                    "Please enter a positive number.\n"
                    "Example: 100"
                )
                return
            
            balance = user_balances[user_id]
            if amount > balance:
                await update.message.reply_html(
                    f"❌ <b>Insufficient balance!</b>\n\n"
                    f"Your balance: {balance} ⭐\n"
                    f"Requested: {amount} ⭐\n\n"
                    f"Please enter a smaller amount or use /deposit to add more Stars."
                )
                return
            
            context.user_data['withdraw_amount'] = amount
            context.user_data['withdraw_state'] = 'waiting_address'
            
            await update.message.reply_html(
                f"📍 <b>Enter your TON address to receive payout for {amount} ⭐️.</b>\n\n"
                f"⚠️ Provide a TON address without memo.\n"
                f"Exchange addresses that require a memo cannot receive payouts."
            )
            return
            
        except ValueError:
            await update.message.reply_html(
                "❌ <b>Invalid input!</b>\n\n"
                "Please enter a valid number (integers only).\n"
                "Example: 100"
            )
            return
    
    elif withdraw_state == 'waiting_address':
        ton_address = text.strip()
        
        if len(ton_address) < 40:
            await update.message.reply_html(
                "❌ <b>Invalid TON address!</b>\n\n"
                "Please provide a valid TON wallet address.\n"
                "The address should be at least 48 characters long."
            )
            return
        
        if ':' in ton_address and 'memo' in ton_address.lower():
            await update.message.reply_html(
                "❌ <b>Memo addresses not supported!</b>\n\n"
                "Please provide a TON address without memo.\n"
                "Exchange addresses that require a memo cannot receive payouts."
            )
            return
        
        context.user_data['withdraw_address'] = ton_address
        stars_amount = context.user_data.get('withdraw_amount', 0)
        ton_amount = round(stars_amount * STARS_TO_TON, 8)
        
        confirm_text = (
            f"📝 <b>Confirm your withdrawal:</b>\n\n"
            f"⭐️ Stars: {stars_amount}\n"
            f"💎 TON amount: {ton_amount}\n"
            f"🏦 Address: <code>{ton_address}</code>"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(confirm_text, reply_markup=reply_markup)
        return
    
    if context.user_data.get('waiting_for_custom_amount'):
        try:
            amount = int(text)
            context.user_data['waiting_for_custom_amount'] = False
            
            if amount < 1:
                await update.message.reply_html("❌ Minimum deposit is 1 ⭐")
                return
            
            if amount > 2500:
                await update.message.reply_html("❌ Maximum deposit is 2500 ⭐")
                return
            
            title = f"Deposit {amount} Stars"
            description = f"Add {amount} ⭐ to your game balance"
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
            return
        except ValueError:
            await update.message.reply_html(
                "❌ Invalid amount! Please enter a number.\n\n"
                "Example: 150"
            )
            return
    
    if user_id in user_games:
        game = user_games[user_id]
        game_info = GAME_TYPES[game.game_type]
        
        if update.message.dice and update.message.dice.emoji == game_info['emoji']:
            value = update.message.dice.value
            
            user_throws = context.user_data.get('current_round_user_throws', [])
            user_throws.append(value)
            context.user_data['current_round_user_throws'] = user_throws
            
            if len(user_throws) >= game.throw_count:
                bot_throws = []
                for _ in range(game.throw_count):
                    bot_msg = await update.message.reply_dice(emoji=game_info['emoji'])
                    bot_throws.append(bot_msg.dice.value)
                    await asyncio.sleep(0.5)
                
                context.user_data['current_round_bot_throws'] = bot_throws
                
                user_total = sum(user_throws)
                bot_total = sum(bot_throws)
                
                game.current_round += 1
                
                if user_total > bot_total:
                    game.user_score += 1
                    round_result = "You win this round! 🎉"
                elif bot_total > user_total:
                    game.bot_score += 1
                    round_result = "Bot wins this round! 🤖"
                else:
                    round_result = "It's a tie! 🤝"
                
                await asyncio.sleep(2)
                
                round_summary = (
                    f"📊 <b>Round {game.current_round} Results:</b>\n\n"
                    f"You: {user_throws} = {user_total}\n"
                    f"Bot: {bot_throws} = {bot_total}\n\n"
                    f"{round_result}\n\n"
                    f"<b>Score:</b> You {game.user_score} - {game.bot_score} Bot"
                )
                
                if game.current_round >= game.total_rounds:
                    if game.user_score > game.bot_score:
                        winnings = game.bet_amount * 2
                        if not game.is_demo:
                            user_balances[user_id] += winnings
                        final_result = f"🏆 <b>YOU WIN!</b> +{winnings} ⭐"
                    elif game.bot_score > game.user_score:
                        final_result = f"😢 <b>Bot wins!</b> -{game.bet_amount} ⭐"
                    else:
                        if not game.is_demo:
                            user_balances[user_id] += game.bet_amount
                        final_result = f"🤝 <b>It's a tie!</b> Bet returned."
                    
                    demo_text = " 🔑 DEMO" if game.is_demo else ""
                    balance = user_balances[user_id]
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("🔄 Same Bet", callback_data="replay_same"),
                            InlineKeyboardButton("⏫ Double Bet", callback_data="replay_double"),
                        ],
                        [
                            InlineKeyboardButton("💰 Balance", callback_data="check_balance"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_html(
                        f"{round_summary}\n\n"
                        f"{'─' * 20}\n\n"
                        f"{final_result}{demo_text}\n"
                        f"💰 Balance: <b>{balance} ⭐</b>",
                        reply_markup=reply_markup
                    )
                else:
                    context.user_data['current_round_user_throws'] = []
                    context.user_data['current_round_bot_throws'] = []
                    
                    await update.message.reply_html(
                        f"{round_summary}\n\n"
                        f"{'─' * 20}\n\n"
                        f"{game_info['emoji']} <b>Round {game.current_round + 1}:</b> Send your {game.throw_count} {game_info['emoji']}!"
                    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount = update.message.successful_payment.total_amount
    
    user_balances[user_id] += amount
    
    await update.message.reply_html(
        f"✅ <b>Payment successful!</b>\n\n"
        f"💎 Added: <b>{amount} ⭐</b>\n"
        f"💰 New balance: <b>{user_balances[user_id]} ⭐</b>\n\n"
        f"🎮 Start playing with /dice, /bowl, /arrow, /football, or /basket!"
    )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("custom", custom_deposit))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("bowl", bowl_command))
    application.add_handler(CommandHandler("arrow", arrow_command))
    application.add_handler(CommandHandler("football", football_command))
    application.add_handler(CommandHandler("basket", basket_command))
    application.add_handler(CommandHandler("demo", demo_command))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_message))
    
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
