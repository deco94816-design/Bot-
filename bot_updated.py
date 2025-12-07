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

BOT_USERNAME = "Iibrate"
DATA_FILE = "bot_data.json"

admin_list = {ADMIN_ID}
ADMIN_BALANCE = 9999999999

user_games = {}
user_balances = defaultdict(float)
game_locks = defaultdict(asyncio.Lock)
user_withdrawals = {}
withdrawal_counter = 26356
user_profiles = {}
user_game_history = defaultdict(list)
user_bonus_claimed = set()
user_last_game_settings = {}
username_to_id = {}
withdraw_video_file_id = None
all_bot_users = set()
banned_users = set()
message_ownership = {}
user_referrals = {}
REFERRAL_BONUS = 10

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

def save_data():
    global withdraw_video_file_id
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
            'all_bot_users': list(all_bot_users),
            'banned_users': list(banned_users),
            'user_referrals': {str(k): v for k, v in user_referrals.items()}
        }
        for user_id, profile in user_profiles.items():
            profile_copy = dict(profile)
            if 'registration_date' in profile_copy:
                profile_copy['registration_date'] = profile_copy['registration_date'].isoformat()
            if 'game_counts' in profile_copy:
                profile_copy['game_counts'] = dict(profile_copy['game_counts'])
            data['user_profiles'][str(user_id)] = profile_copy
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
    global user_balances, user_profiles, user_game_history, user_bonus_claimed
    global user_withdrawals, withdrawal_counter, admin_list, username_to_id
    global user_last_game_settings, withdraw_video_file_id, all_bot_users
    global banned_users, user_referrals
    try:
        if not os.path.exists(DATA_FILE):
            logger.info("No data file found, starting fresh")
            return
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        user_balances.update({int(k): float(v) for k, v in data.get('user_balances', {}).items()})
        for user_id_str, profile in data.get('user_profiles', {}).items():
            user_id = int(user_id_str)
            if 'registration_date' in profile:
                profile['registration_date'] = datetime.fromisoformat(profile['registration_date'])
            if 'game_counts' in profile:
                profile['game_counts'] = defaultdict(int, profile['game_counts'])
            user_profiles[user_id] = profile
        for user_id_str, history in data.get('user_game_history', {}).items():
            user_id = int(user_id_str)
            deserialized_history = []
            for game in history:
                if 'timestamp' in game:
                    game['timestamp'] = datetime.fromisoformat(game['timestamp'])
                deserialized_history.append(game)
            user_game_history[user_id] = deserialized_history
        user_bonus_claimed.update(set(data.get('user_bonus_claimed', [])))
        user_withdrawals.update(data.get('user_withdrawals', {}))
        withdrawal_counter = data.get('withdrawal_counter', 26356)
        admin_list.update(set(data.get('admin_list', [ADMIN_ID])))
        username_to_id.update(data.get('username_to_id', {}))
        user_last_game_settings.update({int(k): v for k, v in data.get('user_last_game_settings', {}).items()})
        withdraw_video_file_id = data.get('withdraw_video_file_id', None)
        all_bot_users.update(set(data.get('all_bot_users', [])))
        banned_users.update(set(data.get('banned_users', [])))
        for user_id_str, ref_data in data.get('user_referrals', {}).items():
            user_referrals[int(user_id_str)] = ref_data
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

def is_admin(user_id): return user_id in admin_list
def is_banned(user_id): return user_id in banned_users
def get_user_balance(user_id):
    if is_admin(user_id): return ADMIN_BALANCE
    return user_balances[user_id]
def set_user_balance(user_id, amount):
    if not is_admin(user_id):
        user_balances[user_id] = amount
        save_data()
def adjust_user_balance(user_id, amount):
    if not is_admin(user_id):
        user_balances[user_id] += amount
        save_data()
def get_user_link(user_id, name): return f'<a href="tg://user?id={user_id}">{name}</a>'
def track_message_owner(message_id, chat_id, user_id): message_ownership[f"{chat_id}_{message_id}"] = user_id
def get_message_owner(message_id, chat_id): return message_ownership.get(f"{chat_id}_{message_id}")
def get_referral_link(user_id, bot_username): return f"https://t.me/{bot_username}?start=ref_{user_id}"
def is_private_chat(update): return update.effective_chat.type == "private"

def get_or_create_profile(user_id, username=None):
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            'user_id': user_id, 'username': username or 'Unknown',
            'registration_date': datetime.now(), 'xp': 0, 'total_games': 0,
            'total_bets': 0.0, 'total_wins': 0.0, 'total_losses': 0.0,
            'games_won': 0, 'games_lost': 0, 'favorite_game': None,
            'biggest_win': 0.0, 'game_counts': defaultdict(int)
        }
        save_data()
    if username:
        username_to_id[username.lower().lstrip('@')] = user_id
        save_data()
    return user_profiles[user_id]

def get_or_create_referral_data(user_id):
    if user_id not in user_referrals:
        user_referrals[user_id] = {'referrer': None, 'referred_users': [], 'earnings': 0}
        save_data()
    return user_referrals[user_id]

def process_referral(new_user_id, referrer_id):
    if new_user_id == referrer_id: return False
    new_user_ref = get_or_create_referral_data(new_user_id)
    if new_user_ref['referrer'] is not None: return False
    if referrer_id not in all_bot_users: return False
    new_user_ref['referrer'] = referrer_id
    referrer_ref = get_or_create_referral_data(referrer_id)
    if new_user_id not in referrer_ref['referred_users']:
        referrer_ref['referred_users'].append(new_user_id)
        referrer_ref['earnings'] += REFERRAL_BONUS
        adjust_user_balance(referrer_id, REFERRAL_BONUS)
        save_data()
        return True
    return False

def get_user_rank(xp):
    current_rank = 1
    for level, data in RANKS.items():
        if xp >= data['xp_required']: current_rank = level
        else: break
    return current_rank

def get_rank_info(level): return RANKS.get(level, RANKS[1])

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
        if win_amount > profile['biggest_win']: profile['biggest_win'] = win_amount
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
        'game_type': game_type, 'bet_amount': bet_amount,
        'win_amount': win_amount if won else 0, 'won': won, 'timestamp': datetime.now()
    })
    save_data()

def generate_transaction_id():
    chars = string.ascii_letters + string.digits
    return 'stx' + ''.join(random.choice(chars) for _ in range(80))

def is_valid_ton_address(address):
    if not address: return False
    if re.match(r'^(UQ|EQ|kQ|0Q)[A-Za-z0-9_-]{46}$', address): return True
    if re.match(r'^-?[0-9]+:[a-fA-F0-9]{64}$', address): return True
    return 48 <= len(address) <= 67

