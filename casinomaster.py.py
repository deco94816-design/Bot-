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

BOT_TOKEN = "8059137164:AAED-jufvoyL7lOuSLNNDH4C02WoBjBNjPU"
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
PROVIDER_TOKEN = ""
ADMIN_ID = 5709159932

# Bot username for bonus check
BOT_USERNAME = "Librate"

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

# Track weekly bonus claims (user_id -> last claim datetime)
user_weekly_bonus_claimed = {}

# Track last game settings for repeat/double feature
user_last_game_settings = {}

# Username to user_id mapping
username_to_id = {}

# Admin-set casino bankroll (USD)
casino_bankroll_usd = 0.0

# Track admin broadcast state per admin user_id
broadcast_waiting = set()

# Track which user owns which menu message (callback protection)
menu_owners = {}

# Withdraw video file_id (set by admin via /video command)
withdraw_video_file_id = None

# Bot identity (set via /steal command)
bot_identity = {
    "name": "Iibrate",
    "channel_link": "",
    "chat_link": "",
    "support_username": ""
}

# Referral system
user_referral_codes = {}  # user_id -> referral_code
referral_code_to_user = {}  # referral_code -> user_id
user_referrers = {}  # user_id -> referrer_user_id (who referred them)
user_referrals = defaultdict(set)  # referrer_user_id -> set of referred user_ids
user_referral_earnings = defaultdict(float)  # user_id -> total lifetime earnings (in stars)
user_referral_balance = defaultdict(float)  # user_id -> current withdrawable balance (in stars)

# Banned users
banned_users = set()  # user_id -> banned status

# Gift system
admin_gift_mode = {}  # admin_id -> True if pingme was sent (enables real stars gift)
gift_comment = "🏆 @Iibrate - be with the best!"  # Gift comment (changeable via /cg)

# Support ticket system
user_tickets = {}  # user_id -> list of tickets
ticket_counter = 1  # Global ticket counter

STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014
MIN_WITHDRAWAL = 200  # Can be changed by admin via /wd command
BONUS_AMOUNT = 20  # legacy/profile bonus
BONUS_MIN = 30
BONUS_MAX = 50

GAME_TYPES = {
    'dice': {'emoji': '🎲', 'name': 'Dice', 'max_value': 6, 'icon': '🎲'},
    'bowl': {'emoji': '🎳', 'name': 'Bowling', 'max_value': 6, 'icon': '🎳'},
    'arrow': {'emoji': '🎯', 'name': 'Darts', 'max_value': 6, 'icon': '🎯'},
    'football': {'emoji': '⚽', 'name': 'Football', 'max_value': 5, 'icon': '🥅'},
    'basket': {'emoji': '🏀', 'name': 'Basketball', 'max_value': 5, 'icon': '🏀'}
}

# Casino Levels System (Steel to Diamond)
CASINO_LEVELS = {
    0: {"name": "Steel", "rakeback": 5.0, "weekly_mult": 1.09, "level_up_bonus": 0, "next_level": 1},
    1: {"name": "Iron I", "rakeback": 6.5, "weekly_mult": 1.09, "level_up_bonus": 5, "next_level": 2},
    2: {"name": "Iron II", "rakeback": 7.0, "weekly_mult": 1.12, "level_up_bonus": 5, "next_level": 3},
    3: {"name": "Iron III", "rakeback": 7.0, "weekly_mult": 1.12, "level_up_bonus": 5, "next_level": 4},
    4: {"name": "Iron IV", "rakeback": 7.0, "weekly_mult": 1.12, "level_up_bonus": 5, "next_level": 5},
    5: {"name": "Bronze I", "rakeback": 7.5, "weekly_mult": 1.15, "level_up_bonus": 7, "next_level": 6},
    6: {"name": "Bronze II", "rakeback": 8.0, "weekly_mult": 1.18, "level_up_bonus": 10, "next_level": 7},
    7: {"name": "Bronze III", "rakeback": 8.5, "weekly_mult": 1.21, "level_up_bonus": 12, "next_level": 8},
    8: {"name": "Bronze IV", "rakeback": 9.0, "weekly_mult": 1.25, "level_up_bonus": 15, "next_level": 9},
    9: {"name": "Silver I", "rakeback": 9.5, "weekly_mult": 1.30, "level_up_bonus": 20, "next_level": 10},
    10: {"name": "Silver II", "rakeback": 10.0, "weekly_mult": 1.35, "level_up_bonus": 25, "next_level": 11},
    11: {"name": "Silver III", "rakeback": 10.5, "weekly_mult": 1.40, "level_up_bonus": 30, "next_level": 12},
    12: {"name": "Silver IV", "rakeback": 11.0, "weekly_mult": 1.45, "level_up_bonus": 40, "next_level": 13},
    13: {"name": "Gold I", "rakeback": 12.0, "weekly_mult": 1.50, "level_up_bonus": 50, "next_level": 14},
    14: {"name": "Gold II", "rakeback": 13.0, "weekly_mult": 1.55, "level_up_bonus": 75, "next_level": 15},
    15: {"name": "Gold III", "rakeback": 14.0, "weekly_mult": 1.60, "level_up_bonus": 100, "next_level": 16},
    16: {"name": "Gold IV", "rakeback": 15.0, "weekly_mult": 1.70, "level_up_bonus": 150, "next_level": 17},
    17: {"name": "Platinum I", "rakeback": 16.0, "weekly_mult": 1.80, "level_up_bonus": 200, "next_level": 18},
    18: {"name": "Platinum II", "rakeback": 17.0, "weekly_mult": 1.90, "level_up_bonus": 250, "next_level": 19},
    19: {"name": "Platinum III", "rakeback": 18.0, "weekly_mult": 2.00, "level_up_bonus": 300, "next_level": 20},
    20: {"name": "Platinum IV", "rakeback": 20.0, "weekly_mult": 2.20, "level_up_bonus": 400, "next_level": 21},
    21: {"name": "Diamond I", "rakeback": 22.0, "weekly_mult": 2.40, "level_up_bonus": 500, "next_level": 22},
    22: {"name": "Diamond II", "rakeback": 24.0, "weekly_mult": 2.60, "level_up_bonus": 750, "next_level": 23},
    23: {"name": "Diamond III", "rakeback": 26.0, "weekly_mult": 2.80, "level_up_bonus": 1000, "next_level": 24},
    24: {"name": "Diamond IV", "rakeback": 28.0, "weekly_mult": 3.00, "level_up_bonus": 1500, "next_level": 25},
    25: {"name": "Diamond V", "rakeback": 30.0, "weekly_mult": 3.50, "level_up_bonus": 2500, "next_level": None}
}

# Level progression thresholds (total bets in USD)
LEVEL_THRESHOLDS = {
    0: 0,      # Steel
    1: 100,    # Iron I
    2: 250,    # Iron II
    3: 500,    # Iron III
    4: 1000,   # Iron IV
    5: 2000,   # Bronze I
    6: 3500,   # Bronze II
    7: 5500,   # Bronze III
    8: 8000,   # Bronze IV
    9: 12000,  # Silver I
    10: 18000, # Silver II
    11: 26000, # Silver III
    12: 36000, # Silver IV
    13: 50000, # Gold I
    14: 70000, # Gold II
    15: 95000, # Gold III
    16: 130000, # Gold IV
    17: 180000, # Platinum I
    18: 250000, # Platinum II
    19: 350000, # Platinum III
    20: 500000, # Platinum IV
    21: 750000, # Diamond I
    22: 1100000, # Diamond II
    23: 1600000, # Diamond III
    24: 2300000, # Diamond IV
    25: 3500000  # Diamond V (MAX)
}


# ==================== JSON DATA PERSISTENCE ====================

def save_data():
    """Save all data to JSON file"""
    global withdraw_video_file_id, MIN_WITHDRAWAL, gift_comment
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
            'user_last_game_settings': user_last_game_settings,
            'withdraw_video_file_id': withdraw_video_file_id,
            'casino_bankroll_usd': casino_bankroll_usd,
            'user_weekly_bonus_claimed': {},
            'user_referral_codes': user_referral_codes,
            'referral_code_to_user': referral_code_to_user,
            'user_referrers': {str(k): v for k, v in user_referrers.items()},
            'user_referrals': {str(k): list(v) for k, v in user_referrals.items()},
            'user_referral_earnings': {str(k): v for k, v in user_referral_earnings.items()},
            'user_referral_balance': {str(k): v for k, v in user_referral_balance.items()},
            'bot_identity': bot_identity,
            'banned_users': list(banned_users),
            'min_withdrawal': MIN_WITHDRAWAL,
            'gift_comment': gift_comment,
            'user_tickets': {str(k): v for k, v in user_tickets.items()},
            'ticket_counter': ticket_counter
        }
        
        # Convert weekly bonus claims with datetime serialization
        for user_id, claim_date in user_weekly_bonus_claimed.items():
            data['user_weekly_bonus_claimed'][str(user_id)] = claim_date.isoformat()
        
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
    global user_withdrawals, withdrawal_counter, admin_list, username_to_id
    global user_last_game_settings, withdraw_video_file_id, casino_bankroll_usd
    global user_weekly_bonus_claimed
    global user_referral_codes, referral_code_to_user, user_referrers
    global user_referrals, user_referral_earnings, user_referral_balance
    global bot_identity, banned_users, MIN_WITHDRAWAL, gift_comment
    global user_tickets, ticket_counter
    
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
        withdraw_video_file_id = data.get('withdraw_video_file_id', None)
        casino_bankroll_usd = float(data.get('casino_bankroll_usd', 0.0))
        
        # Load weekly bonus claims
        for user_id_str, claim_date_str in data.get('user_weekly_bonus_claimed', {}).items():
            user_id = int(user_id_str)
            user_weekly_bonus_claimed[user_id] = datetime.fromisoformat(claim_date_str)
        
        # Load referral data
        user_referral_codes.update({int(k): v for k, v in data.get('user_referral_codes', {}).items()})
        referral_code_to_user.update({k: int(v) for k, v in data.get('referral_code_to_user', {}).items()})
        user_referrers.update({int(k): int(v) for k, v in data.get('user_referrers', {}).items()})
        for k, v in data.get('user_referrals', {}).items():
            user_referrals[int(k)] = set(int(uid) for uid in v)
        user_referral_earnings.update({int(k): float(v) for k, v in data.get('user_referral_earnings', {}).items()})
        user_referral_balance.update({int(k): float(v) for k, v in data.get('user_referral_balance', {}).items()})
        
        # Load bot identity
        if 'bot_identity' in data:
            bot_identity.update(data['bot_identity'])
        
        # Load banned users
        banned_users.update(set(int(uid) for uid in data.get('banned_users', [])))
        
        # Load minimum withdrawal
        if 'min_withdrawal' in data:
            MIN_WITHDRAWAL = int(data['min_withdrawal'])
        
        # Load gift comment
        if 'gift_comment' in data:
            gift_comment = data['gift_comment']
        
        # Load tickets
        if 'user_tickets' in data:
            user_tickets.update({int(k): v for k, v in data['user_tickets'].items()})
        if 'ticket_counter' in data:
            ticket_counter = data['ticket_counter']
        
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


def is_banned(user_id):
    """Check if a user is banned"""
    return user_id in banned_users


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


def register_menu_owner(message, owner_id):
    """Register which user owns an inline menu message (chat-scoped)."""
    if message and hasattr(message, "message_id") and hasattr(message, "chat"):
        key = (message.chat_id, message.message_id)
        menu_owners[key] = owner_id


