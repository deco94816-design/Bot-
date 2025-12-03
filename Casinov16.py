import logging
import random
import string
import re
import json
import os
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
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError
from collections import defaultdict
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y"
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
PROVIDER_TOKEN = ""
ADMIN_ID = 5709159932

# Bot username for bonus check
BOT_USERNAME = "Iibrate"

# Data file path
DATA_FILE = "bot_data.json"

# Admin management
admin_list = {ADMIN_ID}
ADMIN_BALANCE = 9999999999

user_games = {}
user_balances = defaultdict(float)
game_locks = defaultdict(asyncio.Lock)
user_withdrawals = {}
withdrawal_counter = 26356

user_profiles = {}
user_game_history = defaultdict(list)

# Track users who have claimed bonus
user_bonus_claimed = set()

# Track last game settings for repeat/double feature
user_last_game_settings = {}

# Username to user_id mapping
username_to_id = {}

STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014
MIN_WITHDRAWAL = 200
BONUS_AMOUNT = 20

GAME_TYPES = {
    'dice': {'emoji': '🎲', 'name': 'Dice', 'max_value': 6, 'icon': '🎲'},
    'bowl': {'emoji': '🎳', 'name': 'Bowling', 'max_value': 6, 'icon': '🎳'},
    'arrow': {'emoji': '🎯', 'name': 'Darts', 'max_value': 6, 'icon': '🎯'},
    'football': {'emoji': '⚽', 'name': 'Football', 'max_value': 5, 'icon': '🥅'},
    'basket': {'emoji': '🏀', 'name': 'Basketball', 'max_value': 5, 'icon': '🏀'}
}

RANKS = {
    1: {"name": "Newcomer", "xp_required": 0, "emoji": "🌱"},
    2: {"name": "Beginner", "xp_required": 100, "emoji": "🌿"},
    3: {"name": "Amateur", "xp_required": 300, "emoji": "🌾"},
    4: {"name": "Player", "xp_required": 600, "emoji": "⭐"},
    5: {"name": "Regular", "xp_required": 1000, "emoji": "🌟"},
    6: {"name": "Enthusiast", "xp_required": 1500, "emoji": "✨"},
    7: {"name": "Skilled", "xp_required": 2200, "emoji": "💫"},
    8: {"name": "Expert", "xp_required": 3000, "emoji": "🔥"},
    9: {"name": "Veteran", "xp_required": 4000, "emoji": "💎"},
    10: {"name": "Master", "xp_required": 5200, "emoji": "👑"},
    11: {"name": "Grand Master", "xp_required": 6500, "emoji": "🏆"},
    12: {"name": "Champion", "xp_required": 8000, "emoji": "🥇"},
    13: {"name": "Elite", "xp_required": 10000, "emoji": "💠"},
    14: {"name": "Pro", "xp_required": 12500, "emoji": "🎖"},
    15: {"name": "Star", "xp_required": 15500, "emoji": "⚡"},
    16: {"name": "Superstar", "xp_required": 19000, "emoji": "🌠"},
    17: {"name": "Legend", "xp_required": 23000, "emoji": "🔱"},
    18: {"name": "Mythic", "xp_required": 28000, "emoji": "🐉"},
    19: {"name": "Immortal", "xp_required": 35000, "emoji": "👼"},
    20: {"name": "God", "xp_required": 50000, "emoji": "🌌"}
}


# ==================== JSON DATA PERSISTENCE ====================

def save_data():
    """Save all data to JSON file"""
    try:
        data = {
            'user_balances': dict(user_balances),
            'user_profiles': {},
            'user_game_history': {},
            'user_bonus_claimed': list(user_bonus_claimed),
            'user_withdrawals': user_withdrawals,
            'withdrawal_counter': withdrawal_counter,
            'admin_list': list(admin_list),
            'username_to_id': username_to_id,
            'user_last_game_settings': user_last_game_settings
        }
        
        # Convert user_profiles with proper serialization
        for user_id, profile in user_profiles.items():
            profile_copy = dict(profile)
            if 'registration_date' in profile_copy:
                profile_copy['registration_date'] = profile_copy['registration_date'].isoformat()
            if 'game_counts' in profile_copy:
                profile_copy['game_counts'] = dict(profile_copy['game_counts'])
            data['user_profiles'][str(user_id)] = profile_copy
        
        # Convert user_game_history with proper serialization
        for user_id, history in user_game_history.items():
            serialized_history = []
            for game in history:
                game_copy = dict(game)
                if 'timestamp' in game_copy:
                    game_copy['timestamp'] = game_copy['timestamp'].isoformat()
                serialized_history.append(game_copy)
            data['user_game_history'][str(user_id)] = serialized_history
        
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Error saving data: {e}")


def load_data():
    """Load all data from JSON file"""
    global user_balances, user_profiles, user_game_history, user_bonus_claimed
    global user_withdrawals, withdrawal_counter, admin_list, username_to_id, user_last_game_settings
    
    try:
        if not os.path.exists(DATA_FILE):
            logger.info("No data file found, starting fresh")
            return
        
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        # Load user balances
        user_balances.update({int(k): float(v) for k, v in data.get('user_balances', {}).items()})
        
        # Load user profiles
        for user_id_str, profile in data.get('user_profiles', {}).items():
            user_id = int(user_id_str)
            if 'registration_date' in profile:
                profile['registration_date'] = datetime.fromisoformat(profile['registration_date'])
            if 'game_counts' in profile:
                profile['game_counts'] = defaultdict(int, profile['game_counts'])
            user_profiles[user_id] = profile
        
        # Load user game history
        for user_id_str, history in data.get('user_game_history', {}).items():
            user_id = int(user_id_str)
            deserialized_history = []
            for game in history:
                if 'timestamp' in game:
                    game['timestamp'] = datetime.fromisoformat(game['timestamp'])
                deserialized_history.append(game)
            user_game_history[user_id] = deserialized_history
        
        # Load other data
        user_bonus_claimed.update(set(data.get('user_bonus_claimed', [])))
        user_withdrawals.update(data.get('user_withdrawals', {}))
        withdrawal_counter = data.get('withdrawal_counter', 26356)
        admin_list.update(set(data.get('admin_list', [ADMIN_ID])))
        username_to_id.update(data.get('username_to_id', {}))
        user_last_game_settings.update({int(k): v for k, v in data.get('user_last_game_settings', {}).items()})
        
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Error loading data: {e}")


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
        self.bot_first = False
        self.bot_rolled_this_round = False
        self.user_throws_this_round = 0


def is_admin(user_id):
    return user_id in admin_list


def get_user_balance(user_id):
    if is_admin(user_id):
        return ADMIN_BALANCE
    return user_balances[user_id]


def set_user_balance(user_id, amount):
    if not is_admin(user_id):
        user_balances[user_id] = amount
        save_data()


