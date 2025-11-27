import logging
import random
import string
import re
import json
import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
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

# --- CONFIGURATION ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your actual tokens
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y")
PROVIDER_TOKEN = "" # Add your provider token if you have one, or leave blank for Stars only
ADMIN_ID = 5709159932

STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014
DATA_FILE = "bot_data.json"

# --- GAME DEFINITIONS ---
GAME_TYPES = {
    'dice': {'emoji': '🎲', 'name': 'Dice', 'max_value': 6, 'icon': '🎲'},
    'bowl': {'emoji': '🎳', 'name': 'Bowling', 'max_value': 6, 'icon': '🎳'},
    'arrow': {'emoji': '🎯', 'name': 'Darts', 'max_value': 6, 'icon': '🎯'},
    'football': {'emoji': '⚽', 'name': 'Football', 'max_value': 5, 'icon': '🥅'},
    'basket': {'emoji': '🏀', 'name': 'Basketball', 'max_value': 5, 'icon': '🏀'}
}

# --- RANKS SYSTEM (20 Levels based on wagered stars) ---
RANKS = [
    (0, "No Rank"), (100, "Novice"), (500, "Beginner"), (1000, "Amateur"),
    (2500, "Player"), (5000, "Gambler"), (10000, "Pro"), (25000, "Veteran"),
    (50000, "Elite"), (100000, "Master"), (250000, "Grandmaster"), (500000, "Legend"),
    (1000000, "Mythic"), (2500000, "Titan"), (5000000, "Demi-God"), (10000000, "God"),
    (25000000, "Supreme"), (50000000, "Universal"), (100000000, "Multiversal"), (500000000, "Omnipotent")
]

# --- DATA MANAGEMENT ---
users_data = {}
game_locks = defaultdict(asyncio.Lock)
user_games = {}
withdrawal_counter = 26356

def load_data():
    global users_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                users_data = json.load(f)
            # Convert string keys back to int where necessary (JSON keys are always strings)
            users_data = {int(k): v for k, v in users_data.items()}
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            users_data = {}
    else:
        users_data = {}

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def get_user_data(user_id):
    if user_id not in users_data:
        users_data[user_id] = {
            'balance': 0,
            'joined_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'total_games': 0,
            'total_wagered': 0,
            'total_won': 0, # Total winnings amount
            'biggest_win': 0,
            'game_counts': {k: 0 for k in GAME_TYPES.keys()},
            'history': [] # List of last 20 games
        }
        save_data()
    return users_data[user_id]

def get_rank_info(wagered_stars):
    current_level = 1
    current_rank = "No Rank"
    for i, (threshold, name) in enumerate(RANKS):
        if wagered_stars >= threshold:
            current_level = i + 1
            current_rank = name
        else:
            break
    return current_level, current_rank

# --- CLASS DEFINITIONS ---
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
        self.is_demo = False