def check_bot_name_in_profile(user):
    first_name = (user.first_name or "").lower()
    last_name = (user.last_name or "").lower()
    return BOT_USERNAME.lower() in first_name or BOT_USERNAME.lower() in last_name

def save_last_game_settings(user_id, game_type, bet_amount, rounds, throws, bot_first):
    user_last_game_settings[user_id] = {'game_type': game_type, 'bet_amount': bet_amount, 'rounds': rounds, 'throws': throws, 'bot_first': bot_first}
    save_data()

def get_user_id_by_username(username): return username_to_id.get(username.lower().lstrip('@'))

def create_progress_bar(current, total, length=10):
    if total == 0: filled = 0
    else: filled = int((current / total) * length)
    return "▓" * filled + "░" * (length - filled)

def handle_errors(func):
    async def wrapper(update, context, *args, **kwargs):
        try: return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            try:
                if update.message: await update.message.reply_html("❌ An error occurred. Please try again.")
            except: pass
    return wrapper

def check_ban(func):
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and is_banned(user_id) and not is_admin(user_id): return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ==================== COMMANDS ====================

@handle_errors
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>Admin only command.</b>")
        return
    if not context.args:
        await update.message.reply_html(f"🚫 <b>Ban User</b>\n\nUsage: /ban <user_id>\nCurrently banned: {len(banned_users)}")
        return
    try:
        target_id = int(context.args[0])
        if target_id in admin_list:
            await update.message.reply_html("❌ Cannot ban an admin!")
            return
        if target_id in banned_users:
            await update.message.reply_html(f"⚠️ User <code>{target_id}</code> is already banned!")
            return
        banned_users.add(target_id)
        save_data()
        await update.message.reply_html(f"✅ <b>User banned!</b>\n\n👤 ID: <code>{target_id}</code>")
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID!")

@handle_errors
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>Admin only command.</b>")
        return
    if not context.args:
        await update.message.reply_html("✅ <b>Unban User</b>\n\nUsage: /unban <user_id>")
        return
    try:
        target_id = int(context.args[0])
        if target_id not in banned_users:
            await update.message.reply_html(f"⚠️ User <code>{target_id}</code> is not banned!")
            return
        banned_users.remove(target_id)
        save_data()
        await update.message.reply_html(f"✅ <b>User unbanned!</b>\n\n👤 ID: <code>{target_id}</code>")
    except ValueError:
        await update.message.reply_html("❌ Invalid user ID!")

@handle_errors
async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ <b>Admin only command.</b>")
        return
    if not banned_users:
        await update.message.reply_html("✅ No users are currently banned.")
        return
    ban_text = f"🚫 <b>Banned Users</b>\n\nTotal: {len(banned_users)}\n\n"
    for idx, banned_id in enumerate(list(banned_users)[:50], 1):
        ban_text += f"{idx}. <code>{banned_id}</code>\n"
    await update.message.reply_html(ban_text)

@handle_errors
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_html("❌ <b>Admin only command.</b>")
        return
    if not is_private_chat(update):
        await update.message.reply_html("❌ Please use /broadcast in private chat.")
        return
    context.user_data['broadcast_state'] = 'waiting_content'
    context.user_data['broadcast_content'] = None
    context.user_data['broadcast_type'] = None
    context.user_data['broadcast_caption'] = None
    context.user_data['broadcast_button_name'] = None
    context.user_data['broadcast_button_url'] = None
    await update.message.reply_html(f"📢 <b>Broadcast Message</b>\n\n👥 Total users: <b>{len(all_bot_users)}</b>\n\nSend your content (text/photo/video).\nUse /cancel to abort.")