def adjust_user_balance(user_id, amount):
    if not is_admin(user_id):
        user_balances[user_id] += amount
        save_data()


def get_user_link(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def get_or_create_profile(user_id, username=None):
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            'user_id': user_id,
            'username': username or 'Unknown',
            'registration_date': datetime.now(),
            'xp': 0,
            'total_games': 0,
            'total_bets': 0.0,
            'total_wins': 0.0,
            'total_losses': 0.0,
            'games_won': 0,
            'games_lost': 0,
            'favorite_game': None,
            'biggest_win': 0.0,
            'game_counts': defaultdict(int)
        }
        save_data()
    
    # Update username mapping
    if username:
        username_lower = username.lower().lstrip('@')
        username_to_id[username_lower] = user_id
        save_data()
    
    return user_profiles[user_id]


def get_user_rank(xp):
    current_rank = 1
    for level, data in RANKS.items():
        if xp >= data['xp_required']:
            current_rank = level
        else:
            break
    return current_rank


def get_rank_info(level):
    return RANKS.get(level, RANKS[1])


def add_xp(user_id, amount):
    profile = get_or_create_profile(user_id)
    profile['xp'] += amount
    save_data()
    return profile['xp']


def update_game_stats(user_id, game_type, bet_amount, win_amount, won):
    profile = get_or_create_profile(user_id)
    profile['total_games'] += 1
    profile['total_bets'] += bet_amount
    
    if won:
        profile['games_won'] += 1
        profile['total_wins'] += win_amount
        if win_amount > profile['biggest_win']:
            profile['biggest_win'] = win_amount
        add_xp(user_id, int(bet_amount * 2) + 50)
    else:
        profile['games_lost'] += 1
        profile['total_losses'] += bet_amount
        add_xp(user_id, int(bet_amount * 0.5) + 10)
    
    profile['game_counts'][game_type] += 1
    
    max_count = 0
    fav_game = None
    for gt, count in profile['game_counts'].items():
        if count > max_count:
            max_count = count
            fav_game = gt
    profile['favorite_game'] = fav_game
    
    user_game_history[user_id].append({
        'game_type': game_type,
        'bet_amount': bet_amount,
        'win_amount': win_amount if won else 0,
        'won': won,
        'timestamp': datetime.now()
    })
    
    save_data()


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


def check_bot_name_in_profile(user) -> bool:
    first_name = (user.first_name or "").lower()
    last_name = (user.last_name or "").lower()
    bot_name_lower = BOT_USERNAME.lower()
    return bot_name_lower in first_name or bot_name_lower in last_name


def is_private_chat(update: Update) -> bool:
    return update.effective_chat.type == "private"


def save_last_game_settings(user_id, game_type, bet_amount, rounds, throws, bot_first):
    """Save user's last game settings for repeat/double feature"""
    user_last_game_settings[user_id] = {
        'game_type': game_type,
        'bet_amount': bet_amount,
        'rounds': rounds,
        'throws': throws,
        'bot_first': bot_first
    }
    save_data()


def get_user_id_by_username(username):
    """Get user_id from username"""
    username_lower = username.lower().lstrip('@')
    return username_to_id.get(username_lower)


# ==================== ERROR HANDLING DECORATOR ====================

def handle_errors(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except BadRequest as e:
            logger.error(f"BadRequest in {func.__name__}: {e}")
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Request Error</b>\n\n"
                        "Something went wrong with your request. Please try again."
                    )
            except Exception:
                pass
        except Forbidden as e:
            logger.error(f"Forbidden in {func.__name__}: {e}")
        except NetworkError as e:
            logger.error(f"NetworkError in {func.__name__}: {e}")
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Network Error</b>\n\n"
                        "Connection issue. Please try again later."
                    )
            except Exception:
                pass
        except TelegramError as e:
            logger.error(f"TelegramError in {func.__name__}: {e}")
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Error</b>\n\n"
                        "An error occurred. Please try again."
                    )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            try:
                if update.message:
                    await update.message.reply_html(
                        "❌ <b>Unexpected Error</b>\n\n"
                        "Something went wrong. Please try again later."
                    )
            except Exception:
                pass
    return wrapper


# ==================== BONUS COMMAND ====================

@handle_errors
async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id in user_bonus_claimed:
        await update.message.reply_html(
            "❌ <b>Bonus Already Claimed!</b>\n\n"
            "You have already claimed your profile bonus.\n"
            "This bonus can only be claimed once."
        )
        return
    
    if check_bot_name_in_profile(user):
        adjust_user_balance(user_id, BONUS_AMOUNT)
        user_bonus_claimed.add(user_id)
        save_data()
        
        balance = get_user_balance(user_id)
        balance_usd = balance * STARS_TO_USD
        
        await update.message.reply_html(
            f"🎁 <b>Bonus Claimed Successfully!</b>\n\n"
            f"✅ We found <b>'{BOT_USERNAME}'</b> in your profile name!\n\n"
            f"💰 You received: <b>{BONUS_AMOUNT} ⭐</b>\n"
            f"💵 New Balance: <b>{balance:,} ⭐</b> (${balance_usd:.2f})\n\n"
            f"🎉 Thank you for supporting us!"
        )
        
        logger.info(f"Bonus claimed by user {user_id} ({user.first_name})")
    else:
        await update.message.reply_html(
            f"❌ <b>Bonus Not Available</b>\n\n"
            f"To claim your <b>{BONUS_AMOUNT} ⭐</b> bonus, please add "
            f"<b>'{BOT_USERNAME}'</b> to your Telegram profile name.\n\n"
            f"📝 <b>How to claim:</b>\n"
            f"1️⃣ Go to Telegram Settings\n"
            f"2️⃣ Edit your profile\n"
            f"3️⃣ Add <b>'{BOT_USERNAME}'</b> to your First Name or Last Name\n"
            f"4️⃣ Come back and use /bonus again\n\n"
            f"💡 Example: \"John {BOT_USERNAME}\" or \"{BOT_USERNAME} Smith\""
        )


# ==================== ADMIN COMMANDS ====================

@handle_errors
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "👑 <b>Add Admin</b>\n\n"
            "Usage: /addadmin <user_id>\n"
            "Example: /addadmin 123456789\n\n"
            f"Current admins: {len(admin_list)}"
        )
        return
    
    try:
        new_admin_id = int(context.args[0])
        
        if new_admin_id in admin_list:
            await update.message.reply_html(f"⚠️ User <code>{new_admin_id}</code> is already an admin!")
            return
        
        admin_list.add(new_admin_id)
        user_balances[new_admin_id] = ADMIN_BALANCE
        save_data()
        
        await update.message.reply_html(
            f"✅ <b>New admin added successfully!</b>\n\n"
            f"👤 User ID: <code>{new_admin_id}</code>\n"
            f"💰 Balance: <b>{ADMIN_BALANCE:,} ⭐</b>\n"
            f"👑 Total admins: {len(admin_list)}"
        )
        
        logger.info(f"Admin {user_id} added new admin: {new_admin_id}")
        
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID! Please enter a valid number.")