# --- UTILS ---
def generate_transaction_id():
    chars = string.ascii_letters + string.digits
    return 'stx' + ''.join(random.choice(chars) for _ in range(80))

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id)
    
    balance_usd = u_data['balance'] * STARS_TO_USD
    turnover_usd = u_data['total_wagered'] * STARS_TO_USD
    
    welcome_text = (
        f"🐱 <b>Welcome to lenarao Game</b>\n\n"
        f"⭐️ Lenrao Game is the best online mini-games on Telegram\n\n"
        f"📢 <b>How to start winning?</b>\n"
        f"1. Make sure you have a balance. You can top up using the \"Deposit\" button.\n"
        f"2. Join one of our groups from the @lenrao catalog.\n"
        f"3. Click Play below and start playing!\n\n"
        f"💵 Balance: <b>${balance_usd:.2f}</b>\n"
        f"👑 Game turnover: <b>${turnover_usd:.2f}</b>\n\n"
        f"🌐 <b>About us</b>\n"
        f"Channel | Chat | Support"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play", callback_data="open_play_menu")],
        [InlineKeyboardButton("💰 Deposit", callback_data="deposit_custom"), InlineKeyboardButton("👤 Profile", callback_data="open_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_profile(update.effective_user.id, update, is_callback=False)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    history = u_data.get('history', [])
    
    if not history:
        await update.message.reply_html("📜 <b>Game History</b>\n\nNo games played yet!")
        return
        
    history_text = "📜 <b>Last 10 Games History:</b>\n\n"
    
    # Show last 10 games (reversed to show newest first)
    for game in reversed(history[-10:]):
        result_icon = "🟢" if game['result'] == 'win' else "🔴" if game['result'] == 'loss' else "⚪️"
        game_icon = GAME_TYPES.get(game['type'], {'icon': '🎮'})['icon']
        amount_str = f"+{game['amount']}" if game['result'] == 'win' else f"-{game['amount']}" if game['result'] == 'loss' else f"~{game['amount']}"
        
        history_text += (
            f"{result_icon} {game_icon} <b>{game['type'].title()}</b>\n"
            f"Result: {amount_str} ⭐ | Date: {game['date']}\n"
            f"─────────────────\n"
        )
    
    await update.message.reply_html(history_text)

async def show_profile(user_id, update_obj, is_callback=False):
    u_data = get_user_data(user_id)
    
    balance_usd = u_data['balance'] * STARS_TO_USD
    total_wagered_usd = u_data['total_wagered'] * STARS_TO_USD
    total_won_usd = u_data['total_won'] * STARS_TO_USD
    biggest_win_usd = u_data['biggest_win'] * STARS_TO_USD
    
    lvl, rank_name = get_rank_info(u_data['total_wagered'])
    
    # Determine favorite game
    game_counts = u_data.get('game_counts', {})
    fav_game_key = max(game_counts, key=game_counts.get) if any(game_counts.values()) else None
    fav_game = GAME_TYPES[fav_game_key]['name'] if fav_game_key else "?"
    
    profile_text = (
        f"📢 <b>Profile</b>\n\n"
        f"ℹ️ User ID: <code>{user_id}</code>\n"
        f"⬆️ Rank: <b>{rank_name} (Lvl {lvl})</b>\n"
        f"💵 Balance: <b>${balance_usd:.2f}</b> ({u_data['balance']} ⭐)\n\n"
        f"⚡️ Total games: <b>{u_data['total_games']}</b>\n"
        f"💸 Total bets: <b>${total_wagered_usd:.2f}</b>\n"
        f"🏆 Total wins: <b>${total_won_usd:.2f}</b>\n\n"
        f"🎲 Favorite game: <b>{fav_game}</b>\n"
        f"🎉 Biggest win: <b>${biggest_win_usd:.2f}</b>\n\n"
        f"🕒 Registration date: {u_data['joined_date']}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await update_obj.callback_query.edit_message_text(profile_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update_obj.message.reply_html(profile_text, reply_markup=reply_markup)

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("10 ⭐", callback_data="deposit_10"), InlineKeyboardButton("25 ⭐", callback_data="deposit_25")],
        [InlineKeyboardButton("50 ⭐", callback_data="deposit_50"), InlineKeyboardButton("100 ⭐", callback_data="deposit_100")],
        [InlineKeyboardButton("250 ⭐", callback_data="deposit_250"), InlineKeyboardButton("500 ⭐", callback_data="deposit_500")],
        [InlineKeyboardButton("💳 Custom Amount", callback_data="deposit_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html("💳 <b>Select deposit amount:</b>", reply_markup=reply_markup)

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['withdraw_state'] = None
    welcome_text = (
        "✨ <b>Welcome to Stars Withdrawal !</b>\n\n"
        "<b>Withdraw:</b>\n1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
        "<blockquote>⚙️ <b>Good to know:</b>\n• We send TON immediately minus fees.</blockquote>"
    )
    keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html("💳 Usage: /custom <amount>")
        return
    try:
        amount = int(context.args[0])
        await process_deposit_request(update, amount)
    except ValueError:
        await update.message.reply_html("❌ Invalid amount.")

async def process_deposit_request(update_obj, amount):
    if amount < 1 or amount > 2500:
        msg = "❌ Amount must be between 1 and 2500 ⭐"
        if hasattr(update_obj, 'callback_query'):
            await update_obj.callback_query.edit_message_text(msg)
        else:
            await update_obj.message.reply_html(msg)
        return

    title = f"Deposit {amount} Stars"
    description = f"Add {amount} ⭐ to your game balance"
    payload = f"deposit_{amount}_{update_obj.effective_user.id}"
    prices = [LabeledPrice("Stars", amount)]
    
    if hasattr(update_obj, 'callback_query'):
        await update_obj.callback_query.message.reply_invoice(
            title=title, description=description, payload=payload,
            provider_token=PROVIDER_TOKEN, currency="XTR", prices=prices
        )
    else:
        await update_obj.message.reply_invoice(
            title=title, description=description, payload=payload,
            provider_token=PROVIDER_TOKEN, currency="XTR", prices=prices
        )

# --- GAME HANDLERS ---
async def start_game_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎲 Dice", callback_data="game_menu_dice"), InlineKeyboardButton("🎳 Bowl", callback_data="game_menu_bowl")],
        [InlineKeyboardButton("🎯 Arrow", callback_data="game_menu_arrow"), InlineKeyboardButton("🥅 Football", callback_data="game_menu_football")],
        [InlineKeyboardButton("🏀 Basketball", callback_data="game_menu_basket")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🎮 <b>Choose a Game:</b>"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_html(text, reply_markup=reply_markup)

async def init_game_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    balance = u_data['balance']
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await update.callback_query.answer("❌ Finish active game first!", show_alert=True)
            return

        game_info = GAME_TYPES[game_type]
        keyboard = [
            [InlineKeyboardButton("10 ⭐", callback_data=f"bet_{game_type}_10"), InlineKeyboardButton("25 ⭐", callback_data=f"bet_{game_type}_25")],
            [InlineKeyboardButton("50 ⭐", callback_data=f"bet_{game_type}_50"), InlineKeyboardButton("100 ⭐", callback_data=f"bet_{game_type}_100")],
            [InlineKeyboardButton("🔙 Back", callback_data="open_play_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\nYour balance: <b>{balance} ⭐</b>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

# --- CALLBACK HANDLER ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    u_data = get_user_data(user_id) # Ensure data is loaded

    try:
        if data == "back_to_start":
            balance_usd = u_data['balance'] * STARS_TO_USD
            turnover_usd = u_data['total_wagered'] * STARS_TO_USD
            welcome_text = (
                f"🐱 <b>Welcome to lenarao Game</b>\n\n"
                f"⭐️ Lenrao Game is the best online mini-games on Telegram\n\n"
                f"📢 <b>How to start winning?</b>\n"
                f"1. Make sure you have a balance. You can top up using the \"Deposit\" button.\n"
                f"2. Join one of our groups from the @lenrao catalog.\n"
                f"3. Click Play below and start playing!\n\n"
                f"💵 Balance: <b>${balance_usd:.2f}</b>\n"
                f"👑 Game turnover: <b>${turnover_usd:.2f}</b>\n\n"
                f"🌐 <b>About us</b>\n"
                f"Channel | Chat | Support"
            )
            keyboard = [
                [InlineKeyboardButton("🎮 Play", callback_data="open_play_menu")],
                [InlineKeyboardButton("💰 Deposit", callback_data="deposit_custom"), InlineKeyboardButton("👤 Profile", callback_data="open_profile")]
            ]
            await query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
            return

        if data == "open_play_menu":
            await start_game_menu(update, context)
            return

        if data == "open_profile":
            await show_profile(user_id, update, is_callback=True)
            return

        if data.startswith("game_menu_"):
            game_type = data.split("_")[2]
            await init_game_setup(update, context, game_type)
            return

        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            await query.edit_message_text("💫 <b>Enter Stars to withdraw:</b>\nExample: 100", parse_mode=ParseMode.HTML)
            return

        if data == "confirm_withdraw":
            global withdrawal_counter
            amount = context.user_data.get('withdraw_amount', 0)
            address = context.user_data.get('withdraw_address', '')
            
            if u_data['balance'] < amount:
                await query.edit_message_text("❌ Insufficient balance!")
                return
            
            u_data['balance'] -= amount
            save_data()
            
            withdrawal_counter += 1
            ton_amount = round(amount * STARS_TO_TON, 8)
            tx_id = generate_transaction_id()
            
            receipt = (
                f"📄 <b>Withdrawal #{withdrawal_counter}</b>\n"
                f"⭐️ Stars: {amount}\n💎 TON: {ton_amount}\n"
                f"🏦 Address: <code>{address}</code>\n"
                f"🧾 TX ID: <code>{tx_id}</code>\n"
                f"⏳ Status: <b>On Hold (14 Days)</b>"
            )
            await query.edit_message_text(receipt, parse_mode=ParseMode.HTML)
            context.user_data['withdraw_state'] = None
            return

        if data == "cancel_withdraw":
            context.user_data['withdraw_state'] = None
            await query.edit_message_text("❌ Withdrawal cancelled.")
            return

        if data == "deposit_custom":
            await query.edit_message_text("💳 Please type the amount (e.g., <code>150</code>)", parse_mode=ParseMode.HTML)
            context.user_data['waiting_for_custom_amount'] = True
            return

        if data.startswith("deposit_"):
            amount = int(data.split("_")[1])
            await process_deposit_request(update, amount)
            return

        # --- GAME FLOW ---
        if data.startswith("bet_"):
            parts = data.split("_")
            game_type = parts[1]
            bet_amount = int(parts[2])
            
            if u_data['balance'] < bet_amount:
                await query.answer("❌ Insufficient balance!", show_alert=True)
                return
            
            context.user_data['bet_amount'] = bet_amount
            context.user_data['game_type'] = game_type
            context.user_data['is_demo'] = False
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [InlineKeyboardButton("1 Round", callback_data=f"rounds_{game_type}_1"), InlineKeyboardButton("2 Rounds", callback_data=f"rounds_{game_type}_2")],
                [InlineKeyboardButton("3 Rounds", callback_data=f"rounds_{game_type}_3")],
                [InlineKeyboardButton("Back ◀️", callback_data=f"game_menu_{game_type}")]
            ]
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select rounds:</b>\nBet: <b>{bet_amount} ⭐</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
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
            
            keyboard = [
                [InlineKeyboardButton(f"1 {game_info['emoji']}", callback_data=f"throws_{game_type}_1"),
                 InlineKeyboardButton(f"2 {game_info['emoji']}", callback_data=f"throws_{game_type}_2")],
                [InlineKeyboardButton(f"3 {game_info['emoji']}", callback_data=f"throws_{game_type}_3")],
                [InlineKeyboardButton("Back ◀️", callback_data=f"bet_{game_type}_{bet_amount}")]
            ]
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select throws:</b>\nBet: <b>{bet_amount} ⭐</b>\nRounds: <b>{rounds}</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
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

                if user_id in user_games:
                    del user_games[user_id]
                
                if not is_demo:
                    if u_data['balance'] < bet_amount:
                         await query.answer("❌ Insufficient balance!", show_alert=True)
                         return
                    u_data['balance'] -= bet_amount
                    # Update Total Wagered immediately on bet
                    u_data['total_wagered'] += bet_amount
                    save_data()

                game = Game(user_id, query.from_user.first_name, bet_amount, rounds, throw_count, game_type)
                game.is_demo = is_demo
                user_games[user_id] = game
                
                context.user_data['current_round_user_throws'] = []
                context.user_data['current_round_bot_throws'] = []
                
                game_info = GAME_TYPES[game_type]
                demo_txt = " [DEMO]" if is_demo else ""
                
                await query.edit_message_text(
                    f"🎮 <b>{game_info['name']} Started!{demo_txt}</b>\n\n"
                    f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                    f"🎯 Rounds: <b>{rounds}</b>\n"
                    f"{game_info['icon']} Throws: <b>{throw_count}</b>\n\n"
                    f"{game_info['emoji']} <b>Send your {game_info['emoji']} now!</b>",
                    parse_mode=ParseMode.HTML
                )
            return
            
        if data == "replay_same":
            # Logic for replay - simplifies flow
            if user_id in user_games: del user_games[user_id]
            # Need to re-trigger the betting/starting logic, but we need the params.
            # For simplicity, redirect to Game Menu
            await start_game_menu(update, context)
            return

    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.answer("❌ Error occurred", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""
    u_data = get_user_data(user_id)
    
    # Withdrawal Logic
    if context.user_data.get('withdraw_state') == 'waiting_amount':
        try:
            amount = int(text)
            if amount <= 0 or amount > u_data['balance']:
                await update.message.reply_html("❌ Invalid amount or insufficient balance.")
                return
            context.user_data['withdraw_amount'] = amount
            context.user_data['withdraw_state'] = 'waiting_address'
            await update.message.reply_html("📍 <b>Enter TON address:</b>")
        except ValueError:
            await update.message.reply_html("❌ Please enter a number.")
        return

    if context.user_data.get('withdraw_state') == 'waiting_address':
        context.user_data['withdraw_address'] = text
        amount = context.user_data.get('withdraw_amount')
        kb = [[InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]
        await update.message.reply_html(
            f"📝 <b>Confirm:</b>\nStars: {amount}\nAddr: {text}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.HTML
        )
        return

    # Custom Deposit
    if context.user_data.get('waiting_for_custom_amount'):
        try:
            amount = int(text)
            context.user_data['waiting_for_custom_amount'] = False
            await process_deposit_request(update, amount)
        except ValueError:
            await update.message.reply_html("❌ Invalid number.")
        return

    # GAME PLAY LOGIC
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
                    res_txt = "You win round! 🎉"
                elif bot_total > user_total:
                    game.bot_score += 1
                    res_txt = "Bot wins round! 🤖"
                else:
                    res_txt = "Tie! 🤝"
                
                await asyncio.sleep(1)
                
                if game.current_round >= game.total_rounds:
                    # GAME OVER
                    winnings = 0
                    result_status = "tie"
                    
                    if game.user_score > game.bot_score:
                        winnings = game.bet_amount * 2
                        if not game.is_demo:
                            u_data['balance'] += winnings
                            u_data['total_won'] += winnings  # Update total won amount
                            if winnings > u_data['biggest_win']:
                                u_data['biggest_win'] = winnings
                        final_msg = f"🎉 <b>YOU WIN!</b>\nWon: {winnings} ⭐"
                        result_status = "win"
                    elif game.bot_score > game.user_score:
                        final_msg = f"😢 <b>YOU LOST!</b>\nLost: {game.bet_amount} ⭐"
                        result_status = "loss"
                    else:
                        if not game.is_demo:
                            u_data['balance'] += game.bet_amount
                        final_msg = f"🤝 <b>TIE!</b>\nReturned: {game.bet_amount} ⭐"
                        result_status = "tie"
                    
                    # Update User Stats
                    if not game.is_demo:
                        u_data['total_games'] += 1
                        u_data['game_counts'][game.game_type] += 1
                        
                        # Add to History
                        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        history_entry = {
                            'type': game.game_type,
                            'result': result_status,
                            'bet': game.bet_amount,
                            'amount': winnings if result_status == 'win' else game.bet_amount if result_status == 'loss' else 0,
                            'date': date_str
                        }
                        u_data['history'].append(history_entry)
                        # Keep only last 20
                        if len(u_data['history']) > 20:
                            u_data['history'] = u_data['history'][-20:]
                            
                        save_data()

                    kb = [[InlineKeyboardButton("🔄 Play Again", callback_data="open_play_menu")]]
                    await update.message.reply_html(final_msg, reply_markup=InlineKeyboardMarkup(kb))
                    del user_games[user_id]
                else:
                    # Next Round
                    context.user_data['current_round_user_throws'] = []
                    context.user_data['current_round_bot_throws'] = []
                    await update.message.reply_html(
                        f"📊 <b>Round {game.current_round} Result:</b>\nYou: {user_total} | Bot: {bot_total}\n{res_txt}\n\n"
                        f"Score: You {game.user_score} - {game.bot_score} Bot\n"
                        f"⬇️ <b>Start Round {game.current_round + 1}:</b> Send {game.throw_count} emojis!"
                    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount = update.message.successful_payment.total_amount
    u_data = get_user_data(user_id)
    u_data['balance'] += amount
    save_data()
    await update.message.reply_html(f"✅ <b>Deposit Successful!</b>\nAdded: {amount} ⭐")

def main():
    load_data()
    application = Application.builder().token(BOT_TOKEN).build()
    
    app_add = application.add_handler
    app_add(CommandHandler("start", start))
    app_add(CommandHandler("play", start_game_menu)) # Alias
    app_add(CommandHandler("profile", profile_command))
    app_add(CommandHandler("history", history_command))
    app_add(CommandHandler("deposit", deposit_command))
    app_add(CommandHandler("custom", custom_deposit))
    app_add(CommandHandler("withdraw", withdraw_command))
    
    # Game shortcuts
    for g in GAME_TYPES:
        app_add(CommandHandler(g, lambda u, c, t=g: init_game_setup(u, c, t)))

    app_add(CallbackQueryHandler(button_callback))
    app_add(PreCheckoutQueryHandler(precheckout_callback))
    app_add(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_add(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_add(MessageHandler(filters.Dice.ALL, handle_message))
    
    logger.info("Bot started.")
    application.run_polling()

if __name__ == '__main__':
    main()