async def execute_broadcast(context, admin_id):
    broadcast_type = context.user_data.get('broadcast_type')
    content = context.user_data.get('broadcast_content')
    caption = context.user_data.get('broadcast_caption')
    button_name = context.user_data.get('broadcast_button_name')
    button_url = context.user_data.get('broadcast_button_url')
    reply_markup = None
    if button_name and button_url:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_name, url=button_url)]])
    success, failed, blocked = 0, 0, 0
    for uid in list(all_bot_users):
        if uid in banned_users: continue
        try:
            if broadcast_type == 'text':
                await context.bot.send_message(chat_id=uid, text=content, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            elif broadcast_type == 'photo':
                await context.bot.send_photo(chat_id=uid, photo=content, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            elif broadcast_type == 'video':
                await context.bot.send_video(chat_id=uid, video=content, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            success += 1
            await asyncio.sleep(0.05)
        except Forbidden:
            blocked += 1
            all_bot_users.discard(uid)
        except: failed += 1
    save_data()
    await context.bot.send_message(chat_id=admin_id, text=f"📊 <b>Broadcast Complete!</b>\n\n✅ Sent: {success}\n❌ Failed: {failed}\n🚫 Blocked: {blocked}", parse_mode=ParseMode.HTML)

@handle_errors
@check_ban
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_private_chat(update):
        bot_info = await context.bot.get_me()
        await update.message.reply_html(f"🔒 Use /referral in private chat.\n\n👉 <a href='https://t.me/{bot_info.username}'>Open DM</a>")
        return
    bot_info = await context.bot.get_me()
    ref_link = get_referral_link(user_id, bot_info.username)
    ref_data = get_or_create_referral_data(user_id)
    await update.message.reply_html(
        f"👥 <b>Referral Program</b>\n\nEarn <b>{REFERRAL_BONUS} ⭐</b> per referral!\n\n"
        f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
        f"📊 Referred: <b>{len(ref_data['referred_users'])}</b>\n"
        f"💰 Earnings: <b>{ref_data['earnings']} ⭐</b>")

@handle_errors
@check_ban
async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if user_id in user_bonus_claimed:
        await update.message.reply_html("❌ <b>Bonus Already Claimed!</b>")
        return
    if check_bot_name_in_profile(user):
        adjust_user_balance(user_id, BONUS_AMOUNT)
        user_bonus_claimed.add(user_id)
        save_data()
        await update.message.reply_html(f"🎁 <b>Bonus Claimed!</b>\n\n💰 You received: <b>{BONUS_AMOUNT} ⭐</b>")
    else:
        await update.message.reply_html(f"❌ Add <b>'{BOT_USERNAME}'</b> to your profile name, then use /bonus again.")

@handle_errors
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    if not context.args:
        await update.message.reply_html(f"👑 <b>Add Admin</b>\n\nUsage: /addadmin <user_id>\nCurrent: {len(admin_list)}")
        return
    try:
        new_admin_id = int(context.args[0])
        if new_admin_id in admin_list:
            await update.message.reply_html(f"⚠️ Already admin!")
            return
        admin_list.add(new_admin_id)
        save_data()
        await update.message.reply_html(f"✅ Admin added: <code>{new_admin_id}</code>")
    except ValueError:
        await update.message.reply_html("❌ Invalid ID!")

@handle_errors
async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    if not context.args:
        await update.message.reply_html("👑 Usage: /removeadmin <user_id>")
        return
    try:
        remove_id = int(context.args[0])
        if remove_id == ADMIN_ID:
            await update.message.reply_html("❌ Cannot remove main admin!")
            return
        if remove_id not in admin_list:
            await update.message.reply_html("⚠️ Not an admin!")
            return
        admin_list.remove(remove_id)
        save_data()
        await update.message.reply_html(f"✅ Removed: <code>{remove_id}</code>")
    except ValueError:
        await update.message.reply_html("❌ Invalid ID!")

@handle_errors
async def listadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    text = "👑 <b>Admins</b>\n\n"
    for idx, aid in enumerate(admin_list, 1):
        text += f"{idx}. <code>{aid}</code>{' (Main)' if aid == ADMIN_ID else ''}\n"
    await update.message.reply_html(text)

@handle_errors
async def set_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global withdraw_video_file_id
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    if context.args and context.args[0].lower() == 'status':
        await update.message.reply_html(f"🎬 Video: {'✅ Set' if withdraw_video_file_id else '❌ Not set'}")
        return
    if context.args and context.args[0].lower() == 'remove':
        withdraw_video_file_id = None
        save_data()
        await update.message.reply_html("✅ Video removed!")
        return
    context.user_data['waiting_for_video'] = True
    await update.message.reply_html("🎬 Send video now. /cancel to abort.")

@handle_errors
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_html("✅ Cancelled.")

@handle_errors
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    total_games = sum(p.get('total_games', 0) for p in user_profiles.values())
    total_bets = sum(p.get('total_bets', 0) for p in user_profiles.values())
    await update.message.reply_html(
        f"📊 <b>Stats</b>\n\n👥 Users: {len(all_bot_users)}\n🚫 Banned: {len(banned_users)}\n"
        f"🎮 Games: {total_games}\n💰 Bets: {total_bets:,.0f} ⭐")

@handle_errors
@check_ban
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    is_new_user = user_id not in all_bot_users
    all_bot_users.add(user_id)
    get_or_create_profile(user_id, username)
    
    # Handle referral
    if is_new_user and context.args:
        arg = context.args[0]
        if arg.startswith('ref_'):
            try:
                referrer_id = int(arg[4:])
                if process_referral(user_id, referrer_id):
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 <b>New Referral!</b>\n\n{get_user_link(user_id, username)} joined via your link!\n💰 +{REFERRAL_BONUS} ⭐",
                            parse_mode=ParseMode.HTML)
                    except: pass
            except: pass
    save_data()
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play Game", callback_data="menu_play"),
         InlineKeyboardButton("💰 Balance", callback_data="menu_balance")],
        [InlineKeyboardButton("👤 Profile", callback_data="menu_profile"),
         InlineKeyboardButton("📊 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("💳 Deposit", callback_data="menu_deposit"),
         InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw")]
    ]
    msg = await update.message.reply_html(
        f"🎰 <b>Welcome, {username}!</b>\n\n⭐ Balance: <b>{get_user_balance(user_id):,.2f}</b>",
        reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton(f"{data['icon']} {data['name']}", callback_data=f"select_game_{game_type}")] for game_type, data in GAME_TYPES.items()]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    msg = await update.message.reply_html("🎮 <b>Select Game:</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    usd = balance * STARS_TO_USD
    ton = balance * STARS_TO_TON
    keyboard = [
        [InlineKeyboardButton("💳 Deposit", callback_data="menu_deposit"),
         InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw")],
        [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]
    ]
    msg = await update.message.reply_html(
        f"💰 <b>Balance</b>\n\n⭐ {balance:,.2f}\n💵 ${usd:,.2f}\n💎 {ton:,.4f} TON",
        reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    profile = get_or_create_profile(user_id, user.username)
    rank = get_user_rank(profile['xp'])
    rank_info = get_rank_info(rank)
    next_rank_info = get_rank_info(rank + 1) if rank < 20 else None
    ref_data = get_or_create_referral_data(user_id)
    
    text = f"{rank_info['emoji']} <b>{profile['username']}</b>\n\n"
    text += f"🏅 Rank: {rank_info['name']} (Lv.{rank})\n⭐ XP: {profile['xp']:,}"
    if next_rank_info:
        progress = create_progress_bar(profile['xp'] - rank_info['xp_required'], next_rank_info['xp_required'] - rank_info['xp_required'])
        text += f"\n{progress} → {next_rank_info['name']}"
    text += f"\n\n🎮 Games: {profile['total_games']}\n✅ Won: {profile['games_won']} | ❌ Lost: {profile['games_lost']}"
    if profile['total_games'] > 0:
        wr = (profile['games_won'] / profile['total_games']) * 100
        text += f"\n📈 Win Rate: {wr:.1f}%"
    text += f"\n\n💰 Bets: {profile['total_bets']:,.0f} ⭐\n🏆 Best: {profile['biggest_win']:,.0f} ⭐"
    text += f"\n\n👥 Referrals: {len(ref_data['referred_users'])}"
    
    keyboard = [[InlineKeyboardButton("📜 History", callback_data="view_history")],
                [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
    msg = await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("💰 By Balance", callback_data="lb_balance"),
         InlineKeyboardButton("⭐ By XP", callback_data="lb_xp")],
        [InlineKeyboardButton("🎮 By Games", callback_data="lb_games"),
         InlineKeyboardButton("🏆 By Wins", callback_data="lb_wins")],
        [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]
    ]
    msg = await update.message.reply_html("📊 <b>Leaderboard</b>\n\nSelect type:", reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_private_chat(update):
        bot_info = await context.bot.get_me()
        await update.message.reply_html(f"🔒 DM only.\n\n👉 <a href='https://t.me/{bot_info.username}'>Open DM</a>")
        return
    keyboard = [[InlineKeyboardButton(f"⭐ {amt}", callback_data=f"deposit_{amt}")] for amt in [50, 100, 200, 500, 1000]]
    keyboard.append([InlineKeyboardButton("✏️ Custom", callback_data="deposit_custom")])
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")])
    msg = await update.message.reply_html("💳 <b>Deposit</b>\n\nSelect amount:", reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_private_chat(update):
        bot_info = await context.bot.get_me()
        await update.message.reply_html(f"🔒 DM only.\n\n👉 <a href='https://t.me/{bot_info.username}'>Open DM</a>")
        return
    balance = get_user_balance(user_id)
    if balance < MIN_WITHDRAWAL:
        await update.message.reply_html(f"❌ Min {MIN_WITHDRAWAL} ⭐ required.\n\nBalance: {balance:,.2f} ⭐")
        return
    keyboard = [[InlineKeyboardButton("💎 TON", callback_data="withdraw_ton")],
                [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
    msg = await update.message.reply_html(f"💸 <b>Withdraw</b>\n\nBalance: {balance:,.2f} ⭐\nMin: {MIN_WITHDRAWAL} ⭐", reply_markup=InlineKeyboardMarkup(keyboard))
    track_message_owner(msg.message_id, msg.chat_id, user_id)

@handle_errors
@check_ban
async def addbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    if len(context.args) < 2:
        await update.message.reply_html("Usage: /addbalance <user_id/@username> <amount>")
        return
    target, amount_str = context.args[0], context.args[1]
    try:
        amount = float(amount_str)
    except:
        await update.message.reply_html("❌ Invalid amount!")
        return
    if target.startswith('@'):
        target_id = get_user_id_by_username(target)
        if not target_id:
            await update.message.reply_html("❌ User not found!")
            return
    else:
        try: target_id = int(target)
        except:
            await update.message.reply_html("❌ Invalid ID!")
            return
    adjust_user_balance(target_id, amount)
    await update.message.reply_html(f"✅ Added {amount:,.2f} ⭐ to <code>{target_id}</code>\nNew: {get_user_balance(target_id):,.2f} ⭐")

@handle_errors
@check_ban
async def removebalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    if len(context.args) < 2:
        await update.message.reply_html("Usage: /removebalance <user_id/@username> <amount>")
        return
    target, amount_str = context.args[0], context.args[1]
    try:
        amount = float(amount_str)
    except:
        await update.message.reply_html("❌ Invalid amount!")
        return
    if target.startswith('@'):
        target_id = get_user_id_by_username(target)
        if not target_id:
            await update.message.reply_html("❌ User not found!")
            return
    else:
        try: target_id = int(target)
        except:
            await update.message.reply_html("❌ Invalid ID!")
            return
    adjust_user_balance(target_id, -amount)
    await update.message.reply_html(f"✅ Removed {amount:,.2f} ⭐ from <code>{target_id}</code>\nNew: {get_user_balance(target_id):,.2f} ⭐")

@handle_errors
@check_ban
async def checkbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_html("❌ Admin only.")
        return
    if not context.args:
        await update.message.reply_html("Usage: /checkbalance <user_id/@username>")
        return
    target = context.args[0]
    if target.startswith('@'):
        target_id = get_user_id_by_username(target)
        if not target_id:
            await update.message.reply_html("❌ User not found!")
            return
    else:
        try: target_id = int(target)
        except:
            await update.message.reply_html("❌ Invalid ID!")
            return
    balance = get_user_balance(target_id)
    await update.message.reply_html(f"💰 <code>{target_id}</code>: {balance:,.2f} ⭐")

# ==================== CALLBACK HANDLERS ====================

@handle_errors
@check_ban
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # Owner check for game/balance/withdraw buttons
    owner_only_prefixes = ('select_game_', 'bet_', 'rounds_', 'throws_', 'order_', 'confirm_game_',
                           'roll_', 'deposit_', 'withdraw_', 'confirm_withdraw_', 'menu_', 'back_',
                           'lb_', 'view_history', 'replay_')
    if any(data.startswith(p) for p in owner_only_prefixes):
        owner = get_message_owner(query.message.message_id, query.message.chat_id)
        if owner and owner != user_id:
            await query.answer("❌ This is not your message!", show_alert=True)
            return
    
    await query.answer()
    
    # Menu navigation
    if data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("🎮 Play", callback_data="menu_play"),
             InlineKeyboardButton("💰 Balance", callback_data="menu_balance")],
            [InlineKeyboardButton("👤 Profile", callback_data="menu_profile"),
             InlineKeyboardButton("📊 Leaderboard", callback_data="menu_leaderboard")],
            [InlineKeyboardButton("💳 Deposit", callback_data="menu_deposit"),
             InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw")]
        ]
        await query.edit_message_text(f"🎰 <b>Menu</b>\n\n⭐ Balance: <b>{get_user_balance(user_id):,.2f}</b>",
                                      parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_play":
        keyboard = [[InlineKeyboardButton(f"{d['icon']} {d['name']}", callback_data=f"select_game_{gt}")] for gt, d in GAME_TYPES.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        await query.edit_message_text("🎮 <b>Select Game:</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_balance":
        balance = get_user_balance(user_id)
        keyboard = [[InlineKeyboardButton("💳 Deposit", callback_data="menu_deposit"),
                     InlineKeyboardButton("💸 Withdraw", callback_data="menu_withdraw")],
                    [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
        await query.edit_message_text(f"💰 <b>Balance</b>\n\n⭐ {balance:,.2f}\n💵 ${balance*STARS_TO_USD:,.2f}\n💎 {balance*STARS_TO_TON:,.4f} TON",
                                      parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_profile":
        profile = get_or_create_profile(user_id, query.from_user.username)
        rank = get_user_rank(profile['xp'])
        rank_info = get_rank_info(rank)
        ref_data = get_or_create_referral_data(user_id)
        text = f"{rank_info['emoji']} <b>{profile['username']}</b>\n\n🏅 {rank_info['name']} (Lv.{rank})\n⭐ XP: {profile['xp']:,}"
        text += f"\n\n🎮 Games: {profile['total_games']} | ✅ {profile['games_won']} | ❌ {profile['games_lost']}"
        text += f"\n💰 Bets: {profile['total_bets']:,.0f} ⭐\n👥 Referrals: {len(ref_data['referred_users'])}"
        keyboard = [[InlineKeyboardButton("📜 History", callback_data="view_history")],
                    [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_leaderboard":
        keyboard = [[InlineKeyboardButton("💰 Balance", callback_data="lb_balance"),
                     InlineKeyboardButton("⭐ XP", callback_data="lb_xp")],
                    [InlineKeyboardButton("🎮 Games", callback_data="lb_games"),
                     InlineKeyboardButton("🏆 Wins", callback_data="lb_wins")],
                    [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
        await query.edit_message_text("📊 <b>Leaderboard</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_deposit":
        if query.message.chat.type != "private":
            bot_info = await context.bot.get_me()
            await query.edit_message_text(f"🔒 DM only.\n\n👉 <a href='https://t.me/{bot_info.username}'>Open DM</a>", parse_mode=ParseMode.HTML)
            return
        keyboard = [[InlineKeyboardButton(f"⭐ {a}", callback_data=f"deposit_{a}")] for a in [50, 100, 200, 500, 1000]]
        keyboard.append([InlineKeyboardButton("✏️ Custom", callback_data="deposit_custom")])
        keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")])
        await query.edit_message_text("💳 <b>Deposit</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_withdraw":
        if query.message.chat.type != "private":
            bot_info = await context.bot.get_me()
            await query.edit_message_text(f"🔒 DM only.\n\n👉 <a href='https://t.me/{bot_info.username}'>Open DM</a>", parse_mode=ParseMode.HTML)
            return
        balance = get_user_balance(user_id)
        if balance < MIN_WITHDRAWAL:
            await query.edit_message_text(f"❌ Min {MIN_WITHDRAWAL} ⭐\n\nBalance: {balance:,.2f} ⭐", parse_mode=ParseMode.HTML)
            return
        keyboard = [[InlineKeyboardButton("💎 TON", callback_data="withdraw_ton")],
                    [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
        await query.edit_message_text(f"💸 <b>Withdraw</b>\n\nBalance: {balance:,.2f} ⭐", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Game selection
    if data.startswith("select_game_"):
        game_type = data.replace("select_game_", "")
        context.user_data['selected_game'] = game_type
        game_info = GAME_TYPES[game_type]
        balance = get_user_balance(user_id)
        last = user_last_game_settings.get(user_id)
        keyboard = [[InlineKeyboardButton(f"⭐ {a}", callback_data=f"bet_{a}")] for a in [10, 25, 50, 100, 250]]
        keyboard.append([InlineKeyboardButton("✏️ Custom", callback_data="bet_custom")])
        if last and last['game_type'] == game_type:
            keyboard.append([InlineKeyboardButton(f"🔄 Last: {last['bet_amount']}⭐ {last['rounds']}R {last['throws']}T", callback_data="bet_last")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_play")])
        await query.edit_message_text(f"{game_info['icon']} <b>{game_info['name']}</b>\n\n💰 Balance: {balance:,.2f} ⭐\n\nSelect bet:",
                                      parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Bet selection
    if data.startswith("bet_"):
        bet_data = data.replace("bet_", "")
        if bet_data == "custom":
            context.user_data['waiting_for_bet'] = True
            await query.edit_message_text("✏️ Enter bet amount:", parse_mode=ParseMode.HTML)
            return
        if bet_data == "last":
            last = user_last_game_settings.get(user_id)
            if last:
                context.user_data['bet_amount'] = last['bet_amount']
                context.user_data['rounds'] = last['rounds']
                context.user_data['throws'] = last['throw_count'] if 'throw_count' in last else last['throws']
                context.user_data['bot_first'] = last['bot_first']
                game_type = context.user_data.get('selected_game', last['game_type'])
                game_info = GAME_TYPES[game_type]
                order_text = "🤖 Bot First" if last['bot_first'] else "👤 You First"
                keyboard = [[InlineKeyboardButton("✅ Start", callback_data=f"confirm_game_{game_type}")],
                            [InlineKeyboardButton("🔙 Back", callback_data=f"select_game_{game_type}")]]
                await query.edit_message_text(
                    f"{game_info['icon']} <b>{game_info['name']}</b>\n\n💰 Bet: {last['bet_amount']} ⭐\n🔄 Rounds: {last['rounds']}\n🎯 Throws: {last['throws']}\n{order_text}",
                    parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
                return
        try:
            bet = int(bet_data)
            balance = get_user_balance(user_id)
            if bet > balance:
                await query.answer("❌ Insufficient balance!", show_alert=True)
                return
            context.user_data['bet_amount'] = bet
            keyboard = [[InlineKeyboardButton(f"{r}R", callback_data=f"rounds_{r}") for r in [1, 3, 5]]]
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"select_game_{context.user_data.get('selected_game', 'dice')}")])
            await query.edit_message_text(f"💰 Bet: {bet} ⭐\n\nSelect rounds:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        except: pass
        return

    # Rounds selection
    if data.startswith("rounds_"):
        rounds = int(data.replace("rounds_", ""))
        context.user_data['rounds'] = rounds
        keyboard = [[InlineKeyboardButton(f"{t}T", callback_data=f"throws_{t}") for t in [1, 2, 3]]]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"bet_{context.user_data.get('bet_amount', 10)}")])
        await query.edit_message_text(f"🔄 Rounds: {rounds}\n\nSelect throws per round:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Throws selection
    if data.startswith("throws_"):
        throws = int(data.replace("throws_", ""))
        context.user_data['throws'] = throws
        keyboard = [[InlineKeyboardButton("👤 You First", callback_data="order_user"),
                     InlineKeyboardButton("🤖 Bot First", callback_data="order_bot")]]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"rounds_{context.user_data.get('rounds', 1)}")])
        await query.edit_message_text(f"🎯 Throws: {throws}\n\nWho goes first?", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Order selection
    if data.startswith("order_"):
        bot_first = data == "order_bot"
        context.user_data['bot_first'] = bot_first
        game_type = context.user_data.get('selected_game', 'dice')
        game_info = GAME_TYPES[game_type]
        bet = context.user_data.get('bet_amount', 10)
        rounds = context.user_data.get('rounds', 1)
        throws = context.user_data.get('throws', 1)
        order_text = "🤖 Bot First" if bot_first else "👤 You First"
        keyboard = [[InlineKeyboardButton("✅ Start Game", callback_data=f"confirm_game_{game_type}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"throws_{throws}")]]
        await query.edit_message_text(
            f"{game_info['icon']} <b>{game_info['name']}</b>\n\n💰 Bet: {bet} ⭐\n🔄 Rounds: {rounds}\n🎯 Throws: {throws}\n{order_text}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Confirm game start
    if data.startswith("confirm_game_"):
        game_type = data.replace("confirm_game_", "")
        bet = context.user_data.get('bet_amount', 10)
        rounds = context.user_data.get('rounds', 1)
        throws = context.user_data.get('throws', 1)
        bot_first = context.user_data.get('bot_first', False)
        balance = get_user_balance(user_id)
        
        if bet > balance:
            await query.answer("❌ Insufficient balance!", show_alert=True)
            return
        
        async with game_locks[user_id]:
            if user_id in user_games:
                await query.answer("❌ Game in progress!", show_alert=True)
                return
            
            adjust_user_balance(user_id, -bet)
            game = Game(user_id, query.from_user.username or query.from_user.first_name, bet, rounds, throws, game_type)
            game.bot_first = bot_first
            user_games[user_id] = game
            save_last_game_settings(user_id, game_type, bet, rounds, throws, bot_first)
        
        game_info = GAME_TYPES[game_type]
        text = f"{game_info['icon']} <b>Round 1/{rounds}</b>\n\n💰 Bet: {bet} ⭐\n\n"
        
        if bot_first:
            # Bot rolls first
            bot_msg = await query.message.reply_dice(emoji=game_info['emoji'])
            bot_value = bot_msg.dice.value
            game.bot_results.append(bot_value)
            game.bot_rolled_this_round = True
            await asyncio.sleep(3)
            text += f"🤖 Bot: {bot_value}\n👤 You: ?\n\n"
            keyboard = [[InlineKeyboardButton(f"🎲 Roll ({throws - game.user_throws_this_round} left)", callback_data=f"roll_{game_type}")]]
        else:
            text += f"👤 You: ?\n🤖 Bot: ?\n\n"
            keyboard = [[InlineKeyboardButton(f"🎲 Roll ({throws} left)", callback_data=f"roll_{game_type}")]]
        
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Roll dice
    if data.startswith("roll_"):
        game_type = data.replace("roll_", "")
        game = user_games.get(user_id)
        if not game:
            await query.answer("❌ No active game!", show_alert=True)
            return
        
        game_info = GAME_TYPES[game_type]
        
        # User roll
        user_msg = await query.message.reply_dice(emoji=game_info['emoji'])
        user_value = user_msg.dice.value
        game.user_results.append(user_value)
        game.user_throws_this_round += 1
        
        await asyncio.sleep(3)
        
        # Check if round complete
        if game.user_throws_this_round >= game.throw_count:
            # Bot rolls if not already
            if not game.bot_rolled_this_round:
                for _ in range(game.throw_count):
                    bot_msg = await query.message.reply_dice(emoji=game_info['emoji'])
                    game.bot_results.append(bot_msg.dice.value)
                    await asyncio.sleep(3)
            
            # Calculate round scores
            start_idx = game.current_round * game.throw_count
            end_idx = start_idx + game.throw_count
            user_round = sum(game.user_results[start_idx:end_idx])
            bot_round = sum(game.bot_results[start_idx:end_idx])
            
            if user_round > bot_round:
                game.user_score += 1
                result = "✅ You win this round!"
            elif bot_round > user_round:
                game.bot_score += 1
                result = "❌ Bot wins this round!"
            else:
                result = "🤝 Tie!"
            
            game.current_round += 1
            game.user_throws_this_round = 0
            game.bot_rolled_this_round = False
            
            # Check game end
            if game.current_round >= game.total_rounds:
                if game.user_score > game.bot_score:
                    winnings = game.bet_amount * 1.9
                    adjust_user_balance(user_id, winnings)
                    final = f"🎉 <b>YOU WIN!</b>\n\n💰 +{winnings:,.2f} ⭐"
                    update_game_stats(user_id, game_type, game.bet_amount, winnings, True)
                elif game.bot_score > game.user_score:
                    final = f"😢 <b>You Lost</b>\n\n💰 -{game.bet_amount:,.2f} ⭐"
                    update_game_stats(user_id, game_type, game.bet_amount, 0, False)
                else:
                    adjust_user_balance(user_id, game.bet_amount)
                    final = f"🤝 <b>TIE!</b>\n\n💰 Bet returned"
                    update_game_stats(user_id, game_type, game.bet_amount, game.bet_amount, False)
                
                del user_games[user_id]
                keyboard = [[InlineKeyboardButton("🔄 Play Again", callback_data=f"select_game_{game_type}")],
                            [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]]
                await query.edit_message_text(
                    f"{game_info['icon']} <b>Game Over!</b>\n\n👤 You: {game.user_score} | 🤖 Bot: {game.bot_score}\n\n{final}",
                    parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
                return
            
            # Next round
            text = f"{game_info['icon']} <b>Round {game.current_round + 1}/{game.total_rounds}</b>\n\n"
            text += f"📊 Score: 👤 {game.user_score} - {game.bot_score} 🤖\n\n{result}\n\n"
            
            if game.bot_first:
                bot_msg = await query.message.reply_dice(emoji=game_info['emoji'])
                game.bot_results.append(bot_msg.dice.value)
                game.bot_rolled_this_round = True
                await asyncio.sleep(3)
                text += f"🤖 Bot: {bot_msg.dice.value}\n👤 You: ?\n"
            
            keyboard = [[InlineKeyboardButton(f"🎲 Roll ({game.throw_count} left)", callback_data=f"roll_{game_type}")]]
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # More throws in this round
            text = f"{game_info['icon']} <b>Round {game.current_round + 1}/{game.total_rounds}</b>\n\n"
            text += f"👤 Your roll: {user_value}\n"
            remaining = game.throw_count - game.user_throws_this_round
            keyboard = [[InlineKeyboardButton(f"🎲 Roll ({remaining} left)", callback_data=f"roll_{game_type}")]]
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Leaderboards
    if data.startswith("lb_"):
        lb_type = data.replace("lb_", "")
        if lb_type == "balance":
            sorted_users = sorted([(uid, get_user_balance(uid)) for uid in user_profiles.keys() if not is_admin(uid)], key=lambda x: x[1], reverse=True)[:10]
            text = "💰 <b>Top by Balance</b>\n\n"
            for i, (uid, bal) in enumerate(sorted_users, 1):
                name = user_profiles.get(uid, {}).get('username', 'Unknown')
                text += f"{i}. {name}: {bal:,.0f} ⭐\n"
        elif lb_type == "xp":
            sorted_users = sorted([(uid, p.get('xp', 0)) for uid, p in user_profiles.items()], key=lambda x: x[1], reverse=True)[:10]
            text = "⭐ <b>Top by XP</b>\n\n"
            for i, (uid, xp) in enumerate(sorted_users, 1):
                name = user_profiles.get(uid, {}).get('username', 'Unknown')
                text += f"{i}. {name}: {xp:,} XP\n"
        elif lb_type == "games":
            sorted_users = sorted([(uid, p.get('total_games', 0)) for uid, p in user_profiles.items()], key=lambda x: x[1], reverse=True)[:10]
            text = "🎮 <b>Top by Games</b>\n\n"
            for i, (uid, games) in enumerate(sorted_users, 1):
                name = user_profiles.get(uid, {}).get('username', 'Unknown')
                text += f"{i}. {name}: {games} games\n"
        elif lb_type == "wins":
            sorted_users = sorted([(uid, p.get('games_won', 0)) for uid, p in user_profiles.items()], key=lambda x: x[1], reverse=True)[:10]
            text = "🏆 <b>Top by Wins</b>\n\n"
            for i, (uid, wins) in enumerate(sorted_users, 1):
                name = user_profiles.get(uid, {}).get('username', 'Unknown')
                text += f"{i}. {name}: {wins} wins\n"
        else:
            text = "❌ Unknown leaderboard"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_leaderboard")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # View history
    if data == "view_history":
        history = user_game_history.get(user_id, [])[-10:]
        if not history:
            text = "📜 <b>No game history yet!</b>"
        else:
            text = "📜 <b>Recent Games</b>\n\n"
            for g in reversed(history):
                icon = "✅" if g['won'] else "❌"
                gt = GAME_TYPES.get(g['game_type'], {}).get('icon', '🎮')
                text += f"{icon} {gt} {g['bet_amount']}⭐ → {g.get('win_amount', 0)}⭐\n"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_profile")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Deposits
    if data.startswith("deposit_"):
        deposit_data = data.replace("deposit_", "")
        if deposit_data == "custom":
            context.user_data['waiting_for_deposit'] = True
            await query.edit_message_text("✏️ Enter deposit amount (min 50):", parse_mode=ParseMode.HTML)
            return
        try:
            amount = int(deposit_data)
            title = f"Deposit {amount} Stars"
            prices = [LabeledPrice(label="Stars", amount=amount)]
            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title=title,
                description=f"Add {amount} ⭐ to your balance",
                payload=f"deposit_{amount}_{user_id}",
                provider_token=PROVIDER_TOKEN,
                currency="XTR",
                prices=prices
            )
        except Exception as e:
            logger.error(f"Invoice error: {e}")
            await query.edit_message_text("❌ Error creating invoice.", parse_mode=ParseMode.HTML)
        return

    # Withdrawals
    if data == "withdraw_ton":
        context.user_data['withdraw_type'] = 'ton'
        context.user_data['waiting_for_withdraw_amount'] = True
        balance = get_user_balance(user_id)
        await query.edit_message_text(f"💎 <b>TON Withdrawal</b>\n\nBalance: {balance:,.2f} ⭐\nMin: {MIN_WITHDRAWAL} ⭐\n\nEnter amount:", parse_mode=ParseMode.HTML)
        return

    if data.startswith("confirm_withdraw_"):
        parts = data.split("_")
        amount = float(parts[2])
        address = context.user_data.get('withdraw_address')
        if not address:
            await query.answer("❌ Error!", show_alert=True)
            return
        balance = get_user_balance(user_id)
        if amount > balance:
            await query.answer("❌ Insufficient balance!", show_alert=True)
            return
        
        global withdrawal_counter
        withdrawal_counter += 1
        withdraw_id = f"W{withdrawal_counter}"
        
        adjust_user_balance(user_id, -amount)
        ton_amount = amount * STARS_TO_TON
        
        user_withdrawals[withdraw_id] = {
            'user_id': user_id,
            'amount': amount,
            'ton_amount': ton_amount,
            'address': address,
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }
        save_data()
        
        await query.edit_message_text(
            f"✅ <b>Withdrawal Submitted!</b>\n\n🆔 ID: {withdraw_id}\n💰 Amount: {amount:,.0f} ⭐\n💎 TON: {ton_amount:,.4f}\n📍 Address: <code>{address[:20]}...</code>\n\n⏳ Processing 24-48h",
            parse_mode=ParseMode.HTML)
        
        # Notify admin
        for admin_id in admin_list:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 <b>New Withdrawal</b>\n\n🆔 {withdraw_id}\n👤 {user_id}\n💰 {amount:,.0f} ⭐\n💎 {ton_amount:,.4f} TON\n📍 <code>{address}</code>",
                    parse_mode=ParseMode.HTML)
            except: pass
        return

    if data == "cancel_withdraw":
        context.user_data.clear()
        await query.edit_message_text("❌ Withdrawal cancelled.", parse_mode=ParseMode.HTML)
        return

    # Broadcast confirmations
    if data == "broadcast_confirm":
        admin_id = user_id
        await query.edit_message_text("📤 <b>Broadcasting...</b>", parse_mode=ParseMode.HTML)
        asyncio.create_task(execute_broadcast(context, admin_id))
        return

    if data == "broadcast_cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Broadcast cancelled.", parse_mode=ParseMode.HTML)
        return

# ==================== MESSAGE HANDLERS ====================

@handle_errors
@check_ban
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Admin video upload
    if context.user_data.get('waiting_for_video') and is_admin(user_id):
        await update.message.reply_html("❌ Please send a video file, not text.")
        return

    # Broadcast flow
    if context.user_data.get('broadcast_state') and is_admin(user_id):
        state = context.user_data.get('broadcast_state')
        
        if state == 'waiting_content':
            context.user_data['broadcast_type'] = 'text'
            context.user_data['broadcast_content'] = text
            keyboard = [[InlineKeyboardButton("Yes", callback_data="broadcast_add_button"),
                         InlineKeyboardButton("No", callback_data="broadcast_no_button")]]
            await update.message.reply_html("Add inline button?", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data['broadcast_state'] = 'waiting_button_choice'
            return
        
        if state == 'waiting_button_name':
            context.user_data['broadcast_button_name'] = text
            context.user_data['broadcast_state'] = 'waiting_button_url'
            await update.message.reply_html("Enter button URL:")
            return
        
        if state == 'waiting_button_url':
            context.user_data['broadcast_button_url'] = text
            # Show preview
            preview_text = "📢 <b>Preview:</b>\n\n"
            if context.user_data.get('broadcast_type') == 'text':
                preview_text += context.user_data.get('broadcast_content', '')
            else:
                preview_text += f"[{context.user_data.get('broadcast_type').upper()}]"
                if context.user_data.get('broadcast_caption'):
                    preview_text += f"\n{context.user_data.get('broadcast_caption')}"
            preview_text += f"\n\n🔘 Button: {context.user_data.get('broadcast_button_name')}"
            keyboard = [[InlineKeyboardButton("✅ Send", callback_data="broadcast_confirm"),
                         InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]]
            await update.message.reply_html(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data['broadcast_state'] = None
            return

    # Custom bet
    if context.user_data.get('waiting_for_bet'):
        try:
            bet = int(text)
            if bet < 1:
                await update.message.reply_html("❌ Min bet is 1 ⭐")
                return
            balance = get_user_balance(user_id)
            if bet > balance:
                await update.message.reply_html(f"❌ Insufficient balance! You have {balance:,.2f} ⭐")
                return
            context.user_data['bet_amount'] = bet
            context.user_data['waiting_for_bet'] = False
            keyboard = [[InlineKeyboardButton(f"{r}R", callback_data=f"rounds_{r}") for r in [1, 3, 5]]]
            msg = await update.message.reply_html(f"💰 Bet: {bet} ⭐\n\nSelect rounds:", reply_markup=InlineKeyboardMarkup(keyboard))
            track_message_owner(msg.message_id, msg.chat_id, user_id)
        except:
            await update.message.reply_html("❌ Enter a valid number!")
        return

    # Custom deposit
    if context.user_data.get('waiting_for_deposit'):
        try:
            amount = int(text)
            if amount < 50:
                await update.message.reply_html("❌ Min deposit is 50 ⭐")
                return
            context.user_data['waiting_for_deposit'] = False
            prices = [LabeledPrice(label="Stars", amount=amount)]
            await context.bot.send_invoice(
                chat_id=update.message.chat_id,
                title=f"Deposit {amount} Stars",
                description=f"Add {amount} ⭐ to your balance",
                payload=f"deposit_{amount}_{user_id}",
                provider_token=PROVIDER_TOKEN,
                currency="XTR",
                prices=prices
            )
        except:
            await update.message.reply_html("❌ Enter a valid number!")
        return

    # Withdraw amount
    if context.user_data.get('waiting_for_withdraw_amount'):
        try:
            amount = float(text)
            balance = get_user_balance(user_id)
            if amount < MIN_WITHDRAWAL:
                await update.message.reply_html(f"❌ Min withdrawal is {MIN_WITHDRAWAL} ⭐")
                return
            if amount > balance:
                await update.message.reply_html(f"❌ Insufficient balance! You have {balance:,.2f} ⭐")
                return
            context.user_data['withdraw_amount'] = amount
            context.user_data['waiting_for_withdraw_amount'] = False
            context.user_data['waiting_for_withdraw_address'] = True
            await update.message.reply_html("📍 Enter your TON wallet address:")
        except:
            await update.message.reply_html("❌ Enter a valid amount!")
        return

    # Withdraw address
    if context.user_data.get('waiting_for_withdraw_address'):
        address = text.strip()
        if not is_valid_ton_address(address):
            await update.message.reply_html("❌ Invalid TON address! Try again:")
            return
        context.user_data['withdraw_address'] = address
        context.user_data['waiting_for_withdraw_address'] = False
        amount = context.user_data.get('withdraw_amount', 0)
        ton_amount = amount * STARS_TO_TON
        keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_withdraw_{amount}"),
                     InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")]]
        msg = await update.message.reply_html(
            f"💸 <b>Confirm Withdrawal</b>\n\n💰 Amount: {amount:,.0f} ⭐\n💎 TON: {ton_amount:,.4f}\n📍 Address: <code>{address[:30]}...</code>",
            reply_markup=InlineKeyboardMarkup(keyboard))
        track_message_owner(msg.message_id, msg.chat_id, user_id)
        return

@handle_errors
@check_ban
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Broadcast photo
    if context.user_data.get('broadcast_state') == 'waiting_content' and is_admin(user_id):
        photo = update.message.photo[-1]
        context.user_data['broadcast_type'] = 'photo'
        context.user_data['broadcast_content'] = photo.file_id
        context.user_data['broadcast_caption'] = update.message.caption
        keyboard = [[InlineKeyboardButton("Yes", callback_data="broadcast_add_button"),
                     InlineKeyboardButton("No", callback_data="broadcast_no_button")]]
        await update.message.reply_html("Add inline button?", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['broadcast_state'] = 'waiting_button_choice'
        return

@handle_errors
@check_ban  
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global withdraw_video_file_id
    user_id = update.effective_user.id
    
    # Set withdraw video
    if context.user_data.get('waiting_for_video') and is_admin(user_id):
        withdraw_video_file_id = update.message.video.file_id
        context.user_data['waiting_for_video'] = False
        save_data()
        await update.message.reply_html("✅ Withdraw video set!")
        return
    
    # Broadcast video
    if context.user_data.get('broadcast_state') == 'waiting_content' and is_admin(user_id):
        context.user_data['broadcast_type'] = 'video'
        context.user_data['broadcast_content'] = update.message.video.file_id
        context.user_data['broadcast_caption'] = update.message.caption
        keyboard = [[InlineKeyboardButton("Yes", callback_data="broadcast_add_button"),
                     InlineKeyboardButton("No", callback_data="broadcast_no_button")]]
        await update.message.reply_html("Add inline button?", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['broadcast_state'] = 'waiting_button_choice'
        return

# Additional broadcast callbacks
@handle_errors
async def broadcast_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "broadcast_add_button":
        context.user_data['broadcast_state'] = 'waiting_button_name'
        await query.edit_message_text("Enter button name:", parse_mode=ParseMode.HTML)
    elif query.data == "broadcast_no_button":
        # Show preview without button
        preview_text = "📢 <b>Preview:</b>\n\n"
        if context.user_data.get('broadcast_type') == 'text':
            preview_text += context.user_data.get('broadcast_content', '')
        else:
            preview_text += f"[{context.user_data.get('broadcast_type', 'MEDIA').upper()}]"
            if context.user_data.get('broadcast_caption'):
                preview_text += f"\n{context.user_data.get('broadcast_caption')}"
        keyboard = [[InlineKeyboardButton("✅ Send", callback_data="broadcast_confirm"),
                     InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]]
        await query.edit_message_text(preview_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['broadcast_state'] = None

# ==================== PAYMENTS ====================

@handle_errors
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

@handle_errors
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    
    if payload.startswith("deposit_"):
        parts = payload.split("_")
        amount = int(parts[1])
        adjust_user_balance(user_id, amount)
        
        all_bot_users.add(user_id)
        save_data()
        
        transaction_id = generate_transaction_id()
        await update.message.reply_html(
            f"✅ <b>Deposit Successful!</b>\n\n💰 Amount: {amount} ⭐\n🆔 TX: <code>{transaction_id[:20]}...</code>\n\n💰 New Balance: {get_user_balance(user_id):,.2f} ⭐")

# ==================== MAIN ====================

def main():
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("bonus", bonus_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Admin commands
    application.add_handler(CommandHandler("addbalance", addbalance_command))
    application.add_handler(CommandHandler("removebalance", removebalance_command))
    application.add_handler(CommandHandler("checkbalance", checkbalance_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("listadmins", listadmins_command))
    application.add_handler(CommandHandler("setvideo", set_video_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banlist", banlist_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Callbacks
    application.add_handler(CallbackQueryHandler(broadcast_button_callback, pattern="^broadcast_(add_button|no_button)$"))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Payments
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Messages
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