@handle_errors
async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "👑 <b>Remove Admin</b>\n\n"
            "Usage: /removeadmin <user_id>\n"
            "Example: /removeadmin 123456789"
        )
        return
    
    try:
        remove_admin_id = int(context.args[0])
        
        if remove_admin_id == ADMIN_ID:
            await update.message.reply_html("❌ Cannot remove the main admin!")
            return
        
        if remove_admin_id not in admin_list:
            await update.message.reply_html(f"⚠️ User <code>{remove_admin_id}</code> is not an admin!")
            return
        
        admin_list.remove(remove_admin_id)
        save_data()
        
        await update.message.reply_html(
            f"✅ <b>Admin removed successfully!</b>\n\n"
            f"👤 User ID: <code>{remove_admin_id}</code>\n"
            f"👑 Remaining admins: {len(admin_list)}"
        )
        
        logger.info(f"Admin {user_id} removed admin: {remove_admin_id}")
        
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID! Please enter a valid number.")


@handle_errors
async def listadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    admin_text = "👑 <b>Admin List</b>\n\n"
    admin_text += f"Total admins: {len(admin_list)}\n\n"
    
    for idx, admin_id in enumerate(admin_list, 1):
        is_main = " (Main Admin)" if admin_id == ADMIN_ID else ""
        admin_text += f"{idx}. <code>{admin_id}</code>{is_main}\n"
    
    await update.message.reply_html(admin_text)