def get_user_link(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def format_user_display(user_id, profile):
    """Return @username if available, otherwise clickable link with their name."""
    username = (profile.get('username') or '').lstrip('@').strip()
    display_name = profile.get('display_name') or profile.get('username') or 'Player'
    if username and username.lower() != 'unknown':
        return f"@{username}"
    return get_user_link(user_id, display_name)


def get_or_create_profile(user_id, username=None):
    display_name = username or 'Unknown'
    
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            'user_id': user_id,
            'username': username,           # raw username (may be None)
            'display_name': display_name,   # shown when no username
            'registration_date': datetime.now(),
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
    else:
        # Update display name on repeat calls
        profile = user_profiles[user_id]
        if username:
            profile['display_name'] = username
    
    # Update username mapping if an actual username is provided
    if username:
        username_lower = username.lower().lstrip('@')
        username_to_id[username_lower] = user_id
        save_data()
    
    return user_profiles[user_id]


# ==================== REFERRAL SYSTEM ====================

def generate_referral_code():
    """Generate a unique 8-character referral code"""
    import secrets
    max_attempts = 100
    attempts = 0
    while attempts < max_attempts:
        code = secrets.token_hex(4)[:8]  # 8 characters from hex
        if code not in referral_code_to_user:
            return code
        attempts += 1
    # Fallback: use timestamp-based code if all attempts fail
    import time
    code = hex(int(time.time() * 1000000))[-8:].ljust(8, '0')
    return code


def get_or_create_referral_code(user_id):
    """Get or create a referral code for a user"""
    if user_id not in user_referral_codes:
        code = generate_referral_code()
        user_referral_codes[user_id] = code
        referral_code_to_user[code] = user_id
        save_data()
    return user_referral_codes[user_id]


def get_referral_rate(user_id):
    """Get referral commission rate based on user's level"""
    try:
        profile = get_or_create_profile(user_id)
        total_bets = profile.get('total_bets', 0.0)
        total_bets_usd = total_bets * STARS_TO_USD
        level = get_user_level(total_bets_usd)
        
        # Rate tiers based on level
        if level <= 8:  # Steel to Bronze IV
            return 10.0
        elif level <= 12:  # Silver I to Silver IV
            return 12.0
        elif level <= 20:  # Gold I to Platinum IV
            return 15.0
        else:  # Diamond I to Diamond V
            return 20.0
    except Exception:
        return 10.0  # Default rate


def process_referral_earning(referred_user_id, loss_amount):
    """Process referral earnings when a referred user loses"""
    if referred_user_id not in user_referrers:
        return
    
    referrer_id = user_referrers[referred_user_id]
    if not referrer_id:
        return
    
    rate = get_referral_rate(referrer_id)
    earnings = (loss_amount * rate) / 100
    
    user_referral_earnings[referrer_id] += earnings
    user_referral_balance[referrer_id] += earnings
    save_data()
    
    logger.info(f"Referral earning: User {referred_user_id} lost {loss_amount} stars, "
                f"Referrer {referrer_id} earned {earnings} stars ({rate}%)")


# Legacy rank functions (kept for backward compatibility, not used in new level system)
RANKS = {1: {"name": "Newcomer", "xp_required": 0, "emoji": "🌱"}}

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
    else:
        profile['games_lost'] += 1
        profile['total_losses'] += bet_amount
        # Process referral earnings when user loses
        process_referral_earning(user_id, bet_amount)
    
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
    bot_name_lower = bot_identity.get("name", BOT_USERNAME).lower()
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
        # Check if user is banned (allow admins and ban/unban commands)
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
        elif update.message and update.message.from_user:
            user_id = update.message.from_user.id
        elif update.callback_query and update.callback_query.from_user:
            user_id = update.callback_query.from_user.id
        
        # Allow ban/unban commands to work even if admin is somehow banned
        command_name = func.__name__
        is_ban_command = command_name in ['ban_command', 'unban_command']
        
        # Check if user is banned (allow admins and ban/unban commands)
        if user_id and is_banned(user_id) and not is_admin(user_id) and not is_ban_command:
            return  # Silently ignore banned users
        
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

def get_next_saturday():
    """Get the next Saturday at 00:00:00 (if today is Saturday, return next Saturday)"""
    now = datetime.now()
    # Saturday is weekday 5 (Monday=0, Sunday=6)
    days_until_saturday = (5 - now.weekday()) % 7
    
    # If today is Saturday, return next Saturday (7 days)
    if days_until_saturday == 0:
        days_until_saturday = 7
    
    next_saturday = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_saturday += timedelta(days=days_until_saturday)
    return next_saturday


def is_saturday():
    """Check if today is Saturday"""
    return datetime.now().weekday() == 5


def format_time_remaining(target_time):
    """Format time remaining as 'X Days HH:MM:SS'"""
    now = datetime.now()
    if target_time <= now:
        return "0 Days 00:00:00"
    
    delta = target_time - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return f"{days} Days {hours:02d}:{minutes:02d}:{seconds:02d}"


def calculate_estimated_weekly_bonus(user_id):
    """Return a random weekly bonus amount to display (30-50 stars)."""
    return random.randint(BONUS_MIN, BONUS_MAX)


def get_weekly_bonus_amount():
    """Return a random weekly bonus amount within range."""
    return random.randint(BONUS_MIN, BONUS_MAX)


@handle_errors
async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    next_saturday = get_next_saturday()
    time_remaining = format_time_remaining(next_saturday)
    estimated_bonus = calculate_estimated_weekly_bonus(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎁 Redeem bonus", callback_data="redeem_weekly_bonus")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    bot_name = bot_identity.get("name", BOT_USERNAME)
    bonus_text = (
        f"⏰ <b>Weekly Bonus Available in {time_remaining}</b>\n\n"
        f"Total estimated Weekly Bonus: {estimated_bonus} ⭐\n\n"
        f"Add @{bot_name} in your name to get your weekly Boosted"
    )
    
    sent = await update.message.reply_html(bonus_text, reply_markup=reply_markup)
    register_menu_owner(sent, user_id)


@handle_errors
async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Empty bonus command - redirects to /weekly"""
    await weekly_command(update, context)


@handle_errors
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral information and link"""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Check if command is in group chat
        if update.effective_chat.type != "private":
            await update.message.reply_html(
                "Please use this command with bot in private messages."
            )
            return
        
        # Get or create referral code
        ref_code = get_or_create_referral_code(user_id)
        
        # Get referral stats
        rate = get_referral_rate(user_id)
        count = len(user_referrals.get(user_id, set()))
        total_earned = user_referral_earnings.get(user_id, 0.0)
        current_balance = user_referral_balance.get(user_id, 0.0)
        
        # Convert to USD
        total_earned_usd = total_earned * STARS_TO_USD
        current_balance_usd = current_balance * STARS_TO_USD
        
        # Get bot username for link
        try:
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username if bot_info.username else "Iibratebot"
        except Exception:
            bot_username = "Iibratebot"  # Fallback
        
        referral_text = (
            f"ℹ️ <b>Earn a bonus from the losses of the user you invited</b>\n\n"
            f"🔗 <b>Referral link:</b> t.me/{bot_username}?start=ref-{ref_code}\n"
            f"🔥 <b>Current rate:</b> {rate}%\n"
            f"📈 <b>Users invited:</b> {count}\n"
            f"💵 <b>Total earned:</b> ${total_earned_usd:.2f}\n"
            f"💵 <b>Current referral balance:</b> ${current_balance_usd:.2f}"
        )
        
        await update.message.reply_html(referral_text)
    except Exception as e:
        logger.error(f"Error in referral_command: {e}", exc_info=True)
        await update.message.reply_html(
            "❌ <b>An error occurred while displaying referral information.</b>\n\n"
            "Please try again later."
        )


# ==================== ADMIN COMMANDS ====================

@handle_errors
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "👑 <b>Add Admin</b>\n\n"
            "Usage: /addadmin [user_id]\n"
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
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_html(
            "👑 <b>Remove Admin</b>\n\n"
            "Usage: /removeadmin [user_id]\n"
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
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user - bot will ignore them"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    target_user_id = None
    target_username = None
    
    # Check if replying to a message
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
    # Check if username or user_id provided as argument
    elif context.args and len(context.args) > 0:
        arg = context.args[0].strip()
        # Remove @ if present
        if arg.startswith('@'):
            arg = arg[1:]
        
        # Try to find user by username
        if arg.lower() in username_to_id:
            target_user_id = username_to_id[arg.lower()]
            target_username = arg
        # Try to parse as user_id
        else:
            try:
                target_user_id = int(arg)
            except ValueError:
                await update.message.reply_html(
                    "❌ <b>Invalid input!</b>\n\n"
                    "Usage:\n"
                    "• /ban [user_id]\n"
                    "• /ban @username\n"
                    "• /ban (reply to user's message)"
                )
                return
    else:
        await update.message.reply_html(
            "🔨 <b>Ban User</b>\n\n"
            "Usage:\n"
            "• /ban [user_id]\n"
            "• /ban @username\n"
            "• /ban (reply to user's message)\n\n"
            "Example: /ban 123456789 or /ban @username"
        )
        return
    
    if not target_user_id:
        await update.message.reply_html("❌ <b>User not found!</b>")
        return
    
    # Prevent banning admins
    if is_admin(target_user_id):
        await update.message.reply_html("❌ <b>Cannot ban an admin!</b>")
        return
    
    # Check if already banned
    if target_user_id in banned_users:
        await update.message.reply_html(
            f"⚠️ <b>User is already banned!</b>\n\n"
            f"👤 User ID: <code>{target_user_id}</code>\n"
            f"📛 Username: @{target_username}" if target_username else f"👤 User ID: <code>{target_user_id}</code>"
        )
        return
    
    # Ban the user
    banned_users.add(target_user_id)
    save_data()
    
    # Get user link
    user_link = get_user_link(target_user_id, target_username or f"User {target_user_id}")
    
    await update.message.reply_html(
        f"Another one bites the {user_link}..!Banned"
    )
    
    logger.info(f"Admin {user_id} banned user: {target_user_id} ({target_username})")


@handle_errors
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user - bot will listen to them again"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    target_user_id = None
    target_username = None
    
    # Check if replying to a message
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
    # Check if username or user_id provided as argument
    elif context.args and len(context.args) > 0:
        arg = context.args[0].strip()
        # Remove @ if present
        if arg.startswith('@'):
            arg = arg[1:]
        
        # Try to find user by username
        if arg.lower() in username_to_id:
            target_user_id = username_to_id[arg.lower()]
            target_username = arg
        # Try to parse as user_id
        else:
            try:
                target_user_id = int(arg)
            except ValueError:
                await update.message.reply_html(
                    "❌ <b>Invalid input!</b>\n\n"
                    "Usage:\n"
                    "• /unban [user_id]\n"
                    "• /unban @username\n"
                    "• /unban (reply to user's message)"
                )
                return
    else:
        await update.message.reply_html(
            "✅ <b>Unban User</b>\n\n"
            "Usage:\n"
            "• /unban [user_id]\n"
            "• /unban @username\n"
            "• /unban (reply to user's message)\n\n"
            "Example: /unban 123456789 or /unban @username"
        )
        return
    
    if not target_user_id:
        await update.message.reply_html("❌ <b>User not found!</b>")
        return
    
    # Check if user is banned
    if target_user_id not in banned_users:
        await update.message.reply_html(
            f"⚠️ <b>User is not banned!</b>\n\n"
            f"👤 User ID: <code>{target_user_id}</code>\n"
            f"📛 Username: @{target_username}" if target_username else f"👤 User ID: <code>{target_user_id}</code>"
        )
        return
    
    # Unban the user
    banned_users.discard(target_user_id)
    save_data()
    
    username_display = f"@{target_username}" if target_username else "No username"
    await update.message.reply_html(
        f"✅ <b>User unbanned successfully!</b>\n\n"
        f"👤 User ID: <code>{target_user_id}</code>\n"
        f"📛 Username: {username_display}\n\n"
        f"The bot will now listen to this user again."
    )
    
    logger.info(f"Admin {user_id} unbanned user: {target_user_id} ({target_username})")


@handle_errors
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admin commands"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    try:
        total_admins = len(admin_list) if admin_list else 0
    except Exception:
        total_admins = 0
    
    admin_commands_text = (
        "👑 <b>Admin Commands</b>\n\n"
        "<b>Admin Management:</b>\n"
        "• /addadmin [user_id] - Add a new admin\n"
        "• /removeadmin [user_id] - Remove an admin\n"
        "• /listadmins - View all admins\n\n"
        "<b>User Management:</b>\n"
        "• /user - List all users\n"
        "• /ban [user_id/@username] or reply - Ban a user\n"
        "• /unban [user_id/@username] or reply - Unban a user\n\n"
        "<b>Bot Management:</b>\n"
        "• /video - Set withdraw video\n"
        "• /video status - Check video status\n"
        "• /video remove - Remove video\n"
        "• /broadcast or /bc - Send message to all users\n"
        "• /demo - Test games without betting\n"
        "• /steal - Rebrand bot (change name, links, support)\n"
        "• /gift - Send gift to user (emoji or stars)\n"
        "• /cg - Change gift comment\n\n"
        "<b>Bankroll:</b>\n"
        "• /hb or /housebal - Set casino bankroll\n"
        "• /wd - Set minimum withdrawal amount\n\n"
        f"<b>Total Admins:</b> {total_admins}\n"
        f"<b>Your Admin ID:</b> <code>{user_id}</code>"
    )
    
    try:
        await update.message.reply_html(admin_commands_text)
    except Exception as e:
        logger.error(f"Error sending admin command message: {e}", exc_info=True)
        # Try sending as plain text if HTML fails
        try:
            plain_text = (
                "👑 Admin Commands\n\n"
                "Admin Management:\n"
                "• /addadmin [user_id] - Add a new admin\n"
                "• /removeadmin [user_id] - Remove an admin\n"
                "• /listadmins - View all admins\n\n"
                "User Management:\n"
                "• /user - List all users\n"
                "• /ban [user_id/@username] or reply - Ban a user\n"
                "• /unban [user_id/@username] or reply - Unban a user\n\n"
                "Bot Management:\n"
                "• /video - Set withdraw video\n"
                "• /video status - Check video status\n"
                "• /video remove - Remove video\n"
                "• /broadcast or /bc - Send message to all users\n"
                "• /demo - Test games without betting\n"
                "• /gift - Send gift to user (emoji or stars)\n"
                "• /cg - Change gift comment\n\n"
                "Bankroll:\n"
                "• /hb or /housebal - Set casino bankroll\n"
                "• /wd - Set minimum withdrawal amount\n\n"
                f"Total Admins: {total_admins}\n"
                f"Your Admin ID: {user_id}"
            )
            await update.message.reply_text(plain_text)
        except Exception as e2:
            logger.error(f"Error sending plain text admin command: {e2}", exc_info=True)


# ==================== VIDEO COMMAND (ADMIN) ====================

@handle_errors
async def set_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to set the withdraw video"""
    global withdraw_video_file_id
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>Admin only command.</b>")
        return
    
    # Check if admin wants to view current video status
    if context.args and context.args[0].lower() == 'status':
        if withdraw_video_file_id:
            await update.message.reply_html(
                "🎬 <b>Withdraw Video Status</b>\n\n"
                f"✅ Video is set\n"
                f"📎 File ID: <code>{withdraw_video_file_id[:50]}...</code>"
            )
        else:
            await update.message.reply_html(
                "🎬 <b>Withdraw Video Status</b>\n\n"
                "❌ No video set yet\n\n"
                "Use /video to set one."
            )
        return
    
    # Check if admin wants to remove video
    if context.args and context.args[0].lower() == 'remove':
        if withdraw_video_file_id:
            withdraw_video_file_id = None
            save_data()
            await update.message.reply_html(
                "✅ <b>Withdraw video removed!</b>\n\n"
                "The /withdraw command will now send text only."
            )
        else:
            await update.message.reply_html("❌ No video is currently set.")
        return
    
    context.user_data['waiting_for_video'] = True
    await update.message.reply_html(
        "🎬 <b>Set Withdraw Video</b>\n\n"
        "Send a video or MP4 file now.\n\n"
        "This video will be sent with every /withdraw command.\n\n"
        "📝 <b>Other options:</b>\n"
        "• /video status - Check current video\n"
        "• /video remove - Remove current video\n"
        "• /cancel - Cancel this operation"
    )


@handle_errors
async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video upload from admin for withdraw feature and support ticket submissions"""
    global withdraw_video_file_id
    user_id = update.effective_user.id
    
    # Check if user has a support ticket waiting for video/mp3
    ticket_id = context.user_data.get('support_waiting_video_ticket_id')
    if ticket_id:
        # Find the ticket
        user_ticket_list = user_tickets.get(user_id, [])
        ticket = None
        for t in user_ticket_list:
            if t.get('ticket_id') == ticket_id and t.get('waiting_for_video'):
                ticket = t
                break
        
        if ticket:
            # Get video/audio/document from message
            video = update.message.video or update.message.animation or update.message.document
            audio = update.message.audio
            
            # Check if it's a video, audio (mp3), or document
            if video or audio:
                # Mark ticket as video received
                ticket['waiting_for_video'] = False
                ticket['video_received'] = True
                save_data()
                
                # Clear the context flag
                context.user_data.pop('support_waiting_video_ticket_id', None)
                
                # Get withdrawal_id for the confirmation message
                withdrawal_id = ticket.get('withdrawal_id')
                
                if withdrawal_id:
                    await update.message.reply_text(
                        f"Your message has been sent to the support team. We will get back to you shortly. The ticket is linked to exchange #{withdrawal_id}."
                    )
                else:
                    await update.message.reply_text(
                        f"Your message has been sent to the support team. We will get back to you shortly."
                    )
                return
    
    # Only process if admin is waiting to set video
    if not context.user_data.get('waiting_for_video'):
        return
    
    if not is_admin(user_id):
        return
    
    # Get video from message (can be video or animation/GIF)
    video = update.message.video or update.message.animation or update.message.document
    
    if not video:
        await update.message.reply_html(
            "❌ <b>Invalid file!</b>\n\n"
            "Please send a valid video file (MP4, etc.)\n\n"
            "Use /cancel to abort."
        )
        return
    
    # Check if it's a document, verify it's a video type
    if update.message.document:
        mime_type = update.message.document.mime_type or ""
        if not mime_type.startswith('video/'):
            await update.message.reply_html(
                "❌ <b>Invalid file type!</b>\n\n"
                "Please send a video file (MP4, etc.)\n\n"
                "Use /cancel to abort."
            )
            return
    
    withdraw_video_file_id = video.file_id
    context.user_data['waiting_for_video'] = False
    save_data()
    
    await update.message.reply_html(
        "✅ <b>Withdraw video set successfully!</b>\n\n"
        "This video will now be sent with all /withdraw messages.\n\n"
        "📝 <b>Commands:</b>\n"
        "• /video status - Check current video\n"
        "• /video remove - Remove video\n"
        "• /video - Set new video"
    )
    
    logger.info(f"Admin {user_id} set withdraw video: {video.file_id[:50]}...")


# ==================== STEAL COMMAND (ADMIN) ====================

def replace_bot_name_in_text(text, old_name, new_name):
    """Replace bot name in text (case-insensitive)"""
    if not text or not old_name or not new_name:
        return text
    # Replace all occurrences (case-insensitive)
    import re
    pattern = re.compile(re.escape(old_name), re.IGNORECASE)
    return pattern.sub(new_name, text)


@handle_errors
async def steal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to rebrand the bot"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    # Initialize steal flow
    context.user_data['steal_state'] = 'active'
    context.user_data['steal_new_name'] = None
    context.user_data['steal_channel_link'] = None
    context.user_data['steal_chat_link'] = None
    context.user_data['steal_support_username'] = None
    context.user_data['steal_channel_yes'] = False
    context.user_data['steal_chat_yes'] = False
    context.user_data['steal_support_yes'] = False
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="steal_name_yes"),
            InlineKeyboardButton("❌ No", callback_data="steal_name_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "🎭 <b>Bot Rebranding</b>\n\n"
        "This will change the bot's identity:\n"
        "• Bot name (replaces 'Iibrate' everywhere)\n"
        "• Channel link\n"
        "• Chat link\n"
        "• Support username\n\n"
        "📝 <b>Do you want to change the bot name?</b>",
        reply_markup=reply_markup
    )


@handle_errors
async def handle_steal_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle steal command text input flow"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    steal_state = context.user_data.get('steal_state')
    
    if not steal_state or steal_state not in ['collecting_data', 'collecting_all']:
        return
    
    # Determine which field we're waiting for
    if context.user_data.get('steal_waiting') == 'name':
        if not text or len(text) < 2:
            await update.message.reply_html("❌ Please send a valid name (at least 2 characters)")
            return
        context.user_data['steal_new_name'] = text
        await update.message.reply_html(f"✅ Bot name saved: <b>{text}</b>")
        # Move to next value
        await move_to_next_steal_value(update, context)
        return
    
    elif context.user_data.get('steal_waiting') == 'channel':
        if not text.startswith('http://') and not text.startswith('https://') and not text.startswith('@'):
            await update.message.reply_html(
                "❌ Please send a valid channel link or username:\n"
                "• https://t.me/channelname\n"
                "• @channelname"
            )
            return
        context.user_data['steal_channel_link'] = text
        await update.message.reply_html(f"✅ Channel link saved: <b>{text}</b>")
        # Move to next value
        await move_to_next_steal_value(update, context)
        return
    
    elif context.user_data.get('steal_waiting') == 'chat':
        if not text.startswith('http://') and not text.startswith('https://') and not text.startswith('@'):
            await update.message.reply_html(
                "❌ Please send a valid chat link or username:\n"
                "• https://t.me/chatname\n"
                "• @chatname"
            )
            return
        context.user_data['steal_chat_link'] = text
        await update.message.reply_html(f"✅ Chat link saved: <b>{text}</b>")
        # Move to next value
        await move_to_next_steal_value(update, context)
        return
    
    elif context.user_data.get('steal_waiting') == 'support':
        if not text or len(text) < 1:
            await update.message.reply_html("❌ Please send a valid username")
            return
        support_username = text.replace('@', '')
        context.user_data['steal_support_username'] = support_username
        await update.message.reply_html(f"✅ Support username saved: <b>@{support_username}</b>")
        # Move to next value
        await move_to_next_steal_value(update, context)
        return


async def move_to_next_steal_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Move to the next value that needs to be collected"""
    needs_name = context.user_data.get('steal_name_yes') and not context.user_data.get('steal_new_name')
    needs_channel = context.user_data.get('steal_channel_yes') and not context.user_data.get('steal_channel_link')
    needs_chat = context.user_data.get('steal_chat_yes') and not context.user_data.get('steal_chat_link')
    needs_support = context.user_data.get('steal_support_yes') and not context.user_data.get('steal_support_username')
    
    if needs_name:
        context.user_data['steal_waiting'] = 'name'
        await update.message.reply_html("📝 <b>Now send the bot name:</b>")
    elif needs_channel:
        context.user_data['steal_waiting'] = 'channel'
        await update.message.reply_html("📝 <b>Now send the channel link:</b>\n\nFormat: https://t.me/channelname or @channelname")
    elif needs_chat:
        context.user_data['steal_waiting'] = 'chat'
        await update.message.reply_html("📝 <b>Now send the chat link:</b>\n\nFormat: https://t.me/chatname or @chatname")
    elif needs_support:
        context.user_data['steal_waiting'] = 'support'
        await update.message.reply_html("📝 <b>Now send the support username:</b> (without @)")
    else:
        # All values collected, apply changes
        context.user_data['steal_waiting'] = None
        await apply_steal_changes(update, context)


async def check_and_continue_steal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if all required data is collected and continue or finish"""
    # This function is now mainly for backward compatibility
    # The main flow uses move_to_next_steal_value
    await move_to_next_steal_value(update, context)


async def apply_steal_changes_from_query(query, context: ContextTypes.DEFAULT_TYPE):
    """Apply all steal changes from a callback query"""
    user_id = query.from_user.id
    old_name = bot_identity.get("name", "Iibrate")
    
    # Update bot name if provided
    if context.user_data.get('steal_new_name'):
        bot_identity["name"] = context.user_data['steal_new_name']
    
    # Update channel link if provided
    if context.user_data.get('steal_channel_link'):
        bot_identity["channel_link"] = context.user_data['steal_channel_link']
    
    # Update chat link if provided
    if context.user_data.get('steal_chat_link'):
        bot_identity["chat_link"] = context.user_data['steal_chat_link']
    
    # Update support username if provided
    if context.user_data.get('steal_support_username'):
        bot_identity["support_username"] = context.user_data['steal_support_username']
    
    save_data()
    
    # Build summary
    new_name = bot_identity.get("name", old_name)
    changes = []
    if context.user_data.get('steal_new_name'):
        changes.append(f"• Name: {old_name} → {new_name}")
    if context.user_data.get('steal_channel_link'):
        changes.append(f"• Channel: {bot_identity.get('channel_link', 'Not set')}")
    if context.user_data.get('steal_chat_link'):
        changes.append(f"• Chat: {bot_identity.get('chat_link', 'Not set')}")
    if context.user_data.get('steal_support_username'):
        changes.append(f"• Support: @{bot_identity.get('support_username', 'Not set')}")
    
    # Clear steal state
    context.user_data.pop('steal_state', None)
    context.user_data.pop('steal_new_name', None)
    context.user_data.pop('steal_channel_link', None)
    context.user_data.pop('steal_chat_link', None)
    context.user_data.pop('steal_support_username', None)
    context.user_data.pop('steal_name_yes', None)
    context.user_data.pop('steal_channel_yes', None)
    context.user_data.pop('steal_chat_yes', None)
    context.user_data.pop('steal_support_yes', None)
    context.user_data.pop('steal_waiting', None)
    
    changes_text = "\n".join(changes) if changes else "No changes made."
    
    await query.message.reply_html(
        f"✅ <b>Bot Rebranding Complete!</b>\n\n"
        f"📝 <b>Changes Applied:</b>\n"
        f"{changes_text}\n\n"
        f"All messages will now use the new identity!"
    )
    
    logger.info(f"Admin {user_id} rebranded bot: {old_name} → {new_name}")


async def apply_steal_changes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apply all steal changes"""
    user_id = update.effective_user.id
    old_name = bot_identity.get("name", "Iibrate")
    
    # Update bot name if provided
    if context.user_data.get('steal_new_name'):
        bot_identity["name"] = context.user_data['steal_new_name']
    
    # Update channel link if provided
    if context.user_data.get('steal_channel_link'):
        bot_identity["channel_link"] = context.user_data['steal_channel_link']
    
    # Update chat link if provided
    if context.user_data.get('steal_chat_link'):
        bot_identity["chat_link"] = context.user_data['steal_chat_link']
    
    # Update support username if provided
    if context.user_data.get('steal_support_username'):
        bot_identity["support_username"] = context.user_data['steal_support_username']
    
    save_data()
    
    # Build summary
    new_name = bot_identity.get("name", old_name)
    changes = []
    if context.user_data.get('steal_new_name'):
        changes.append(f"• Name: {old_name} → {new_name}")
    if context.user_data.get('steal_channel_link'):
        changes.append(f"• Channel: {bot_identity.get('channel_link', 'Not set')}")
    if context.user_data.get('steal_chat_link'):
        changes.append(f"• Chat: {bot_identity.get('chat_link', 'Not set')}")
    if context.user_data.get('steal_support_username'):
        changes.append(f"• Support: @{bot_identity.get('support_username', 'Not set')}")
    
    # Clear steal state
    context.user_data.pop('steal_state', None)
    context.user_data.pop('steal_new_name', None)
    context.user_data.pop('steal_channel_link', None)
    context.user_data.pop('steal_chat_link', None)
    context.user_data.pop('steal_support_username', None)
    context.user_data.pop('steal_name_yes', None)
    context.user_data.pop('steal_channel_yes', None)
    context.user_data.pop('steal_chat_yes', None)
    context.user_data.pop('steal_support_yes', None)
    context.user_data.pop('steal_waiting', None)
    
    changes_text = "\n".join(changes) if changes else "No changes made."
    
    # Get message object (could be from update.message or update.callback_query.message)
    message = update.message
    if not message and update.callback_query:
        message = update.callback_query.message
    
    if message:
        await message.reply_html(
            f"✅ <b>Bot Rebranding Complete!</b>\n\n"
            f"📝 <b>Changes Applied:</b>\n"
            f"{changes_text}\n\n"
            f"All messages will now use the new identity!"
        )
    
    logger.info(f"Admin {user_id} rebranded bot: {old_name} → {new_name}")


@handle_errors
async def handle_steal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle steal command inline button callbacks"""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    data = query.data
    
    if not is_admin(user_id):
        await query.answer("❌ Admin only!", show_alert=True)
        return
    
    # Handle name yes/no
    if data == "steal_name_yes":
        context.user_data['steal_name_yes'] = True
        await show_next_steal_question(query, context)
        await query.answer("✅ Will change bot name")
        return
    
    elif data == "steal_name_no":
        context.user_data['steal_name_yes'] = False
        await show_next_steal_question(query, context)
        await query.answer("❌ Bot name skipped")
        return
    
    # Handle channel yes/no
    elif data == "steal_channel_yes":
        context.user_data['steal_channel_yes'] = True
        await show_next_steal_question(query, context)
        await query.answer("✅ Will change channel link")
        return
    
    elif data == "steal_channel_no":
        context.user_data['steal_channel_yes'] = False
        await show_next_steal_question(query, context)
        await query.answer("❌ Channel link skipped")
        return
    
    # Handle chat yes/no
    elif data == "steal_chat_yes":
        context.user_data['steal_chat_yes'] = True
        await show_next_steal_question(query, context)
        await query.answer("✅ Will change chat link")
        return
    
    elif data == "steal_chat_no":
        context.user_data['steal_chat_yes'] = False
        await show_next_steal_question(query, context)
        await query.answer("❌ Chat link skipped")
        return
    
    # Handle support yes/no
    elif data == "steal_support_yes":
        context.user_data['steal_support_yes'] = True
        await show_next_steal_question(query, context)
        await query.answer("✅ Will change support username")
        return
    
    elif data == "steal_support_no":
        context.user_data['steal_support_yes'] = False
        await show_next_steal_question(query, context)
        await query.answer("❌ Support username skipped")
        return


async def show_next_steal_question(query, context: ContextTypes.DEFAULT_TYPE):
    """Show the next yes/no question in the steal flow"""
    try:
        if 'steal_name_yes' not in context.user_data:
            # Ask about name
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes", callback_data="steal_name_yes"),
                    InlineKeyboardButton("❌ No", callback_data="steal_name_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🎭 <b>Bot Rebranding</b>\n\n"
                "📝 <b>Do you want to change the bot name?</b>\n"
                "(This replaces 'Iibrate' everywhere)",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        elif 'steal_channel_yes' not in context.user_data:
            # Ask about channel
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes", callback_data="steal_channel_yes"),
                    InlineKeyboardButton("❌ No", callback_data="steal_channel_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            name_status = "✅ Name: Will change" if context.user_data.get('steal_name_yes') else "❌ Name: Skipped"
            await query.edit_message_text(
                f"{name_status}\n\n"
                "📝 <b>Do you want to change the channel link?</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        elif 'steal_chat_yes' not in context.user_data:
            # Ask about chat
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes", callback_data="steal_chat_yes"),
                    InlineKeyboardButton("❌ No", callback_data="steal_chat_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            name_status = "✅ Name: Will change" if context.user_data.get('steal_name_yes') else "❌ Name: Skipped"
            channel_status = "✅ Channel: Will change" if context.user_data.get('steal_channel_yes') else "❌ Channel: Skipped"
            await query.edit_message_text(
                f"{name_status}\n{channel_status}\n\n"
                "📝 <b>Do you want to change the chat link?</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        elif 'steal_support_yes' not in context.user_data:
            # Ask about support
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes", callback_data="steal_support_yes"),
                    InlineKeyboardButton("❌ No", callback_data="steal_support_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            name_status = "✅ Name: Will change" if context.user_data.get('steal_name_yes') else "❌ Name: Skipped"
            channel_status = "✅ Channel: Will change" if context.user_data.get('steal_channel_yes') else "❌ Channel: Skipped"
            chat_status = "✅ Chat: Will change" if context.user_data.get('steal_chat_yes') else "❌ Chat: Skipped"
            await query.edit_message_text(
                f"{name_status}\n{channel_status}\n{chat_status}\n\n"
                "📝 <b>Do you want to change the support username?</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        else:
            # All questions answered, start collecting data
            # Check what values we need to collect
            needs_name = context.user_data.get('steal_name_yes') and not context.user_data.get('steal_new_name')
            needs_channel = context.user_data.get('steal_channel_yes') and not context.user_data.get('steal_channel_link')
            needs_chat = context.user_data.get('steal_chat_yes') and not context.user_data.get('steal_chat_link')
            needs_support = context.user_data.get('steal_support_yes') and not context.user_data.get('steal_support_username')
            
            # If nothing needs to be collected, apply changes
            if not needs_name and not needs_channel and not needs_chat and not needs_support:
                await apply_steal_changes_from_query(query, context)
                return
            
            # Set state to collecting all values
            context.user_data['steal_state'] = 'collecting_all'
            
            # Show summary of what will be collected
            prompt_parts = []
            if needs_name:
                prompt_parts.append("📝 Bot name")
            if needs_channel:
                prompt_parts.append("📝 Channel link")
            if needs_chat:
                prompt_parts.append("📝 Chat link")
            if needs_support:
                prompt_parts.append("📝 Support username")
            
            await query.edit_message_text(
                f"✅ <b>All questions answered!</b>\n\n"
                f"<b>I need the following values:</b>\n" + "\n".join(prompt_parts) + "\n\n"
                f"<b>I'll ask for them one by one. Send the first value now:</b>",
                parse_mode=ParseMode.HTML
            )
            
            # Set waiting state for the first needed value and prompt
            if needs_name:
                context.user_data['steal_waiting'] = 'name'
                await query.message.reply_html("📝 <b>Send the bot name:</b>")
            elif needs_channel:
                context.user_data['steal_waiting'] = 'channel'
                await query.message.reply_html("📝 <b>Send the channel link:</b>\n\nFormat: https://t.me/channelname or @channelname")
            elif needs_chat:
                context.user_data['steal_waiting'] = 'chat'
                await query.message.reply_html("📝 <b>Send the chat link:</b>\n\nFormat: https://t.me/chatname or @chatname")
            elif needs_support:
                context.user_data['steal_waiting'] = 'support'
                await query.message.reply_html("📝 <b>Send the support username:</b> (without @)")
    except Exception as e:
        logger.error(f"Error in show_next_steal_question: {e}")
        try:
            await query.answer("❌ An error occurred. Please try again.", show_alert=True)
        except:
            pass


@handle_errors
async def handle_broadcast_capture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture any message from admin when broadcast mode is active."""
    user_id = update.effective_user.id
    if user_id not in broadcast_waiting:
        return
    if update.effective_chat.type != "private":
        return
    if not is_admin(user_id):
        broadcast_waiting.discard(user_id)
        return
    
    await perform_broadcast(update, context, update.message)
    broadcast_waiting.discard(user_id)


@handle_errors
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing operation"""
    user_id = update.effective_user.id
    
    cancelled = False
    
    if context.user_data.get('waiting_for_video'):
        context.user_data['waiting_for_video'] = False
        cancelled = True
    
    if context.user_data.get('waiting_for_custom_amount'):
        context.user_data['waiting_for_custom_amount'] = False
        cancelled = True
    
    if context.user_data.get('withdraw_state'):
        context.user_data['withdraw_state'] = None
        context.user_data['withdraw_amount'] = None
        context.user_data['withdraw_address'] = None
        cancelled = True
    
    # Cancel gift process
    if context.user_data.get('gift_state'):
        context.user_data['gift_state'] = None
        context.user_data['gift_target_user_id'] = None
        context.user_data['gift_target_username'] = None
        cancelled = True

    # Cancel broadcast wait
    if user_id in broadcast_waiting:
        broadcast_waiting.discard(user_id)
        cancelled = True
    
    if cancelled:
        await update.message.reply_html("✅ Operation cancelled.")
    else:
        await update.message.reply_html("ℹ️ Nothing to cancel.")


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
                f"✅ Tipped <b>{tip_amount}⭐</b> to {recipient_link}"
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
            f"✅ Tipped <b>{tip_amount}⭐</b> to {recipient_link}"
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
    
    # Check if user is banned
    if is_banned(user_id):
        return  # Silently ignore banned users
    
    # Check for start parameters (e.g., /start withdraw, /start deposit, /start ref-CODE)
    if context.args and len(context.args) > 0:
        start_param = context.args[0].lower()
        if start_param == "withdraw":
            # Redirect to withdraw command
            await withdraw_command(update, context)
            return
        elif start_param == "deposit":
            # Redirect to deposit command
            await deposit_command(update, context)
            return
        elif start_param == "support":
            # Redirect to support command
            await support_command(update, context)
            return
        elif start_param.startswith("ref-"):
            # Handle referral code
            try:
                ref_code = start_param.replace("ref-", "").strip()
                if ref_code and ref_code in referral_code_to_user:
                    referrer_id = referral_code_to_user[ref_code]
                    # Only set referrer if user doesn't already have one and isn't referring themselves
                    if user_id not in user_referrers and user_id != referrer_id:
                        user_referrers[user_id] = referrer_id
                        user_referrals[referrer_id].add(user_id)
                        save_data()
                        logger.info(f"User {user_id} joined via referral code {ref_code} from user {referrer_id}")
            except Exception as e:
                logger.error(f"Error processing referral code: {e}", exc_info=True)
    
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
    
    # Get bot identity
    bot_name = bot_identity.get("name", "Iibrate")
    channel_link_raw = bot_identity.get("channel_link", "https://t.me/Iibrate")
    chat_link_raw = bot_identity.get("chat_link", "https://t.me/librateds")
    support_username = bot_identity.get("support_username", "Iibratesupport")
    
    # Format channel link (convert @username to https://t.me/username)
    if channel_link_raw.startswith('@'):
        channel_link = f"https://t.me/{channel_link_raw[1:]}"
    elif not channel_link_raw.startswith('http'):
        channel_link = f"https://t.me/{channel_link_raw.replace('@', '')}"
    else:
        channel_link = channel_link_raw
    
    # Format chat link (convert @username to https://t.me/username)
    if chat_link_raw.startswith('@'):
        chat_link = f"https://t.me/{chat_link_raw[1:]}"
    elif not chat_link_raw.startswith('http'):
        chat_link = f"https://t.me/{chat_link_raw.replace('@', '')}"
    else:
        chat_link = chat_link_raw
    
    # Format support link
    if support_username.startswith('@'):
        support_link = f"https://t.me/{support_username[1:]}"
    else:
        support_link = f"https://t.me/{support_username}"
    
    welcome_text = (
        f"🐱 <b>Welcome to {bot_name} Game{admin_badge}</b>\n\n"
        f"⭐️ {bot_name} Game is the best online mini-games on Telegram\n\n"
        f"📢 <b>How to start winning?</b>\n\n"
        f"1. Make sure you have a balance. You can top up using the \"Deposit\" button.\n\n"
        f"2. Join one of our groups from the {bot_name} catalog.\n\n"
        f"3. Type /play and start playing!\n\n\n"
        f"💵 Balance: ${balance_usd:.2f}\n"
        f"👑 Game turnover: ${turnover:.2f}\n\n"
        f"🌐 <b>About us</b>\n"
        f"<a href='{channel_link}'>Channel</a> | <a href='{chat_link}'>Chat</a> | <a href='{support_link}'>Support</a>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play", callback_data="show_games")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent = await update.message.reply_html(welcome_text, reply_markup=reply_markup, disable_web_page_preview=True)
    register_menu_owner(sent, user_id)


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
    
    sent = await update.message.reply_html(
        "🎮 <b>Select a game to play:</b>\n\n"
        "🎲 <b>Dice</b> - Roll the dice and beat the bot!\n"
        "🎳 <b>Bowling</b> - Strike your way to victory!\n"
        "🎯 <b>Darts</b> - Aim for the bullseye!\n"
        "⚽ <b>Football</b> - Score goals and win!\n"
        "🏀 <b>Basketball</b> - Shoot hoops for stars!",
        reply_markup=reply_markup
    )
    register_menu_owner(sent, user_id)


# ==================== CASINO LEVELS SYSTEM ====================

def get_user_level(total_bets_usd):
    """Calculate user's level based on total bets in USD"""
    try:
        # Ensure total_bets_usd is a valid number
        if not isinstance(total_bets_usd, (int, float)):
            total_bets_usd = 0.0
        total_bets_usd = max(0.0, float(total_bets_usd))
        
        level = 0
        for lvl, threshold in sorted(LEVEL_THRESHOLDS.items(), reverse=True):
            if total_bets_usd >= threshold:
                level = lvl
                break
        return max(0, min(25, level))
    except Exception as e:
        logger.error(f"Error in get_user_level: {e}", exc_info=True)
        return 0


def get_level_progress(total_bets_usd, current_level):
    """Calculate progress percentage to next level"""
    try:
        # Ensure inputs are valid
        if not isinstance(total_bets_usd, (int, float)):
            total_bets_usd = 0.0
        total_bets_usd = max(0.0, float(total_bets_usd))
        current_level = int(max(0, min(25, current_level)))
        
        if current_level >= 25:  # MAX LEVEL
            return 100
        
        current_threshold = LEVEL_THRESHOLDS.get(current_level, 0)
        next_threshold = LEVEL_THRESHOLDS.get(current_level + 1)
        
        if next_threshold is None or next_threshold == current_threshold:
            return 100
        
        if next_threshold - current_threshold == 0:
            return 100
        
        progress = ((total_bets_usd - current_threshold) / (next_threshold - current_threshold)) * 100
        return max(0, min(100, progress))
    except Exception as e:
        logger.error(f"Error in get_level_progress: {e}", exc_info=True)
        return 0


def create_progress_bar(percentage, length=20):
    """Create a progress bar with filled and empty blocks"""
    try:
        percentage = float(percentage) if percentage else 0.0
        percentage = max(0, min(100, percentage))
        filled = int((percentage / 100) * length)
        empty = max(0, length - filled)
        return "▮" * filled + "▯" * empty
    except Exception:
        return "▯" * length


def format_level_display(user_id, username=None):
    """Format the level display for a user"""
    profile = get_or_create_profile(user_id, username)
    total_bets = profile.get('total_bets', 0.0)
    total_bets_usd = total_bets * STARS_TO_USD
    
    current_level = get_user_level(total_bets_usd)
    # Ensure level is within valid range
    current_level = max(0, min(25, current_level))
    level_info = CASINO_LEVELS.get(current_level, CASINO_LEVELS[0])
    progress = get_level_progress(total_bets_usd, current_level)
    
    # Current level features
    current_rakeback = level_info.get('rakeback', 5.0)
    current_weekly = level_info.get('weekly_mult', 1.09)
    
    # Next level info
    if current_level < 25:
        next_level = current_level + 1
        next_level_info = CASINO_LEVELS.get(next_level)
        if not next_level_info:
            next_level_info = CASINO_LEVELS[25]  # Fallback to max level
        next_rakeback = next_level_info.get('rakeback', current_rakeback)
        next_weekly = next_level_info.get('weekly_mult', current_weekly)
        level_up_bonus = next_level_info.get('level_up_bonus', 0)
        next_level_name = next_level_info.get('name', 'MAX LEVEL')
    else:
        next_level = None
        next_level_name = "MAX LEVEL"
        next_rakeback = current_rakeback
        next_weekly = current_weekly
        level_up_bonus = 0
    
    progress_bar = create_progress_bar(progress)
    
    text = f"Your profile Level: <b>{level_info.get('name', 'Steel')} (Lvl {current_level})</b>\n"
    text += f"Progress: <b>{progress:.1f}%</b> → {next_level_name}\n"
    text += f"{progress_bar}\n\n"
    
    text += f"<b>[{level_info.get('name', 'Steel')}] features:</b>\n"
    text += f"Rakeback: <b>{current_rakeback}%</b>\n"
    text += f"Weekly bonus: <b>{current_weekly}x</b>\n\n"
    
    if current_level < 25:
        text += f"<b>[{next_level_name}] features:</b>\n"
        text += f"Level-Up bonus: <b>${level_up_bonus}</b>\n"
        text += f"Rakeback: <b>{current_rakeback}%</b> → <b>{next_rakeback}%</b>\n"
        text += f"Weekly bonus: <b>{current_weekly}x</b> → <b>{next_weekly}x</b>\n"
    
    return text


@handle_errors
async def levels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's level and all available levels"""
    try:
        user = update.effective_user
        user_id = user.id
        
        profile = get_or_create_profile(user_id, user.username or user.first_name)
        total_bets = profile.get('total_bets', 0.0)
        
        # Ensure total_bets is a valid number
        try:
            total_bets = float(total_bets) if total_bets else 0.0
        except (ValueError, TypeError):
            total_bets = 0.0
        
        total_bets_usd = total_bets * STARS_TO_USD
        
        # Initialize all variables with defaults
        current_level = 0
        level_info = CASINO_LEVELS[0]
        progress = 0.0
        current_rakeback = 5.0
        current_weekly = 1.09
        next_rakeback = 6.5
        next_weekly = 1.09
        level_up_bonus = 5
        next_level_name = "Iron I"
        level_name = "Steel"
        
        try:
            current_level = get_user_level(total_bets_usd)
            # Ensure level is within valid range
            current_level = max(0, min(25, int(current_level)))
            level_info = CASINO_LEVELS.get(current_level)
            if not level_info:
                level_info = CASINO_LEVELS[0]
            
            progress = get_level_progress(total_bets_usd, current_level)
            if progress is None:
                progress = 0.0
            progress = float(progress)
            
            # Current level features
            current_rakeback = float(level_info.get('rakeback', 5.0))
            current_weekly = float(level_info.get('weekly_mult', 1.09))
            level_name = str(level_info.get('name', 'Steel'))
            
            # Next level info
            if current_level < 25:
                next_level = current_level + 1
                next_level_info = CASINO_LEVELS.get(next_level)
                if next_level_info:
                    next_rakeback = float(next_level_info.get('rakeback', current_rakeback))
                    next_weekly = float(next_level_info.get('weekly_mult', current_weekly))
                    level_up_bonus = int(next_level_info.get('level_up_bonus', 0))
                    next_level_name = str(next_level_info.get('name', 'MAX LEVEL'))
                else:
                    next_level_name = "MAX LEVEL"
                    next_rakeback = current_rakeback
                    next_weekly = current_weekly
                    level_up_bonus = 0
            else:
                next_level_name = "MAX LEVEL"
                next_rakeback = current_rakeback
                next_weekly = current_weekly
                level_up_bonus = 0
        except Exception as e:
            logger.error(f"Error calculating level info: {e}", exc_info=True)
            # Use defaults already set above
        
        try:
            progress_bar = create_progress_bar(progress)
            if not progress_bar:
                progress_bar = "▯" * 20
        except Exception:
            progress_bar = "▯" * 20
        
        # Build the message text
        try:
            text = f"Your profile Level: <b>{level_name} (Lvl {current_level})</b>\n"
            text += f"Progress: <b>{progress:.1f}%</b> → {next_level_name}\n"
            text += f"{progress_bar}\n\n"
            
            text += f"<b>[{level_name}] features:</b>\n"
            text += f"Rakeback: <b>{current_rakeback}%</b>\n"
            text += f"Weekly bonus: <b>{current_weekly}x</b>\n\n"
            
            if current_level < 25:
                text += f"<b>[{next_level_name}] features:</b>\n"
                text += f"Level-Up bonus: <b>${level_up_bonus}</b>\n"
                text += f"Rakeback: <b>{current_rakeback}%</b> → <b>{next_rakeback}%</b>\n"
                text += f"Weekly bonus: <b>{current_weekly}x</b> → <b>{next_weekly}x</b>\n\n"
            
            text += "Use /levels to see all the rank levels, benefits and bonuses"
            
            await update.message.reply_html(text)
        except Exception as e:
            logger.error(f"Error formatting level text: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"Error in levels_command: {e}", exc_info=True)
        await update.message.reply_html(
            "❌ <b>An error occurred while displaying your level.</b>\n\n"
            "Please try again later."
        )


@handle_errors
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    profile = get_or_create_profile(user_id, user.username or user.first_name)
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    admin_badge = " 👑" if is_admin(user_id) else ""
    user_link = get_user_link(user_id, user.first_name)
    
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
    
    try:
        total_bets = profile.get('total_bets', 0)
        total_bets = float(total_bets) if total_bets else 0.0
    except (ValueError, TypeError):
        total_bets = 0.0
    
    try:
        total_wins = profile.get('total_wins', 0)
        total_wins = float(total_wins) if total_wins else 0.0
    except (ValueError, TypeError):
        total_wins = 0.0
    
    total_bets_usd = total_bets * STARS_TO_USD
    total_wins_usd = total_wins * STARS_TO_USD
    
    # Get level information with error handling
    try:
        current_level = get_user_level(total_bets_usd)
        # Ensure level is within valid range
        current_level = max(0, min(25, current_level))
        level_info = CASINO_LEVELS.get(current_level, CASINO_LEVELS[0])
        progress = get_level_progress(total_bets_usd, current_level)
        
        if current_level < 25:
            next_level_info = CASINO_LEVELS.get(current_level + 1)
            if next_level_info:
                next_level_name = next_level_info.get('name', 'MAX LEVEL')
            else:
                next_level_name = "MAX LEVEL"
        else:
            next_level_name = "MAX LEVEL"
        
        progress_bar = create_progress_bar(progress)
        level_name = level_info.get('name', 'Steel')
    except Exception as e:
        logger.error(f"Error calculating level in profile: {e}", exc_info=True)
        # Fallback to default values
        current_level = 0
        level_name = "Steel"
        next_level_name = "Iron I"
        progress = 0
        progress_bar = create_progress_bar(0)
    profile_text = (
        f"📢 <b>Profile{admin_badge}</b>\n\n"
        f"👤 User: {user_link}\n"
        f"ℹ️ User ID: <code>{user_id}</code>\n"
        f"💵 Balance: ${balance_usd:.2f}\n\n"
        f"Your profile Level: <b>{level_name} (Lvl {current_level})</b>\n"
        f"Progress: <b>{progress:.1f}%</b> → {next_level_name}\n"
        f"{progress_bar}\n\n"
        f"⚡️ Total games: {profile.get('total_games', 0)}\n"
        f"Total bets: ${total_bets_usd:.2f}\n"
        f"Total wins: ${total_wins_usd:.2f}\n\n"
        f"🎲 Favorite game: {fav_game_display}\n"
        f"🎉 Biggest win: {biggest_win_display}\n\n"
        f"🕒 Registration date: {reg_date_str}"
    )
    
    await update.message.reply_html(profile_text)


# Old progress bar function removed - using the new one for levels


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
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboards: top wins, games played, win rate, bankroll."""
    user = update.effective_user
    user_id = user.id
    get_or_create_profile(user_id, user.username or user.first_name)
    
    if not user_profiles:
        await update.message.reply_html("ℹ️ No players yet. Play a game to appear on the leaderboard!")
        return
    
    def top_by(key_fn, limit=5):
        return sorted(user_profiles.items(), key=key_fn, reverse=True)[:limit]
    
    # Top Total Wins (Stars)
    top_wins = top_by(lambda item: item[1].get('total_wins', 0))
    win_lines = []
    for pos, (uid, profile) in enumerate(top_wins, start=1):
        display = format_user_display(uid, profile)
        stars_won = int(profile.get('total_wins', 0))
        win_lines.append(f"{pos}. {display} — {stars_won} ⭐")
    
    # Top Games Played
    top_games = top_by(lambda item: item[1].get('total_games', 0))
    game_lines = []
    for pos, (uid, profile) in enumerate(top_games, start=1):
        display = format_user_display(uid, profile)
        games = profile.get('total_games', 0)
        game_lines.append(f"{pos}. {display} — {games} games")
    
    # Top Win Rate (min 5 games)
    eligible = [
        (uid, p) for uid, p in user_profiles.items()
        if p.get('total_games', 0) >= 5
    ]
    win_rate_sorted = sorted(
        eligible,
        key=lambda item: (
            (item[1].get('games_won', 0) / item[1].get('total_games', 1)) if item[1].get('total_games', 0) > 0 else 0,
            item[1].get('total_games', 0)
        ),
        reverse=True
    )[:5]
    rate_lines = []
    for pos, (uid, profile) in enumerate(win_rate_sorted, start=1):
        display = format_user_display(uid, profile)
        total_games = profile.get('total_games', 0)
        wins = profile.get('games_won', 0)
        rate = (wins / total_games * 100) if total_games > 0 else 0
        rate_lines.append(f"{pos}. {display} — {rate:.1f}% ({total_games} games)")
    
    # Casino Bankroll (sum of non-admin user balances)
    bankroll_usd = casino_bankroll_usd
    
    leaderboard_text = "🏆 <b>Leaderboards</b>\n"
    leaderboard_text += "💰 <b>Top Total Wins (Stars)</b>\n" + ("\n".join(win_lines) if win_lines else "No data") + "\n\n"
    leaderboard_text += "🎮 <b>Top Games Played</b>\n" + ("\n".join(game_lines) if game_lines else "No data") + "\n\n"
    leaderboard_text += "📈 <b>Top Win Rate (min 5 games)</b>\n" + ("\n".join(rate_lines) if rate_lines else "No data (min 5 games)") + "\n\n"
    leaderboard_text += f"🏦 <b>Casino Bankroll:</b> ${bankroll_usd:,.2f}"
    
    await update.message.reply_html(leaderboard_text)


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
        f"🎁 <b>Weekly Bonus:</b>\n"
        f"Add '{BOT_USERNAME}' to your profile name and use /weekly to claim your weekly bonus!\n\n"
        "🏆 <b>Leaderboard:</b>\n"
        "Use /leaderboard to see the top players.\n\n"
        "🏦 <b>Bankroll:</b>\n"
        "Use /hb or /housebal to view the casino bankroll.\n\n"
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
            "/video - Set withdraw video\n"
            "/video status - Check video status\n"
            "/video remove - Remove video\n"
            "/broadcast or /bc - Send a message to all users\n"
        )
    
    await update.message.reply_html(help_text)


@handle_errors
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    balance_usd = balance * STARS_TO_USD
    
    admin_note = " (Admin - Unlimited)" if is_admin(user_id) else ""
    
    # Get bot username for URL buttons
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username if bot_info.username else "Iibratebot"
    except Exception:
        bot_username = "Iibratebot"  # Fallback
    
    keyboard = [
        [
            InlineKeyboardButton("💳 Deposit", url=f"https://t.me/{bot_username}?start=deposit"),
            InlineKeyboardButton("💎 Withdraw", url=f"https://t.me/{bot_username}?start=withdraw"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent = await update.message.reply_html(
        f"💰 <b>Your Balance</b>{admin_note}\n\n"
        f"⭐ Stars: <b>{balance:,} ⭐</b>\n"
        f"💵 USD: <b>${balance_usd:.2f}</b>",
        reply_markup=reply_markup
    )
    register_menu_owner(sent, user_id)


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
    sent = await update.message.reply_html(
        "💳 <b>Select deposit amount:</b>",
        reply_markup=reply_markup
    )
    register_menu_owner(sent, update.effective_user.id)


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
    
    # Send with video if set, otherwise just text
    sent = None
    if withdraw_video_file_id:
        try:
            sent = await update.message.reply_video(
                video=withdraw_video_file_id,
                caption=welcome_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send withdraw video: {e}")
            # Fallback to text if video fails
            sent = await update.message.reply_html(welcome_text, reply_markup=reply_markup)
    else:
        sent = await update.message.reply_html(welcome_text, reply_markup=reply_markup)
    
    if sent:
        register_menu_owner(sent, user_id)


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
            sent = await update.message.reply_html(
                f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                f"💰 Bet: <b>{bet_amount} ⭐</b>\n\n"
                f"Select number of rounds:",
                reply_markup=reply_markup
            )
            register_menu_owner(sent, user_id)
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
        sent = await update.message.reply_html(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\n"
            f"Your balance: <b>{balance:,} ⭐</b>",
            reply_markup=reply_markup
        )
        register_menu_owner(sent, user_id)


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
        sent = await query.edit_message_text(
            f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
            f"💰 Choose your bet:\n"
            f"Your balance: <b>{balance:,} ⭐</b>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        register_menu_owner(sent, user_id)


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


def format_withdrawal_status(status):
    """Format withdrawal status for display"""
    status_map = {
        'on_hold': '⏳ Pending',
        'cancelled': '🚫 Cancelled',
        'completed': '✅ Completed',
        'draft': '📝 Draft'
    }
    return status_map.get(status, status)


def format_withdrawal_date(date_str):
    """Format withdrawal date for display"""
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%d.%m %H:%M")
        return str(date_str)
    except:
        return str(date_str)


@handle_errors
async def handle_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all support ticket callbacks"""
    global ticket_counter
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "support_create_ticket":
        # Ask which bot/topic
        keyboard = [
            [
                InlineKeyboardButton("💎 Withdraw", callback_data="support_topic_withdraw"),
                InlineKeyboardButton("❓ other topic", callback_data="support_topic_other")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Which bot do you need help with?",
            reply_markup=reply_markup
        )
        await query.answer()
        return
    
    elif data == "support_my_tickets":
        # Show user's tickets
        user_ticket_list = user_tickets.get(user_id, [])
        if not user_ticket_list:
            await query.edit_message_text(
                "🗒️ <b>My Tickets</b>\n\n"
                "You don't have any tickets yet.",
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return
        
        tickets_text = "🗒️ <b>My Tickets</b>\n\n"
        for idx, ticket in enumerate(user_ticket_list[-10:], 1):  # Show last 10 tickets
            ticket_id = ticket.get('ticket_id', 'N/A')
            topic = ticket.get('topic', 'Unknown')
            status = ticket.get('status', 'open')
            created = ticket.get('created', '')
            tickets_text += f"{idx}. Ticket #{ticket_id} - {topic} ({status})\n"
        
        await query.edit_message_text(tickets_text, parse_mode=ParseMode.HTML)
        await query.answer()
        return
    
    elif data == "support_topic_withdraw":
        # Show withdrawal history as inline buttons
        buttons = []
        
        # Get all withdrawals for user
        # user_withdrawals structure: {str(user_id): {withdrawal_data}}
        all_withdrawals = []
        
        # Check if user has a withdrawal stored
        user_withdrawal = user_withdrawals.get(str(user_id))
        if user_withdrawal and isinstance(user_withdrawal, dict) and 'exchange_id' in user_withdrawal:
            all_withdrawals.append(user_withdrawal)
        
        # Also check all withdrawals to find ones for this user
        # (in case structure is different or there are multiple)
        for key, withdrawal in user_withdrawals.items():
            if isinstance(withdrawal, dict) and 'exchange_id' in withdrawal:
                # If key is user_id, it's for that user
                try:
                    if int(key) == user_id:
                        if withdrawal not in all_withdrawals:
                            all_withdrawals.append(withdrawal)
                except:
                    pass
        
        # Sort by date (newest first)
        try:
            all_withdrawals.sort(key=lambda x: x.get('created', ''), reverse=True)
        except:
            pass
        
        # Limit to 20 withdrawals for display
        display_withdrawals = all_withdrawals[:20]
        
        if not display_withdrawals:
            await query.edit_message_text(
                "❌ <b>No withdrawals found.</b>\n\n"
                "You don't have any withdrawal history.",
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return
        
        # Build text and buttons
        page_num = 1
        withdrawal_text = f"Select the exchange you need help with.\nPage {page_num}.\n\n"
        
        for withdrawal in display_withdrawals:
            exchange_id = withdrawal.get('exchange_id', 'N/A')
            stars = withdrawal.get('stars', 0)
            ton_amount = withdrawal.get('ton_amount', 0)
            status = withdrawal.get('status', 'draft')
            created = withdrawal.get('created', '')
            
            status_display = format_withdrawal_status(status)
            
            # Parse date format: "2024-12-07 06:27" -> "07.12 06:27"
            try:
                if isinstance(created, str):
                    if ' ' in created:
                        date_part, time_part = created.split(' ', 1)
                        year, month, day = date_part.split('-')
                        hour, minute = time_part.split(':')[:2]
                        date_display = f"{day}.{month} {hour}:{minute}"
                    else:
                        date_display = created
                else:
                    date_display = str(created)
            except:
                date_display = str(created)
            
            # Format: Two lines per withdrawal
            # Line 1: "Date — Status · Stars → TON · Date"
            # Line 2: "#ExchangeID — Status · Stars → TON · Date"
            withdrawal_text += f"{date_display} — {status_display} · {stars:,} STARS → {ton_amount:.2f} TON · {date_display}\n#{exchange_id} — {status_display} · {stars:,} STARS → {ton_amount:.2f} TON · {date_display}\n"
            
            # Create button for each withdrawal
            button_text = f"#{exchange_id} - {status_display}"
            if len(button_text) > 64:  # Telegram button text limit
                button_text = f"#{exchange_id}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"support_withdraw_{exchange_id}")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(withdrawal_text, reply_markup=reply_markup)
        await query.answer()
        return
    
    elif data.startswith("support_withdraw_"):
        # User selected a withdrawal
        exchange_id = data.replace("support_withdraw_", "")
        
        # Store selected withdrawal in context
        context.user_data['support_selected_withdrawal'] = exchange_id
        
        keyboard = [
            [InlineKeyboardButton("🧊 My transaction is frozen", callback_data="support_issue_frozen")],
            [InlineKeyboardButton("🔒 My account is locked", callback_data="support_issue_locked")],
            [InlineKeyboardButton("💸 I didn't receive ton", callback_data="support_issue_not_received")],
            [InlineKeyboardButton("❓ Another question", callback_data="support_issue_other")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👋 Hello! What seems to be the problem?",
            reply_markup=reply_markup
        )
        await query.answer()
        return
    
    elif data in ["support_issue_frozen", "support_issue_locked", "support_issue_other"]:
        # Create ticket and send wait message
        ticket_id = ticket_counter
        ticket_counter += 1
        
        issue_type = {
            "support_issue_frozen": "Transaction frozen",
            "support_issue_locked": "Account locked",
            "support_issue_other": "Another question"
        }.get(data, "Unknown issue")
        
        # Create ticket
        if user_id not in user_tickets:
            user_tickets[user_id] = []
        
        ticket = {
            'ticket_id': ticket_id,
            'user_id': user_id,
            'topic': 'Withdraw',
            'issue': issue_type,
            'withdrawal_id': context.user_data.get('support_selected_withdrawal'),
            'status': 'open',
            'created': datetime.now().isoformat()
        }
        
        user_tickets[user_id].append(ticket)
        save_data()
        
        await query.edit_message_text(
            "⏳ Please wait—our managers will contact you as soon as possible to resolve your issue."
        )
        await query.answer()
        return
    
    elif data == "support_issue_not_received":
        # Ask how they topped up
        keyboard = [
            [
                InlineKeyboardButton("1 Fragment", callback_data="support_topup_fragment"),
                InlineKeyboardButton("2 Apple/Google Store", callback_data="support_topup_store")
            ],
            [
                InlineKeyboardButton("3 Premium Bot", callback_data="support_topup_premium"),
                InlineKeyboardButton("4 Selling Gifts", callback_data="support_topup_gifts")
            ],
            [
                InlineKeyboardButton("5 Purchased in another bot", callback_data="support_topup_other_bot"),
                InlineKeyboardButton("6 Other", callback_data="support_topup_other")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "How did you top up stars to your account?",
            reply_markup=reply_markup
        )
        await query.answer()
        return
    
    elif data in ["support_topup_fragment", "support_topup_store", "support_topup_premium", 
                  "support_topup_gifts", "support_topup_other_bot", "support_topup_other"]:
        # All buttons (1-6): Ask for screen recording
        logger.info(f"Support topup callback received: {data} from user {user_id}")
        
        ticket_id = ticket_counter
        ticket_counter += 1
        
        topup_method = {
            "support_topup_fragment": "Fragment",
            "support_topup_store": "Apple/Google Store",
            "support_topup_premium": "Premium Bot",
            "support_topup_gifts": "Selling Gifts",
            "support_topup_other_bot": "Purchased in another bot",
            "support_topup_other": "Other"
        }.get(data, "Unknown")
        
        # Create ticket
        if user_id not in user_tickets:
            user_tickets[user_id] = []
        
        ticket = {
            'ticket_id': ticket_id,
            'user_id': user_id,
            'topic': 'Withdraw',
            'issue': "Didn't receive TON",
            'topup_method': topup_method,
            'withdrawal_id': context.user_data.get('support_selected_withdrawal'),
            'status': 'open',
            'waiting_for_video': True,  # Flag to track waiting for video
            'created': datetime.now().isoformat()
        }
        
        user_tickets[user_id].append(ticket)
        save_data()
        
        # Store ticket_id in context for video handler
        context.user_data['support_waiting_video_ticket_id'] = ticket_id
        
        # Answer callback and edit message
        try:
            await query.answer()
            await query.edit_message_text(
                "Please send a screen recording with all your star transactions."
            )
            logger.info(f"Successfully sent screen recording request for ticket {ticket_id}")
        except Exception as e:
            logger.error(f"Error in support topup handler: {e}", exc_info=True)
            # Try to send as new message if edit fails
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="Please send a screen recording with all your star transactions."
                )
            except Exception as e2:
                logger.error(f"Error sending message for support topup: {e2}", exc_info=True)
        return
    
    elif data == "support_topic_other":
        # Handle other topic
        ticket_id = ticket_counter
        ticket_counter += 1
        
        # Create ticket
        if user_id not in user_tickets:
            user_tickets[user_id] = []
        
        ticket = {
            'ticket_id': ticket_id,
            'user_id': user_id,
            'topic': 'Other',
            'status': 'open',
            'created': datetime.now().isoformat()
        }
        
        user_tickets[user_id].append(ticket)
        save_data()
        
        await query.edit_message_text(
            "⏳ Please wait—our managers will contact you as soon as possible to resolve your issue."
        )
        await query.answer()
        return


@handle_errors
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # Check if user is banned (allow admins)
    if is_banned(user_id) and not is_admin(user_id):
        await query.answer()
        return  # Silently ignore banned users
    
    # Callback ownership protection
    key = (query.message.chat_id, query.message.message_id)
    owner_id = menu_owners.get(key)
    if owner_id and owner_id != user_id:
        await query.answer("⚠️This is not your menu", show_alert=True)
        return
    
    try:
        # Handle steal command callbacks
        if data.startswith("steal_"):
            await query.answer()
            await handle_steal_callback(update, context)
            return
        
        # Handle support ticket callbacks
        if data.startswith("support_"):
            logger.info(f"Routing support callback: {data} to handle_support_callback")
            await handle_support_callback(update, context)
            return
        
        # Answer callback for other handlers
        await query.answer()
        
        # Handle repeat/double buttons
        if data == "game_repeat":
            await start_repeat_game(context, user_id, query.message.chat_id, double=False)
            return
        
        if data == "game_double":
            await start_repeat_game(context, user_id, query.message.chat_id, double=True)
            return
        
        # Handle weekly bonus redemption
        if data == "redeem_weekly_bonus":
            user = query.from_user
            
            # Check if it's Saturday
            if not is_saturday():
                await query.edit_message_text(
                    "❌ <b>No bonus available</b>",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Check if user has already claimed this Saturday
            last_claim = user_weekly_bonus_claimed.get(user_id)
            if last_claim:
                now = datetime.now()
                # Check if last claim was on a Saturday and it's the same date (same Saturday)
                if last_claim.weekday() == 5 and last_claim.date() == now.date():
                    await query.answer("❌ You have already claimed your weekly bonus today!", show_alert=True)
                    return
                # If last claim was on a Saturday but different date, allow (it's a new Saturday)
            
            # Check if user has bot name in profile
            bot_name = bot_identity.get("name", BOT_USERNAME)
            if not check_bot_name_in_profile(user):
                await query.answer(
                    f"❌ Add @{bot_name} to your profile name to claim the weekly bonus!",
                    show_alert=True
                )
                return
            
            # Give random weekly bonus
            weekly_bonus = get_weekly_bonus_amount()
            adjust_user_balance(user_id, weekly_bonus)
            user_weekly_bonus_claimed[user_id] = datetime.now()
            save_data()
            
            balance = get_user_balance(user_id)
            balance_usd = balance * STARS_TO_USD
            
            await query.edit_message_text(
                f"🎁 <b>Weekly Bonus Claimed Successfully!</b>\n\n"
                f"✅ We found <b>@{bot_name}</b> in your profile name!\n\n"
                f"💰 You received: <b>{weekly_bonus} ⭐</b>\n"
                f"💵 New Balance: <b>{balance:,} ⭐</b> (${balance_usd:.2f})\n\n"
                f"🎉 Thank you for supporting us!\n\n"
                f"⏰ Next weekly bonus available next Saturday!",
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"Weekly bonus claimed by user {user_id} ({user.first_name})")
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
            sent_dep = await query.edit_message_text(
                "💳 <b>Select deposit amount:</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_dep, user_id)
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
            
            # For callback, we need to handle video differently
            # If video is set, delete current message and send new one with video
            if withdraw_video_file_id:
                try:
                    await query.message.delete()
                    sent_msg = await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=withdraw_video_file_id,
                        caption=welcome_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    register_menu_owner(sent_msg, user_id)
                except Exception as e:
                    logger.error(f"Failed to send withdraw video in callback: {e}")
                    sent_edit = await query.edit_message_text(
                        welcome_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                    register_menu_owner(sent_edit, user_id)
            else:
                sent_edit = await query.edit_message_text(
                    welcome_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                register_menu_owner(sent_edit, user_id)
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
            
            sent_balance = await query.edit_message_text(
                f"💰 <b>Your Balance</b>{admin_note}\n\n"
                f"⭐ Stars: <b>{balance:,} ⭐</b>\n"
                f"💵 USD: <b>${balance_usd:.2f}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_balance, user_id)
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
            sent_show = await query.edit_message_text(
                "🎮 <b>Select a game to play:</b>\n\n"
                "🎲 <b>Dice</b> - Roll the dice and beat the bot!\n"
                "🎳 <b>Bowling</b> - Strike your way to victory!\n"
                "🎯 <b>Darts</b> - Aim for the bullseye!\n"
                "⚽ <b>Football</b> - Score goals and win!\n"
                "🏀 <b>Basketball</b> - Shoot hoops for stars!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_show, user_id)
            return
        
        if data.startswith("play_game_"):
            game_type = data.replace("play_game_", "")
            await start_game_from_callback(query, context, game_type)
            return
        
        if data == "start_withdraw":
            context.user_data['withdraw_state'] = 'waiting_amount'
            
            # Try to edit caption if it's a video message, otherwise edit text
            try:
                await query.edit_message_caption(
                    caption=f"💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                            f"Minimum: {MIN_WITHDRAWAL} ⭐\n"
                            f"Example: 100",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await query.edit_message_text(
                        f"💫 <b>Enter the number of ⭐️ to withdraw:</b>\n\n"
                        f"Minimum: {MIN_WITHDRAWAL} ⭐\n"
                        f"Example: 100",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to edit message for withdraw: {e}")
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
                f"📝 Reason: {bot_identity.get('name', 'Iibrate')} game rating is negative. Placed on 14-day hold."
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
            sent_bet = await query.edit_message_text(
                f"{game_info['icon']} <b>Select number of rounds:</b>\n"
                f"Bet: <b>{bet_amount} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_bet, user_id)
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
            sent_back_bet = await query.edit_message_text(
                f"{game_info['icon']} <b>{game_info['name']} Game</b>\n\n"
                f"💰 Choose your bet:\n"
                f"Your balance: <b>{balance:,} ⭐</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_back_bet, user_id)
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
            
            sent_rounds = await query.edit_message_text(
                f"{game_info['icon']} <b>Select throws per round:</b>{demo_tag}\n"
                f"Rounds: <b>{rounds}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_rounds, user_id)
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
            
            sent_throws = await query.edit_message_text(
                f"{game_info['icon']} <b>Who should roll first?{demo_tag}</b>\n\n"
                f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
                f"🔄 Rounds: <b>{rounds}</b>\n"
                f"🎯 Throws per round: <b>{throws}</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            register_menu_owner(sent_throws, user_id)
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
    
    # Check if user is banned
    if is_banned(user_id):
        return  # Silently ignore banned users
    
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
            
            sent = await message.reply_html(
                f"<b>Final Round Results:</b>\n\n"
                f"👤 Your total: <b>{user_round_total}</b>\n"
                f"🤖 Bot total: <b>{bot_round_total}</b>\n\n"
                f"{round_result}\n\n"
                f"📊 Final Score: You <b>{game.user_score}</b> - <b>{game.bot_score}</b> Bot\n\n"
                f"{result_text}\n\n"
                f"💰 Balance: <b>{balance:,} ⭐</b>",
                reply_markup=reply_markup
            )
            if reply_markup:
                register_menu_owner(sent, user_id)
            
            del user_games[user_id]


@handle_errors
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user is banned (allow admins and special flows)
    if is_banned(user_id) and not is_admin(user_id):
        # Allow admin flows even if admin is somehow banned (shouldn't happen)
        if not context.user_data.get('steal_state') and not context.user_data.get('waiting_for_bankroll') and not context.user_data.get('waiting_for_min_withdrawal'):
            return  # Silently ignore banned users
    
    text = (update.message.text or "").strip()
    
    # Handle steal command flow
    if context.user_data.get('steal_state'):
        await handle_steal_flow(update, context)
        return
    
    # Handle bankroll input from admin prompt
    if context.user_data.get('waiting_for_bankroll'):
        if not is_admin(user_id):
            context.user_data['waiting_for_bankroll'] = False
            await update.message.reply_html("❌ Only admins can set bankroll.")
            return
        try:
            amount = float(text)
            global casino_bankroll_usd
            casino_bankroll_usd = amount
            context.user_data['waiting_for_bankroll'] = False
            save_data()
            await update.message.reply_html(
                f"✅ Bankroll updated.\n\n🏦 Casino Bankroll\n💵 USD: ${casino_bankroll_usd:,.2f}"
            )
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid number (e.g., 2493.23).")
        return
    
    # Handle minimum withdrawal input (admin only)
    if context.user_data.get('waiting_for_min_withdrawal'):
        if not is_admin(user_id):
            context.user_data['waiting_for_min_withdrawal'] = False
            await update.message.reply_html("❌ Only admins can set minimum withdrawal.")
            return
        try:
            amount = int(text)
            if amount < 1:
                await update.message.reply_html("❌ Minimum withdrawal must be at least 1 ⭐")
                return
            global MIN_WITHDRAWAL
            MIN_WITHDRAWAL = amount
            context.user_data['waiting_for_min_withdrawal'] = False
            save_data()
            await update.message.reply_html(
                f"✅ <b>Minimum withdrawal updated!</b>\n\n"
                f"💰 New minimum: <b>{MIN_WITHDRAWAL} ⭐</b>"
            )
            logger.info(f"Admin {user_id} set minimum withdrawal to {MIN_WITHDRAWAL}")
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid integer number (e.g., 200).")
        return

    # Handle gift chat ID input (Step 2)
    if context.user_data.get('gift_state') == 'waiting_for_chat_id':
        await process_gift_chat_id(update, context, text)
        return
    
    # Handle "1" as payment shortcut after /pingme (Step 3 shortcut)
    if context.user_data.get('gift_state') == 'waiting_for_payment' and text.strip() == "1":
        if not is_admin(user_id):
            return
        # Treat "1" as payment confirmation - process gift automatically
        logger.info(f"Admin {user_id}: Received '1' as payment shortcut, processing gift")
        await update.message.reply_html("✅ <b>Payment confirmed!</b>\n\n🎁 <b>Processing gift...</b>")
        await process_gift_after_payment(update, context)
        return
    
    # Handle broadcast text (admin only, waiting flag set via /broadcast)
    if user_id in broadcast_waiting and update.effective_chat.type == "private":
        if not is_admin(user_id):
            broadcast_waiting.discard(user_id)
            return
        await perform_broadcast(update, context, update.message)
        broadcast_waiting.discard(user_id)
        return
    
    if context.user_data.get('waiting_for_custom_amount'):
        # Only respond in private chats (DM), not in groups
        if update.effective_chat.type != "private":
            return  # Silently ignore messages in groups
        
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
        # Only respond in private chats (DM), not in groups
        if update.effective_chat.type != "private":
            return  # Silently ignore messages in groups
        
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
        # Only respond in private chats (DM), not in groups
        if update.effective_chat.type != "private":
            return  # Silently ignore messages in groups
        
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
        
        sent_summary = await update.message.reply_html(
            f"📋 <b>Withdrawal Summary:</b>\n\n"
            f"⭐️ Stars: {stars_amount}\n"
            f"💎 TON: {ton_amount}\n"
            f"🏦 Address: <code>{text}</code>\n\n"
            f"Confirm withdrawal?",
            reply_markup=reply_markup
        )
        register_menu_owner(sent_summary, user_id)
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
    payload = payment.invoice_payload
    
    # Check if this is a gift payment
    if payload and payload.startswith('gift_payment_'):
        # This is a gift payment - process gift automatically
        logger.info(f"Admin {user_id}: Gift payment received, processing gift automatically")
        await process_gift_after_payment(update, context)
        return
    
    # Regular deposit payment
    adjust_user_balance(user_id, amount)
    balance = get_user_balance(user_id)
    
    await update.message.reply_html(
        f"✅ <b>Payment successful!</b>\n\n"
        f"💰 Added: <b>{amount} ⭐</b>\n"
        f"💳 New balance: <b>{balance:,} ⭐</b>"
    )


@handle_errors
async def wd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set minimum withdrawal amount (admin only)"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>You don't have permission to use this command.</b>")
        return
    
    # Check if admin provided amount directly
    if context.args and len(context.args) >= 1:
        try:
            amount = int(context.args[0])
            if amount < 1:
                await update.message.reply_html("❌ Minimum withdrawal must be at least 1 ⭐")
                return
            
            global MIN_WITHDRAWAL
            MIN_WITHDRAWAL = amount
            save_data()
            await update.message.reply_html(
                f"✅ <b>Minimum withdrawal updated!</b>\n\n"
                f"💰 New minimum: <b>{MIN_WITHDRAWAL} ⭐</b>"
            )
            logger.info(f"Admin {user_id} set minimum withdrawal to {MIN_WITHDRAWAL}")
            return
        except ValueError:
            await update.message.reply_html("❌ Please enter a valid integer number.")
            return
    
    # Prompt admin for amount
    context.user_data['waiting_for_min_withdrawal'] = True
    await update.message.reply_html(
        "💰 <b>Set Minimum Withdrawal</b>\n\n"
        f"Current minimum: <b>{MIN_WITHDRAWAL} ⭐</b>\n\n"
        "Send the new minimum withdrawal amount in stars (integer only).\n"
        "Example: 200"
    )


# Gift system configuration
GIFT_STARS = 15  # Telegram's gift limit
PAYMENT_STARS = 1  # Payment amount for gift process

@handle_errors
async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start gift process - Step 1: Ask for chat ID or username"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ You are not authorized")
        return
    
    # Reset any previous state
    context.user_data['gift_state'] = 'waiting_for_chat_id'
    context.user_data['gift_target_user_id'] = None
    context.user_data['gift_target_username'] = None
    
    await update.message.reply_html(
        "📬 <b>Please send the chat ID or username of the recipient</b>"
    )
    
    logger.info(f"Admin {user_id} started gift process - waiting for chat ID")


@handle_errors
async def pingme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hidden command - Step 3: Create payment invoice"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return  # Silently ignore non-admins
    
    # Delete the command message to hide it
    try:
        await update.message.delete()
    except Exception:
        pass
    
    # Check if target user is set (Step 2 completed)
    if context.user_data.get('gift_state') != 'waiting_for_pingme':
        await update.message.reply_html(
            "❌ <b>Please complete the gift process first.</b>\n\n"
            "Use /gift to start, then provide chat ID or username."
        )
        return
    
    target_user_id = context.user_data.get('gift_target_user_id')
    if not target_user_id:
        await update.message.reply_html("❌ Target user not set. Use /gift to start.")
        return
    
    # Create payment invoice for 1 Star
    try:
        prices = [LabeledPrice("Gift Payment", PAYMENT_STARS)]
        payload = f"gift_payment_{user_id}_{target_user_id}"
        
        await update.message.reply_invoice(
            title="🎁 Gift Payment",
            description="Payment for sending Telegram gift",
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="XTR",  # Telegram Stars currency
            prices=prices,
            start_parameter="gift"
        )
        
        # Inform admin about "1" shortcut
        await update.message.reply_html(
            "💡 <b>Tip:</b> You can also send <b>1</b> to confirm payment and process the gift automatically."
        )
        
        context.user_data['gift_state'] = 'waiting_for_payment'
        logger.info(f"Admin {user_id} created gift payment invoice for target {target_user_id}")
    except Exception as e:
        logger.error(f"Error creating gift payment invoice: {e}", exc_info=True)
        await update.message.reply_html(
            f"❌ <b>Failed to create payment invoice.</b>\n\n"
            f"Error: {str(e)}"
        )


@handle_errors
async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users (admin only)"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ You are not authorized")
        return
    
    try:
        # Get all users from profiles
        all_user_ids = list(user_profiles.keys())
        
        if not all_user_ids:
            await update.message.reply_html("📋 <b>User List</b>\n\nNo users found.")
            return
        
        # Sort by user ID
        all_user_ids.sort()
        
        # Check if pagination is needed (Telegram message limit is 4096 characters)
        total_users = len(all_user_ids)
        
        # Build user list
        user_list_text = f"📋 <b>User List</b>\n\n"
        user_list_text += f"Total users: <b>{total_users}</b>\n\n"
        
        # List users (limit to avoid message too long)
        max_users_per_message = 50
        users_to_show = all_user_ids[:max_users_per_message]
        
        for idx, uid in enumerate(users_to_show, 1):
            profile = user_profiles.get(uid, {})
            username = profile.get('username', '')
            display_name = profile.get('display_name', '')
            balance = get_user_balance(uid)
            
            # Format username display
            if username:
                user_display = f"@{username}"
            elif display_name:
                user_display = display_name
            else:
                user_display = f"User {uid}"
            
            # Check if banned
            banned_status = "🔨" if uid in banned_users else ""
            
            user_list_text += f"{idx}. <code>{uid}</code> - {user_display} {banned_status}\n"
        
        if total_users > max_users_per_message:
            user_list_text += f"\n... and {total_users - max_users_per_message} more users"
        
        await update.message.reply_html(user_list_text)
        
        logger.info(f"Admin {user_id} viewed user list ({total_users} users)")
        
    except Exception as e:
        logger.error(f"Error in user_command: {e}", exc_info=True)
        await update.message.reply_html(
            "❌ <b>An error occurred while displaying user list.</b>\n\n"
            "Please try again later."
        )


@handle_errors
async def com_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available commands for users"""
    if not update.message:
        return
    
    commands_text = (
        "📋 <b>Available Commands</b>\n\n"
        "<b>Basic Commands:</b>\n"
        "• /start - Start the bot\n"
        "• /help - Show help information\n"
        "• /cancel - Cancel current operation\n\n"
        "<b>Balance & Money:</b>\n"
        "• /balance or /bal - Check your balance\n"
        "• /deposit or /depo - Deposit stars\n"
        "• /withdraw - Withdraw stars to TON wallet\n\n"
        "<b>Games:</b>\n"
        "• /play - Start playing games\n\n"
        "<b>Profile & Stats:</b>\n"
        "• /profile - View your profile\n"
        "• /levels - View your level and progress\n"
        "• /history - View your game history\n"
        "• /leaderboard - View top players\n\n"
        "<b>Rewards:</b>\n"
        "• /weekly - Claim weekly bonus (Saturdays only)\n"
        "• /referral or /ref - View referral information\n\n"
        "<b>Social:</b>\n"
        "• /tip [amount] - Send stars to another user\n\n"
        "<b>Support:</b>\n"
        "• /support - Get help or create a support ticket\n\n"
        "💡 <b>Tip:</b> Use /help for more information about any command."
    )
    
    try:
        await update.message.reply_html(commands_text)
    except Exception as e:
        logger.error(f"Error in com_command: {e}", exc_info=True)
        # Fallback to plain text
        plain_text = (
            "📋 Available Commands\n\n"
            "Basic Commands:\n"
            "• /start - Start the bot\n"
            "• /help - Show help information\n"
            "• /cancel - Cancel current operation\n\n"
            "Balance & Money:\n"
            "• /balance or /bal - Check your balance\n"
            "• /deposit or /depo - Deposit stars\n"
            "• /withdraw - Withdraw stars to TON wallet\n\n"
            "Games:\n"
            "• /play - Start playing games\n\n"
            "Profile & Stats:\n"
            "• /profile - View your profile\n"
            "• /levels - View your level and progress\n"
            "• /history - View your game history\n"
            "• /leaderboard - View top players\n\n"
            "Rewards:\n"
            "• /weekly - Claim weekly bonus (Saturdays only)\n"
            "• /referral or /ref - View referral information\n\n"
            "Social:\n"
            "• /tip [amount] - Send stars to another user\n\n"
            "💡 Tip: Use /help for more information about any command."
        )
        await update.message.reply_text(plain_text)


@handle_errors
async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support command - create or view tickets"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    # Check if command is in group chat
    if not is_private_chat(update):
        keyboard = [
            [InlineKeyboardButton("Click here", url="https://t.me/Iibratebot?start=support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            "Please use this command with bot in private messages.",
            reply_markup=reply_markup
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✉️ create ticket", callback_data="support_create_ticket"),
            InlineKeyboardButton("🗒️ my ticket", callback_data="support_my_tickets")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        "Support answers in 1–5 minutes.",
        reply_markup=reply_markup
    )


@handle_errors
async def cg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change gift comment (admin only)"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_html("❌ You are not authorized")
        return
    
    # Check if admin provided new comment directly
    if context.args and len(context.args) > 0:
        new_comment = ' '.join(context.args)
        global gift_comment
        gift_comment = new_comment
        save_data()
        await update.message.reply_html(
            f"✅ <b>Gift comment updated!</b>\n\n"
            f"New comment: <b>{gift_comment}</b>"
        )
        logger.info(f"Admin {user_id} changed gift comment to: {gift_comment}")
        return
    
    # Show current comment and prompt for new one
    await update.message.reply_html(
        f"💬 <b>Change Gift Comment</b>\n\n"
        f"Current comment: <b>{gift_comment}</b>\n\n"
        f"Usage: /cg [new comment]\n\n"
        f"Example: /cg 🏆 @Iibrate - be with the best!"
    )


async def process_gift_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Process chat ID or username input - Step 2"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    target_user_id = None
    target_username = None
    
    # Try to parse as user_id (numeric)
    try:
        target_user_id = int(text.strip())
        target_username = str(target_user_id)
    except ValueError:
        # Try to find by username
        username = text.strip()
        if username.startswith('@'):
            username = username[1:]
        username_lower = username.lower()
        
        if username_lower in username_to_id:
            target_user_id = username_to_id[username_lower]
            target_username = username
        else:
            await update.message.reply_html(
                "❌ <b>User not found!</b>\n\n"
                "Please provide a valid username or chat ID.\n\n"
                "Examples:\n"
                "• 123456789 (chat ID)\n"
                "• @username (username)\n"
                "• username (username without @)"
            )
            return
    
    # Save target user
    context.user_data['gift_target_user_id'] = target_user_id
    context.user_data['gift_target_username'] = target_username
    context.user_data['gift_state'] = 'waiting_for_pingme'
    
    await update.message.reply_html(
        f"✅ <b>Target user set: {target_username or target_user_id}</b>\n\n"
        f"Now send /pingme to create payment invoice"
    )
    
    logger.info(f"Admin {user_id} set gift target: {target_user_id} ({target_username})")


async def process_gift_after_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically process gift after successful payment - Step 4"""
    user_id = update.effective_user.id
    target_user_id = context.user_data.get('gift_target_user_id')
    target_username = context.user_data.get('gift_target_username', str(target_user_id))
    
    if not target_user_id:
        logger.error(f"Gift processing failed: No target user ID for admin {user_id}")
        await update.message.reply_html("❌ Target user not found. Gift process cancelled.")
        return
    
    try:
        # Get available gifts from Telegram API
        logger.info(f"Admin {user_id}: Getting available gifts from Telegram API")
        
        # Use get_available_gifts() method
        if hasattr(context.bot, 'get_available_gifts'):
            gifts_response = await context.bot.get_available_gifts()
        else:
            # Fallback: Use API directly
            gifts_response = await context.bot._post('getAvailableGifts', {})
        
        # Filter gifts where star_count <= 15
        available_gifts = []
        if hasattr(gifts_response, 'gifts'):
            gifts_list = gifts_response.gifts
        elif isinstance(gifts_response, dict) and 'gifts' in gifts_response:
            gifts_list = gifts_response['gifts']
        else:
            gifts_list = []
        
        for gift in gifts_list:
            star_count = getattr(gift, 'star_count', None) or gift.get('star_count', 0)
            if star_count <= GIFT_STARS:
                available_gifts.append(gift)
        
        if not available_gifts:
            logger.error(f"No suitable gifts found (all exceed {GIFT_STARS} stars)")
            await update.message.reply_html(
                f"❌ <b>No suitable gifts available.</b>\n\n"
                f"All available gifts exceed {GIFT_STARS} stars limit."
            )
            # Reset state
            context.user_data['gift_state'] = None
            context.user_data['gift_target_user_id'] = None
            context.user_data['gift_target_username'] = None
            return
        
        # Select gift closest to 15 stars (prefer highest <= 15)
        selected_gift = max(available_gifts, key=lambda g: getattr(g, 'star_count', 0) or g.get('star_count', 0))
        gift_id = getattr(selected_gift, 'id', None) or selected_gift.get('id')
        gift_stars = getattr(selected_gift, 'star_count', None) or selected_gift.get('star_count', 0)
        
        logger.info(f"Admin {user_id}: Selected gift ID {gift_id} with {gift_stars} stars")
        
        # Send gift to target user with inbuilt comment
        # Try different parameter names that Telegram API might use for comment
        gift_sent = False
        comment_sent_in_gift = False
        
        # Try with 'comment' parameter first
        try:
            result = await context.bot._post(
                'sendGift',
                {
                    'user_id': target_user_id,
                    'gift_id': gift_id,
                    'comment': gift_comment
                }
            )
            gift_sent = True
            comment_sent_in_gift = True
            logger.info(f"Sent gift with inbuilt comment (parameter: 'comment') to {target_user_id}")
        except Exception as e1:
            error_msg = str(e1).lower()
            # Try with 'message' parameter
            if 'comment' in error_msg or 'unexpected' in error_msg or 'invalid' in error_msg:
                try:
                    result = await context.bot._post(
                        'sendGift',
                        {
                            'user_id': target_user_id,
                            'gift_id': gift_id,
                            'message': gift_comment
                        }
                    )
                    gift_sent = True
                    comment_sent_in_gift = True
                    logger.info(f"Sent gift with inbuilt comment (parameter: 'message') to {target_user_id}")
                except Exception as e2:
                    # Try with 'text' parameter
                    try:
                        result = await context.bot._post(
                            'sendGift',
                            {
                                'user_id': target_user_id,
                                'gift_id': gift_id,
                                'text': gift_comment
                            }
                        )
                        gift_sent = True
                        comment_sent_in_gift = True
                        logger.info(f"Sent gift with inbuilt comment (parameter: 'text') to {target_user_id}")
                    except Exception as e3:
                        # Last resort: send gift without comment, then send comment separately
                        logger.warning(f"None of the comment parameters worked, sending gift without comment: {e3}")
                        try:
                            result = await context.bot._post(
                                'sendGift',
                                {
                                    'user_id': target_user_id,
                                    'gift_id': gift_id
                                }
                            )
                            gift_sent = True
                            # Send comment as separate message
                            try:
                                await context.bot.send_message(
                                    chat_id=target_user_id,
                                    text=gift_comment
                                )
                                logger.info(f"Sent gift comment as separate message to {target_user_id}")
                            except Exception:
                                pass
                        except Exception as e4:
                            logger.error(f"Error sending gift: {e4}", exc_info=True)
                            raise e4
        
        if not gift_sent:
            raise Exception("Failed to send gift after all attempts")
        
        logger.info(f"Admin {user_id}: Successfully sent gift {gift_id} ({gift_stars} stars) to {target_user_id}")
        
        # Send referral message to gift recipient IMMEDIATELY after gift is sent
        try:
            # Get or create referral code for recipient
            recipient_ref_code = get_or_create_referral_code(target_user_id)
            
            # Get bot username for referral link
            try:
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username if bot_info.username else "Iibratebot"
            except Exception:
                bot_username = "Iibratebot"  # Fallback
            
            referral_link = f"t.me/{bot_username}?start=ref-{recipient_ref_code}"
            
            referral_message = (
                f"Invite your friends using your special link and receive a <b>daily gift</b> worth 10% from their activity 💝🔗\n\n"
                f"Claim your gift link:👉 {referral_link}\n\n"
                f"✨ The more friends you invite, the bigger your <b>daily gifts</b>⏰\n\n"
                f"Gifts are credited every day automatically"
            )
            
            await context.bot.send_message(
                chat_id=target_user_id,
                text=referral_message,
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Sent referral message immediately to gift recipient {target_user_id}")
        except Exception as ref_error:
            logger.warning(f"Failed to send referral message to {target_user_id}: {ref_error}")
            # Continue even if referral message fails
        
        # Confirm success to admin (after referral message is sent)
        await update.message.reply_html(
            f"✅ <b>Payment received!</b>\n\n"
            f"🎁 <b>Processing gift...</b>\n\n"
            f"✅ <b>Gift sent successfully to user {target_username or target_user_id}!</b>\n\n"
            f"Gift ID: <code>{gift_id}</code>\n"
            f"Stars: {gift_stars} ⭐"
        )
        
        # Reset state
        context.user_data['gift_state'] = None
        context.user_data['gift_target_user_id'] = None
        context.user_data['gift_target_username'] = None
        
    except Exception as e:
        logger.error(f"Error processing gift after payment: {e}", exc_info=True)
        await update.message.reply_html(
            f"❌ <b>Failed to send gift.</b>\n\n"
            f"Error: {str(e)}\n\n"
            "Please try again or contact support."
        )
        # Reset state on error
        context.user_data['gift_state'] = None
        context.user_data['gift_target_user_id'] = None
        context.user_data['gift_target_username'] = None


@handle_errors
async def bankroll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show or set bankroll. Admins can set; everyone can view."""
    user_id = update.effective_user.id
    
    # Admin setting value
    if is_admin(user_id):
        if context.args and len(context.args) >= 1:
            try:
                amount = float(context.args[0])
                global casino_bankroll_usd
                casino_bankroll_usd = amount
                save_data()
                await update.message.reply_html(
                    f"✅ Bankroll updated.\n\n🏦 Casino Bankroll\n💵 USD: ${casino_bankroll_usd:,.2f}"
                )
                return
            except ValueError:
                pass  # fall through to prompt
        
        # Prompt admin for amount if not provided or invalid
        context.user_data['waiting_for_bankroll'] = True
        await update.message.reply_html(
            "🏦 <b>Set Casino Bankroll</b>\n\n"
            "Send the bankroll amount in USD (e.g., 2493.23)."
        )
        return
    
    # Non-admins just view
    await update.message.reply_html(
        f"🏦 <b>Casino Bankroll</b>\n💵 USD: ${casino_bankroll_usd:,.2f}"
    )


async def perform_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, source_message):
    """Copy the admin's message to all known users who started the bot."""
    admin_id = update.effective_user.id
    total = 0
    sent = 0
    errors = 0
    
    # We consider all known user_ids from profiles as started users
    target_users = list(user_profiles.keys())
    total = len(target_users)
    
    for uid in target_users:
        try:
            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=source_message.chat_id,
                message_id=source_message.message_id
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Forbidden:
            errors += 1
        except Exception:
            errors += 1
    
    await context.bot.send_message(
        chat_id=admin_id,
        text=(
            f"✅ Broadcast finished.\n"
            f"Total users: {total}\n"
            f"Sent: {sent}\n"
            f"Failed: {errors}"
        )
    )


@handle_errors
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt admin for a message to broadcast to all users."""
    user_id = update.effective_user.id
    
    # Must be admin
    if not is_admin(user_id):
        await update.message.reply_html("❌ Only admins can broadcast.")
        return
    
    # Only accept in private chat
    if update.effective_chat.type != "private":
        await update.message.reply_html("❌ Use this command in DM with the bot.")
        return
    
    broadcast_waiting.add(user_id)
    await update.message.reply_html(
        "📢 <b>Broadcast Mode</b>\n\n"
        "Send the message you want to broadcast.\n"
        "Supports text, photos, videos, audio (mp3), documents, etc.\n\n"
        "Use /cancel to exit."
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
    application.add_handler(CommandHandler("help", support_command))  # Alias for /support
    application.add_handler(CommandHandler("com", com_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("bal", balance_command))  # Alias
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("depo", deposit_command))  # Alias
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("custom", custom_deposit))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("levels", levels_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("bonus", bonus_command))
    application.add_handler(CommandHandler("weekly", weekly_command))
    application.add_handler(CommandHandler(["referral", "ref"], referral_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler(["hb", "housebal"], bankroll_command))
    application.add_handler(CommandHandler("wd", wd_command))
    
    # Game commands
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("bowl", bowl_command))
    application.add_handler(CommandHandler("arrow", arrow_command))
    application.add_handler(CommandHandler("football", football_command))
    application.add_handler(CommandHandler("basket", basket_command))
    application.add_handler(CommandHandler("demo", demo_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("listadmins", listadmins_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("user", user_command))
    application.add_handler(CommandHandler("video", set_video_command))
    application.add_handler(CommandHandler("steal", steal_command))
    application.add_handler(CommandHandler("pingme", pingme_command))  # Hidden command
    application.add_handler(CommandHandler("gift", gift_command))
    application.add_handler(CommandHandler("cg", cg_command))
    
    # Tip command
    application.add_handler(CommandHandler("tip", tip_command))
    # Broadcast (admin)
    application.add_handler(CommandHandler(["broadcast", "bc"], broadcast_command))
    
    # Handlers
    # Put broadcast capture in a later group so game handlers run first
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_broadcast_capture, block=False), group=1)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO | filters.AUDIO | filters.Document.AUDIO, handle_video_message))
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_game_emoji))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()