@handle_errors
async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    
    # Check if using /tip amount @username format
    if context.args and len(context.args) >= 2:
        try:
            tip_amount = int(context.args[0])
            target = context.args[1]
            
            if tip_amount < 1:
                await message.reply_html("❌ Tip amount must be at least 1 ⭐")
                return
            
            # Check if target is a username
            if target.startswith('@'):
                username = target.lstrip('@')
                recipient_id = get_user_id_by_username(username)
                
                if not recipient_id:
                    await message.reply_html(
                        f"❌ <b>User not found!</b>\n\n"
                        f"User @{username} has not interacted with the bot yet.\n"
                        f"They need to use the bot at least once before receiving tips."
                    )
                    return
                
                recipient_profile = user_profiles.get(recipient_id, {})
                recipient_name = recipient_profile.get('username', username)
            else:
                # Try to parse as user_id
                try:
                    recipient_id = int(target)
                    recipient_profile = user_profiles.get(recipient_id, {})
                    recipient_name = recipient_profile.get('username', 'User')
                except ValueError:
                    await message.reply_html("❌ Invalid user! Use @username or user ID.")
                    return
            
            if recipient_id == user_id:
                await message.reply_html("❌ You can't tip yourself!")
                return
            
            sender_balance = get_user_balance(user_id)
            if sender_balance < tip_amount:
                await message.reply_html(
                    f"❌ <b>Insufficient balance!</b>\n\n"
                    f"Your balance: {sender_balance} ⭐\n"
                    f"Tip amount: {tip_amount} ⭐"
                )
                return
            
            if not is_admin(user_id):
                user_balances[user_id] -= tip_amount
            
            adjust_user_balance(recipient_id, tip_amount)
            
            tip_usd = tip_amount * STARS_TO_USD
            sender_name = message.from_user.first_name
            
            sender_link = get_user_link(user_id, sender_name)
            recipient_link = get_user_link(recipient_id, recipient_name)
            
            await message.reply_html(
                f"💝 <b>Tip sent successfully!</b>\n\n"
                f"👤 From: {sender_link}\n"
                f"👤 To: {recipient_link}\n"
                f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
                f"🎉 Thank you for your generosity!"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=recipient_id,
                    text=(
                        f"🎁 <b>You received a tip!</b>\n\n"
                        f"👤 From: {sender_link}\n"
                        f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
                        f"💵 Your new balance: <b>{get_user_balance(recipient_id)} ⭐</b>"
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.warning(f"Could not notify recipient {recipient_id}: {e}")
            
            logger.info(f"Tip: {user_id} ({sender_name}) -> {recipient_id} ({recipient_name}): {tip_amount} stars")
            return
            
        except ValueError:
            pass  # Fall through to reply-based tip
    
    # Reply-based tip
    if not message.reply_to_message:
        await message.reply_html(
            "💝 <b>Tip Command</b>\n\n"
            "<b>Method 1:</b> Reply to a user's message:\n"
            "/tip <amount>\n\n"
            "<b>Method 2:</b> Tip by username:\n"
            "/tip <amount> @username\n\n"
            "<b>Examples:</b>\n"
            "• /tip 100 (reply to message)\n"
            "• /tip 100 @username\n"
            "• /tip 50 @JohnDoe\n\n"
            "This will send stars from your balance to the user."
        )
        return
    
    if not context.args or len(context.args) == 0:
        await message.reply_html("❌ Please specify the amount to tip!\nExample: /tip 100")
        return
    
    try:
        tip_amount = int(context.args[0])
        
        if tip_amount < 1:
            await message.reply_html("❌ Tip amount must be at least 1 ⭐")
            return
        
        recipient_id = message.reply_to_message.from_user.id
        recipient_name = message.reply_to_message.from_user.first_name
        sender_name = message.from_user.first_name
        
        # Update username mapping for recipient
        if message.reply_to_message.from_user.username:
            username_to_id[message.reply_to_message.from_user.username.lower()] = recipient_id
            save_data()
        
        if recipient_id == user_id:
            await message.reply_html("❌ You can't tip yourself!")
            return
        
        sender_balance = get_user_balance(user_id)
        if sender_balance < tip_amount:
            await message.reply_html(
                f"❌ <b>Insufficient balance!</b>\n\n"
                f"Your balance: {sender_balance} ⭐\n"
                f"Tip amount: {tip_amount} ⭐"
            )
            return
        
        if not is_admin(user_id):
            user_balances[user_id] -= tip_amount
        
        adjust_user_balance(recipient_id, tip_amount)
        get_or_create_profile(recipient_id, recipient_name)
        
        tip_usd = tip_amount * STARS_TO_USD
        
        sender_link = get_user_link(user_id, sender_name)
        recipient_link = get_user_link(recipient_id, recipient_name)
        
        await message.reply_html(
            f"💝 <b>Tip sent successfully!</b>\n\n"
            f"👤 From: {sender_link}\n"
            f"👤 To: {recipient_link}\n"
            f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
            f"🎉 Thank you for your generosity!"
        )
        
        try:
            await context.bot.send_message(
                chat_id=recipient_id,
                text=(
                    f"🎁 <b>You received a tip!</b>\n\n"
                    f"👤 From: {sender_link}\n"
                    f"💰 Amount: <b>{tip_amount} ⭐</b> (${tip_usd:.2f})\n\n"
                    f"💵 Your new balance: <b>{get_user_balance(recipient_id)} ⭐</b>"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Could not notify recipient {recipient_id}: {e}")
        
        logger.info(f"Tip: {user_id} ({sender_name}) -> {recipient_id} ({recipient_name}): {tip_amount} stars")
        
    except ValueError:
        await message.reply_html("❌ Invalid amount! Please enter a number.")


@handle_errors
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    get_or_create_profile(user_id, user.username or user.first_name)
    
    # Update username mapping
    if user.username:
        username_to_id[user.username.lower()] = user_id
        save_data()
    
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    profile = user_profiles.get(user_id, {})
    turnover = profile.get('total_bets', 0.0) * STARS_TO_USD
    
    admin_badge = " 👑" if is_admin(user_id) else ""
    
    welcome_text = (
        f"🐱 <b>Welcome to Iibrate Game{admin_badge}</b>\n\n"
        f"⭐️ Iibrate Game is the best online mini-games on Telegram\n\n"
        f"📢 <b>How to start winning?</b>\n\n"
        f"1. Make sure you have a balance. You can top up using the \"Deposit\" button.\n\n"
        f"2. Join one of our groups from the @Iibrate catalog.\n\n"
        f"3. Type /play and start playing!\n\n\n"
        f"💵 Balance: ${balance_usd:.2f}\n"
        f"👑 Game turnover: ${turnover:.2f}\n\n"
        f"🌐 <b>About us</b>\n"
        f"<a href='https://t.me/Iibrate'>Channel</a> | <a href='https://t.me/Iibrates'>Chat</a> | <a href='https://t.me/Iibratesupport'>Support</a>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play", callback_data="show_games")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup, disable_web_page_preview=True)


@handle_errors
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_or_create_profile(user_id, update.effective_user.username or update.effective_user.first_name)
    
    keyboard = [
        [
            InlineKeyboardButton("🎲 Dice", callback_data="play_game_dice"),
            InlineKeyboardButton("🎳 Bowling", callback_data="play_game_bowl"),
        ],
        [
            InlineKeyboardButton("🎯 Darts", callback_data="play_game_arrow"),
            InlineKeyboardButton("⚽ Football", callback_data="play_game_football"),
        ],
        [
            InlineKeyboardButton("🏀 Basketball", callback_data="play_game_basket"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "🎮 <b>Select a game to play:</b>\n\n"
        "🎲 <b>Dice</b> - Roll the dice and beat the bot!\n"
        "🎳 <b>Bowling</b> - Strike your way to victory!\n"
        "🎯 <b>Darts</b> - Aim for the bullseye!\n"
        "⚽ <b>Football</b> - Score goals and win!\n"
        "🏀 <b>Basketball</b> - Shoot hoops for stars!",
        reply_markup=reply_markup
    )


@handle_errors
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    rank_level = get_user_rank(profile['xp'])
    rank_info = get_rank_info(rank_level)
    
    admin_badge = " 👑" if is_admin(user_id) else ""
    user_link = get_user_link(user_id, user.first_name)
    
    if rank_level < 20:
        next_rank_info = get_rank_info(rank_level + 1)
        xp_progress = profile['xp'] - rank_info['xp_required']
        xp_needed = next_rank_info['xp_required'] - rank_info['xp_required']
        progress_bar = create_progress_bar(xp_progress, xp_needed)
        rank_display = f"{rank_info['emoji']} {rank_info['name']} (Lvl {rank_level})\n{progress_bar} {profile['xp']}/{next_rank_info['xp_required']} XP"
    else:
        rank_display = f"{rank_info['emoji']} {rank_info['name']} (MAX LEVEL)\n🌌 {profile['xp']} XP"
    
    fav_game = profile.get('favorite_game')
    if fav_game and fav_game in GAME_TYPES:
        fav_game_display = f"{GAME_TYPES[fav_game]['icon']} {GAME_TYPES[fav_game]['name']}"
    else:
        fav_game_display = "?"
    
    biggest_win = profile.get('biggest_win', 0)
    if biggest_win > 0:
        biggest_win_display = f"${biggest_win * STARS_TO_USD:.2f}"
    else:
        biggest_win_display = "?"
    
    reg_date = profile.get('registration_date', datetime.now())
    reg_date_str = reg_date.strftime("%Y-%m-%d %H:%M")
    
    total_bets_usd = profile.get('total_bets', 0) * STARS_TO_USD
    total_wins_usd = profile.get('total_wins', 0) * STARS_TO_USD
    
    profile_text = (
        f"📢 <b>Profile{admin_badge}</b>\n\n"
        f"👤 User: {user_link}\n"
        f"ℹ️ User ID: <code>{user_id}</code>\n"
        f"⬆️ Rank: {rank_display}\n"
        f"💵 Balance: ${balance_usd:.2f}\n\n"
        f"⚡️ Total games: {profile.get('total_games', 0)}\n"
        f"Total bets: ${total_bets_usd:.2f}\n"
        f"Total wins: ${total_wins_usd:.2f}\n\n"
        f"🎲 Favorite game: {fav_game_display}\n"
        f"🎉 Biggest win: {biggest_win_display}\n\n"
        f"🕒 Registration date: {reg_date_str}"
    )
    
    await update.message.reply_html(profile_text)


def create_progress_bar(current, total, length=10):
    if total == 0:
        filled = 0
    else:
        filled = int((current / total) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty


@handle_errors
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    history = user_game_history.get(user_id, [])
    
    total_games = profile.get('total_games', 0)
    total_bets = profile.get('total_bets', 0)
    total_wins = profile.get('total_wins', 0)
    total_losses = profile.get('total_losses', 0)
    games_won = profile.get('games_won', 0)
    games_lost = profile.get('games_lost', 0)
    
    total_wagered = total_bets
    net_profit = total_wins - total_losses
    
    total_bets_usd = total_bets * STARS_TO_USD
    total_wins_usd = total_wins * STARS_TO_USD
    total_losses_usd = total_losses * STARS_TO_USD
    total_wagered_usd = total_wagered * STARS_TO_USD
    net_profit_usd = net_profit * STARS_TO_USD
    
    if total_games > 0:
        win_rate = (games_won / total_games) * 100
    else:
        win_rate = 0
    
    history_text = (
        f"📊 <b>Game History</b>\n\n"
        f"🎮 <b>Total Games Played:</b> {total_games}\n"
        f"✅ Games Won: {games_won}\n"
        f"❌ Games Lost: {games_lost}\n"
        f"📈 Win Rate: {win_rate:.1f}%\n\n"
        f"💰 <b>Financial Summary:</b>\n"
        f"💵 Total Bets: ${total_bets_usd:.2f}\n"
        f"🏆 Total Wins: ${total_wins_usd:.2f}\n"
        f"📉 Total Losses: ${total_losses_usd:.2f}\n"
        f"🔄 Total Wagered: ${total_wagered_usd:.2f}\n"
        f"{'📈' if net_profit >= 0 else '📉'} Net Profit: ${net_profit_usd:.2f}\n"
    )
    
    if history:
        history_text += "\n📜 <b>Recent Games:</b>\n"
        recent_games = history[-5:]
        for game in reversed(recent_games):
            game_type = game['game_type']
            game_info = GAME_TYPES.get(game_type, {'icon': '🎮', 'name': 'Unknown'})
            status = "✅ Won" if game['won'] else "❌ Lost"
            bet_usd = game['bet_amount'] * STARS_TO_USD
            timestamp = game['timestamp'].strftime("%m/%d %H:%M")
            history_text += f"{game_info['icon']} {game_info['name']} - {status} (${bet_usd:.2f}) - {timestamp}\n"
    
    await update.message.reply_html(history_text)


@handle_errors
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    help_text = (
        "🎯 <b>How to Play:</b>\n\n"
        "1️⃣ Deposit Stars using /deposit or /depo\n"
        "2️⃣ Choose a game (/dice, /bowl, /arrow, /football, /basket)\n"
        "3️⃣ Select bet amount or use shortcuts:\n"
        "   • /dice 100 - Bet 100 stars\n"
        "   • /dice all - Bet entire balance\n"
        "   • /dice half - Bet half balance\n"
        "4️⃣ Choose rounds (1-3)\n"
        "5️⃣ Choose throws (1-3)\n"
        "6️⃣ Optionally let bot roll first\n"
        "7️⃣ Send your emojis!\n"
        "8️⃣ Higher total wins!\n\n"
        "🏆 Most rounds won = Winner!\n"
        "💎 Winner takes the pot!\n\n"
        "💝 <b>Tip Users:</b>\n"
        "• Reply to a message: /tip <amount>\n"
        "• By username: /tip <amount> @username\n\n"
        f"🎁 <b>Bonus:</b>\n"
        f"Add '{BOT_USERNAME}' to your profile name and use /bonus to get {BONUS_AMOUNT} ⭐!\n\n"
        "📝 <b>Command Aliases:</b>\n"
        "• /bal = /balance\n"
        "• /depo = /deposit\n\n"
    )
    
    if is_admin(user_id):
        help_text += (
            "👑 <b>Admin Commands:</b>\n"
            "/addadmin - Add new admin\n"
            "/removeadmin - Remove admin\n"
            "/listadmins - View all admins\n"
            "/demo - Test games without betting\n"
        )
    
    await update.message.reply_html(help_text)


@handle_errors
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    admin_note = " (Admin - Unlimited)" if is_admin(user_id) else ""
    
    keyboard = [
        [
            InlineKeyboardButton("💳 Deposit", callback_data="balance_deposit"),
            InlineKeyboardButton("💎 Withdraw", callback_data="balance_withdraw"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"💰 <b>Your Balance</b>{admin_note}\n\n"
        f"⭐ Stars: <b>{balance:,} ⭐</b>\n"
        f"💵 USD: <b>${balance_usd:.2f}</b>",
        reply_markup=reply_markup
    )


@handle_errors
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


@handle_errors
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_private_chat(update):
        bot_info = await context.bot.get_me()
        await update.message.reply_html(
            "🔒 <b>Private Command Only</b>\n\n"
            "For your security, the /withdraw command can only be used in a private chat with the bot.\n\n"
            f"👉 <a href='https://t.me/{bot_info.username}?start=withdraw'>Click here to open DM</a>\n\n"
            "Or search for @{} and start a private conversation.".format(bot_info.username)
        )
        return
    
    context.user_data['withdraw_state'] = None
    context.user_data['withdraw_amount'] = None
    context.user_data['withdraw_address'] = None
    
    welcome_text = (
        "✨ <b>Welcome to Stars Withdrawal!</b>\n\n"
        "<b>Withdraw:</b>\n"
        "1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
        f"<b>Minimum withdrawal: {MIN_WITHDRAWAL} ⭐</b>\n\n"
        "<blockquote>⚙️ <b>Good to know:</b>\n"
        "• When you exchange stars through a channel or bot, Telegram keeps a 15% fee and applies a 21-day hold.\n"
        "• We send TON immediately—factoring in this fee and a small service premium.</blockquote>"
    )
    
    keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)


@handle_errors
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


async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    user_id = update.effective_user.id
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await update.message.reply_html(
                "❌ You already have an active game! Finish it first."
            )
            return
        
        balance = get_user_balance(user_id)
        
        bet_amount = None
        if context.args and len(context.args) > 0:
            arg = context.args[0].lower()
            if arg == 'all':
                bet_amount = int(balance)
            elif arg == 'half':
                bet_amount = int(balance / 2)
            else:
                try:
                    bet_amount = int(arg)
                except ValueError:
                    await update.message.reply_html("❌ Invalid bet amount! Use a number, 'all', or 'half'.")
                    return
            
            if bet_amount < 1:
                await update.message.reply_html("❌ Bet amount must be at least 1 ⭐")
                return
            
            if bet_amount > balance and not is_admin(user_id):
                await update.message.reply_html(
                    f"❌ Insufficient balance!\n"
                    f"Your balance: <b>{balance} ⭐</b>\n"
                    f"Bet amount: <b>{bet_amount} ⭐</b>"
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
                    InlineKeyboardButton("Cancel ❌", callback_data="cancel_game"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_html(
                f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                f"💰 Bet: <b>{bet_amount} ⭐</b>\n\n"
                f"Select number of rounds:",
                reply_markup=reply_markup
            )
            return
        
        if balance < 1 and not is_admin(user_id):
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
            f"Your balance: <b>{balance:,} ⭐</b>",
            reply_markup=reply_markup
        )


async def start_game_from_callback(query, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    user_id = query.from_user.id
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await query.edit_message_text(
                "❌ You already have an active game! Finish it first.",
                parse_mode=ParseMode.HTML
            )
            return
        
        balance = get_user_balance(user_id)
        
        if balance < 1 and not is_admin(user_id):
            await query.edit_message_text(
                "❌ Insufficient balance! Use /deposit to add Stars.\n"
                f"Your balance: <b>{balance} ⭐</b>",
                parse_mode=ParseMode.HTML
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
                InlineKeyboardButton("◀️ Back to Games", callback_data="show_games"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\n"
            f"Your balance: <b>{balance:,} ⭐</b>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )


@handle_errors
async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'dice')


@handle_errors
async def bowl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'bowl')


@handle_errors
async def arrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'arrow')


@handle_errors
async def football_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'football')


@handle_errors
async def basket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_game_command(update, context, 'basket')


@handle_errors
async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
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


async def start_repeat_game(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, double: bool = False):
    """Start a repeat/double game based on last game settings"""
    if user_id not in user_last_game_settings:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ No previous game found to repeat!",
            parse_mode=ParseMode.HTML
        )
        return
    
    settings = user_last_game_settings[user_id]
    game_type = settings['game_type']
    bet_amount = settings['bet_amount']
    rounds = settings['rounds']
    throws = settings['throws']
    bot_first = settings['bot_first']
    
    if double:
        bet_amount = bet_amount * 2
    
    balance = get_user_balance(user_id)
    
    if balance < bet_amount and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ <b>Insufficient balance!</b>\n\n"
                 f"Required: <b>{bet_amount} ⭐</b>\n"
                 f"Your balance: <b>{balance} ⭐</b>\n\n"
                 f"Use /deposit to add more Stars.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if user_id in user_games:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ You already have an active game! Finish it first.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Deduct balance
    if not is_admin(user_id):
        user_balances[user_id] -= bet_amount
        save_data()
    
    # Get username from profile
    profile = user_profiles.get(user_id, {})
    username = profile.get('username', 'Player')
    
    game = Game(
        user_id=user_id,
        username=username,
        bet_amount=bet_amount,
        rounds=rounds,
        throw_count=throws,
        game_type=game_type
    )
    game.is_demo = False
    game.bot_first = bot_first
    game.bot_rolled_this_round = False
    game.user_throws_this_round = 0
    user_games[user_id] = game
    
    game_info = GAME_TYPES[game_type]
    double_tag = " (DOUBLED!)" if double else ""
    
    if game.bot_first:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{game_info['icon']} <b>Game Started!{double_tag}</b>\n\n"
                 f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                 f"🔄 Rounds: <b>{rounds}</b>\n"
                 f"🎯 Throws per round: <b>{throws}</b>\n\n"
                 f"🤖 Bot is rolling first...",
            parse_mode=ParseMode.HTML
        )
        
        await asyncio.sleep(1)
        bot_results = []
        for i in range(throws):
            bot_msg = await context.bot.send_dice(chat_id=chat_id, emoji=game_info['emoji'])
            bot_results.append(bot_msg.dice.value)
            await asyncio.sleep(0.3)
        
        game.bot_results.extend(bot_results)
        game.bot_rolled_this_round = True
        bot_total = sum(bot_results)
        
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🤖 <b>Bot's Round 1 total: {bot_total}</b>\n\n"
                 f"👤 Now it's your turn! Send {throws}x {game_info['emoji']}",
            parse_mode=ParseMode.HTML
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{game_info['icon']} <b>Game Started!{double_tag}</b>\n\n"
                 f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                 f"🔄 Rounds: <b>{rounds}</b>\n"
                 f"🎯 Throws per round: <b>{throws}</b>\n\n"
                 f"👤 You roll first! Send {throws}x {game_info['emoji']}",
            parse_mode=ParseMode.HTML
        )


@handle_errors
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        # Handle repeat/double buttons
        if data == "game_repeat":
            await start_repeat_game(context, user_id, query.message.chat_id, double=False)
            return
        
        if data == "game_double":
            await start_repeat_game(context, user_id, query.message.chat_id, double=True)
            return
        
        # Handle balance inline buttons
        if data == "balance_deposit":
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
                ],
                [
                    InlineKeyboardButton("◀️ Back", callback_data="back_to_balance"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "💳 <b>Select deposit amount:</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "balance_withdraw":
            if query.message.chat.type != "private":
                bot_info = await context.bot.get_me()
                await query.edit_message_text(
                    "🔒 <b>Private Command Only</b>\n\n"
                    "For your security, withdrawals can only be done in a private chat with the bot.\n\n"
                    f"👉 <a href='https://t.me/{bot_info.username}?start=withdraw'>Click here to open DM</a>\n\n"
                    "Then use /withdraw command.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            context.user_data['withdraw_state'] = None
            context.user_data['withdraw_amount'] = None
            context.user_data['withdraw_address'] = None
            
            welcome_text = (
                "✨ <b>Welcome to Stars Withdrawal!</b>\n\n"
                "<b>Withdraw:</b>\n"
                "1 ⭐️ = $0.0179 = 0.01201014 TON\n\n"
                f"<b>Minimum withdrawal: {MIN_WITHDRAWAL} ⭐</b>\n\n"
                "<blockquote>⚙️ <b>Good to know:</b>\n"
                "• When you exchange stars through a channel or bot, Telegram keeps a 15% fee and applies a 21-day hold.\n"
                "• We send TON immediately—factoring in this fee and a small service premium.</blockquote>"
            )
            
            keyboard = [[InlineKeyboardButton("💎 Withdraw", callback_data="start_withdraw")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "back_to_balance":
            balance = get_user_balance(user_id)
            balance_usd = balance * STARS_TO_USD
            admin_note = " (Admin - Unlimited)" if is_admin(user_id) else ""
            
            keyboard = [
                [
                    InlineKeyboardButton("💳 Deposit", callback_data="balance_deposit"),
                    InlineKeyboardButton("💎 Withdraw", callback_data="balance_withdraw"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"💰 <b>Your Balance</b>{admin_note}\n\n"
                f"⭐ Stars: <b>{balance:,} ⭐</b>\n"
                f"💵 USD: <b>${balance_usd:.2f}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "show_games":
            keyboard = [
                [
                    InlineKeyboardButton("🎲 Dice", callback_data="play_game_dice"),
                    InlineKeyboardButton("🎳 Bowling", callback_data="play_game_bowl"),
                ],
                [
                    InlineKeyboardButton("🎯 Darts", callback_data="play_game_arrow"),
                    InlineKeyboardButton("⚽ Football", callback_data="play_game_football"),
                ],
                [
                    InlineKeyboardButton("🏀 Basketball", callback_data="play_game_basket"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🎮 <b>Select a game to play:</b>\n\n"
                "🎲 <b>Dice</b> - Roll the dice and beat the bot!\n"
                "🎳 <b>Bowling</b> - Strike your way to victory!\n"
                "🎯 <b>Darts</b> - Aim for the bullseye!\n"
                "⚽ <b>Football</b> - Score goals and win!\n"
                "🏀 <b>Basketball</b> - Shoot hoops for stars!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("play_game_"):
            game_type = data.replace("play_game_", "")
            await start_game_from_callback(query, context, game_type)
            return
        
        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            await query.edit_message_text(
                f"💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                f"Minimum: {MIN_WITHDRAWAL} ⭐\n"
                f"Example: 100",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "confirm_withdraw":
            global withdrawal_counter
            
            stars_amount = context.user_data.get('withdraw_amount', 0)
            ton_address = context.user_data.get('withdraw_address', '')
            
            balance = get_user_balance(user_id)
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
            
            if not is_admin(user_id):
                user_balances[user_id] -= stars_amount
            
            withdrawal_counter += 1
            exchange_id = withdrawal_counter
            
            ton_amount = round(stars_amount * STARS_TO_TON, 8)
            transaction_id = generate_transaction_id()
            
            now = datetime.now()
            created_date = now.strftime("%Y-%m-%d %H:%M")
            hold_until = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
            
            user_withdrawals[str(user_id)] = {
                'exchange_id': exchange_id,
                'stars': stars_amount,
                'ton_amount': ton_amount,
                'address': ton_address,
                'transaction_id': transaction_id,
                'created': created_date,
                'hold_until': hold_until,
                'status': 'on_hold'
            }
            
            save_data()
            
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
                f"📝 Reason: Iibrate game rating is negative. Placed on 14-day hold."
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
            if not is_admin(user_id):
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
            if not is_admin(user_id):
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
            balance = get_user_balance(user_id)
            
            if balance < bet_amount and not is_admin(user_id):
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
            balance = get_user_balance(user_id)
            
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
                    InlineKeyboardButton("◀️ Back to Games", callback_data="show_games"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                f"💰 Choose your bet:\n"
                f"Your balance: <b>{balance:,} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("rounds_"):
            parts = data.split("_")
            game_type = parts[1]
            rounds = int(parts[2])
            
            context.user_data['rounds'] = rounds
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("1 Throw", callback_data=f"throws_{game_type}_1"),
                    InlineKeyboardButton("2 Throws", callback_data=f"throws_{game_type}_2"),
                ],
                [
                    InlineKeyboardButton("3 Throws", callback_data=f"throws_{game_type}_3"),
                ],
                [
                    InlineKeyboardButton("Back ◀️", callback_data=f"bet_{game_type}_{context.user_data.get('bet_amount', 10)}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            is_demo = context.user_data.get('is_demo', False)
            demo_tag = " 🔑" if is_demo else ""
            
            await query.edit_message_text(
                f"{game_info['icon']} <b>Select throws per round:</b>{demo_tag}\n"
                f"Rounds: <b>{rounds}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("throws_"):
            parts = data.split("_")
            game_type = parts[1]
            throws = int(parts[2])
            
            bet_amount = context.user_data.get('bet_amount', 10)
            rounds = context.user_data.get('rounds', 1)
            is_demo = context.user_data.get('is_demo', False)
            
            context.user_data['throws'] = throws
            
            game_info = GAME_TYPES[game_type]
            keyboard = [
                [
                    InlineKeyboardButton("👤 I roll first", callback_data=f"start_game_{game_type}_user"),
                ],
                [
                    InlineKeyboardButton("🤖 Bot rolls first", callback_data=f"start_game_{game_type}_bot"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            demo_tag = " 🔑 DEMO" if is_demo else ""
            
            await query.edit_message_text(
                f"{game_info['icon']} <b>Who should roll first?{demo_tag}</b>\n\n"
                f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                f"🔄 Rounds: <b>{rounds}</b>\n"
                f"🎯 Throws per round: <b>{throws}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        if data.startswith("start_game_"):
            parts = data.split("_")
            game_type = parts[2]
            who_first = parts[3]
            
            bet_amount = context.user_data.get('bet_amount', 10)
            rounds = context.user_data.get('rounds', 1)
            throws = context.user_data.get('throws', 1)
            is_demo = context.user_data.get('is_demo', False)
            
            if not is_demo and not is_admin(user_id):
                balance = get_user_balance(user_id)
                if balance < bet_amount:
                    await query.edit_message_text(
                        "❌ Insufficient balance! Use /deposit to add Stars."
                    )
                    return
                user_balances[user_id] -= bet_amount
                save_data()
            
            game = Game(
                user_id=user_id,
                username=query.from_user.username or query.from_user.first_name,
                bet_amount=bet_amount,
                rounds=rounds,
                throw_count=throws,
                game_type=game_type
            )
            game.is_demo = is_demo
            game.bot_first = (who_first == 'bot')
            game.bot_rolled_this_round = False
            game.user_throws_this_round = 0
            user_games[user_id] = game
            
            # Save game settings for repeat/double feature
            if not is_demo:
                save_last_game_settings(user_id, game_type, bet_amount, rounds, throws, game.bot_first)
            
            game_info = GAME_TYPES[game_type]
            demo_tag = " 🔑 DEMO" if is_demo else ""
            
            if game.bot_first:
                await query.edit_message_text(
                    f"{game_info['icon']} <b>Game Started!{demo_tag}</b>\n\n"
                    f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                    f"🔄 Rounds: <b>{rounds}</b>\n"
                    f"🎯 Throws per round: <b>{throws}</b>\n\n"
                    f"🤖 Bot is rolling first...",
                    parse_mode=ParseMode.HTML
                )
                
                await asyncio.sleep(1)
                bot_results = []
                for i in range(throws):
                    bot_msg = await query.message.reply_dice(emoji=game_info['emoji'])
                    bot_results.append(bot_msg.dice.value)
                    await asyncio.sleep(0.3)
                
                game.bot_results.extend(bot_results)
                game.bot_rolled_this_round = True
                bot_total = sum(bot_results)
                
                await asyncio.sleep(1)
                await query.message.reply_html(
                    f"🤖 <b>Bot's Round 1 total: {bot_total}</b>\n\n"
                    f"👤 Now it's your turn! Send {throws}x {game_info['emoji']}"
                )
            else:
                await query.edit_message_text(
                    f"{game_info['icon']} <b>Game Started!{demo_tag}</b>\n\n"
                    f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                    f"🔄 Rounds: <b>{rounds}</b>\n"
                    f"🎯 Throws per round: <b>{throws}</b>\n\n"
                    f"👤 You roll first! Send {throws}x {game_info['emoji']}",
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
            
    except Exception as e:
        logger.error(f"Button callback error: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ An error occurred. Please try again.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


@handle_errors
async def handle_game_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_games:
        return
    
    game = user_games[user_id]
    game_info = GAME_TYPES[game.game_type]
    emoji = game_info['emoji']
    
    message = update.message
    if not message.dice:
        return
    
    if message.dice.emoji != emoji:
        return
    
    user_value = message.dice.value
    game.user_results.append(user_value)
    game.user_throws_this_round += 1
    
    if game.user_throws_this_round >= game.throw_count:
        await asyncio.sleep(0.5)
        
        if not game.bot_rolled_this_round:
            bot_results = []
            for _ in range(game.throw_count):
                bot_msg = await message.reply_dice(emoji=emoji)
                bot_results.append(bot_msg.dice.value)
                await asyncio.sleep(0.3)
            
            game.bot_results.extend(bot_results)
        
        round_start = (game.current_round) * game.throw_count
        user_round_total = sum(game.user_results[round_start:round_start + game.throw_count])
        bot_round_total = sum(game.bot_results[round_start:round_start + game.throw_count])
        
        game.current_round += 1
        
        game.bot_rolled_this_round = False
        game.user_throws_this_round = 0
        
        if user_round_total > bot_round_total:
            game.user_score += 1
            round_result = "✅ You won this round!"
        elif bot_round_total > user_round_total:
            game.bot_score += 1
            round_result = "❌ Bot won this round!"
        else:
            round_result = "🤝 This round is a tie!"
        
        await asyncio.sleep(2)
        
        if game.current_round < game.total_rounds:
            if game.bot_first:
                await message.reply_html(
                    f"<b>Round {game.current_round} Results:</b>\n\n"
                    f"👤 Your total: <b>{user_round_total}</b>\n"
                    f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                    f"{round_result}\n\n"
                    f"📊 Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                    f"🤖 Bot is rolling for Round {game.current_round + 1}..."
                )
                
                await asyncio.sleep(1)
                bot_results = []
                for _ in range(game.throw_count):
                    bot_msg = await message.reply_dice(emoji=emoji)
                    bot_results.append(bot_msg.dice.value)
                    await asyncio.sleep(0.3)
                
                game.bot_results.extend(bot_results)
                game.bot_rolled_this_round = True
                bot_total = sum(bot_results)
                
                await asyncio.sleep(1)
                await message.reply_html(
                    f"🤖 <b>Bot's Round {game.current_round + 1} total: {bot_total}</b>\n\n"
                    f"👤 Your turn! Send {game.throw_count}x {emoji}"
                )
            else:
                await message.reply_html(
                    f"<b>Round {game.current_round} Results:</b>\n\n"
                    f"👤 Your total: <b>{user_round_total}</b>\n"
                    f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                    f"{round_result}\n\n"
                    f"📊 Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                    f"👤 Send {game.throw_count}x {emoji} for Round {game.current_round + 1}!"
                )
        else:
            demo_tag = " (DEMO)" if game.is_demo else ""
            
            user_link = get_user_link(user_id, game.username)
            
            if game.user_score > game.bot_score:
                winnings = game.bet_amount * 2
                if not game.is_demo:
                    adjust_user_balance(user_id, winnings)
                    update_game_stats(user_id, game.game_type, game.bet_amount, winnings, True)
                result_text = f"🎉 <b>{user_link} WON!{demo_tag}</b> 🎉\n\n💰 Winnings: <b>{winnings} ⭐</b>"
            elif game.bot_score > game.user_score:
                if not game.is_demo:
                    update_game_stats(user_id, game.game_type, game.bet_amount, 0, False)
                result_text = f"😔 <b>{user_link} lost!{demo_tag}</b>\n\n💸 Lost: <b>{game.bet_amount} ⭐</b>"
            else:
                if not game.is_demo:
                    adjust_user_balance(user_id, game.bet_amount)
                result_text = f"🤝 <b>It's a tie!{demo_tag}</b>\n\n💰 Bet returned: <b>{game.bet_amount} ⭐</b>"
            
            balance = get_user_balance(user_id)
            
            # Create repeat/double buttons (only for non-demo games)
            if not game.is_demo:
                double_bet = game.bet_amount * 2
                keyboard = [
                    [
                        InlineKeyboardButton(f"🔄 Repeat ({game.bet_amount} ⭐)", callback_data="game_repeat"),
                        InlineKeyboardButton(f"⏫ Double ({double_bet} ⭐)", callback_data="game_double"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None
            
            await message.reply_html(
                f"<b>Final Round Results:</b>\n\n"
                f"👤 Your total: <b>{user_round_total}</b>\n"
                f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                f"{round_result}\n\n"
                f"📊 Final Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                f"{result_text}\n\n"
                f"💰 Balance: <b>{balance:,} ⭐</b>",
                reply_markup=reply_markup
            )
            
            del user_games[user_id]


@handle_errors
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_custom_amount'):
        try:
            amount = int(text)
            if amount < 1:
                await update.message.reply_html("❌ Minimum deposit is 1 ⭐")
                return
            if amount > 2500:
                await update.message.reply_html("❌ Maximum deposit is 2500 ⭐")
                return
            
            context.user_data['waiting_for_custom_amount'] = False
            
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
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid number.")
        return
    
    if context.user_data.get('withdraw_state') == 'waiting_amount':
        try:
            amount = int(text)
            balance = get_user_balance(user_id)
            
            if amount < MIN_WITHDRAWAL:
                await update.message.reply_html(f"❌ Minimum withdrawal is {MIN_WITHDRAWAL} ⭐")
                return
            
            if amount > balance:
                await update.message.reply_html(
                    f"❌ Insufficient balance!\n\n"
                    f"Your balance: {balance} ⭐\n"
                    f"Requested: {amount} ⭐"
                )
                return
            
            context.user_data['withdraw_amount'] = amount
            context.user_data['withdraw_state'] = 'waiting_address'
            
            ton_amount = round(amount * STARS_TO_TON, 8)
            
            await update.message.reply_html(
                f"💎 <b>Withdrawal Amount:</b> {amount} ⭐\n"
                f"💰 <b>TON Amount:</b> {ton_amount}\n\n"
                f"📝 <b>Enter your TON wallet address:</b>"
            )
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid number.")
        return
    
    if context.user_data.get('withdraw_state') == 'waiting_address':
        if not is_valid_ton_address(text):
            await update.message.reply_html(
                "❌ <b>Invalid TON address!</b>\n\n"
                "Please enter a valid TON wallet address."
            )
            return
        
        context.user_data['withdraw_address'] = text
        
        stars_amount = context.user_data.get('withdraw_amount', 0)
        ton_amount = round(stars_amount * STARS_TO_TON, 8)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"📋 <b>Withdrawal Summary:</b>\n\n"
            f"⭐️ Stars: {stars_amount}\n"
            f"💎 TON: {ton_amount}\n"
            f"🏦 Address: <code>{text}</code>\n\n"
            f"Confirm withdrawal?",
            reply_markup=reply_markup
        )
        return


@handle_errors
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


@handle_errors
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    
    amount = payment.total_amount
    adjust_user_balance(user_id, amount)
    
    balance = get_user_balance(user_id)
    
    await update.message.reply_html(
        f"✅ <b>Payment successful!</b>\n\n"
        f"💰 Added: <b>{amount} ⭐</b>\n"
        f"💳 New balance: <b>{balance:,} ⭐</b>"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_html(
                "❌ <b>An unexpected error occurred</b>\n\n"
                "Please try again later. If the problem persists, contact support."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")


def main():
    # Load saved data on startup
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_error_handler(error_handler)
    
    # Basic commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("bal", balance_command))  # Alias
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("depo", deposit_command))  # Alias
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("custom", custom_deposit))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("bonus", bonus_command))
    
    # Game commands
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("bowl", bowl_command))
    application.add_handler(CommandHandler("arrow", arrow_command))
    application.add_handler(CommandHandler("football", football_command))
    application.add_handler(CommandHandler("basket", basket_command))
    application.add_handler(CommandHandler("demo", demo_command))
    
    # Admin commands
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("listadmins", listadmins_command))
    
    # Tip command
    application.add_handler(CommandHandler("tip", tip_command))
    
    # Handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_game_emoji))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
