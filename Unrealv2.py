import logging
import random
import json
import asyncio
import aiohttp
from datetime import datetime
from telethon import TelegramClient, events, types
from collections import defaultdict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== CONFIGURATION ==========
API_ID = 0  # Get from https://my.telegram.org
API_HASH = ""  # Get from https://my.telegram.org
PHONE_NUMBER = ""  # Your phone number
BOT_USERNAME = ""  # Main bot username (e.g., @yourbotname)
BOT_TOKEN = ""  # Main bot token for sending invoices
ADMIN_USER_ID = 0  # Set your admin Telegram user ID here

# ========== DATA STORAGE ==========
allowed_groups = set()
user_games = {}
user_balances = defaultdict(float)
game_locks = defaultdict(asyncio.Lock)
user_profiles = {}
user_game_history = defaultdict(list)
pending_payments = {}

ADMIN_BALANCE = 9999999999
STARS_TO_USD = 0.0179
STARS_TO_TON = 0.01201014
MIN_WITHDRAWAL = 100

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

class Game:
    def __init__(self, user_id, username, bet_amount, rounds, throw_count, game_type, chat_id):
        self.user_id = user_id
        self.username = username
        self.bet_amount = bet_amount
        self.total_rounds = rounds
        self.throw_count = throw_count
        self.game_type = game_type
        self.chat_id = chat_id
        self.current_round = 0
        self.user_score = 0
        self.bot_score = 0
        self.user_results = []
        self.bot_results = []

def is_admin(user_id):
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID and ADMIN_USER_ID != 0

def ensure_admin_balance():
    """Ensure admin always has unlimited balance"""
    if ADMIN_USER_ID != 0:
        user_balances[ADMIN_USER_ID] = ADMIN_BALANCE

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

def save_data():
    """Save data to file"""
    try:
        data = {
            'allowed_groups': list(allowed_groups),
            'user_balances': dict(user_balances),
            'user_profiles': {k: {**v, 'registration_date': v['registration_date'].isoformat(), 
                                  'game_counts': dict(v['game_counts'])} 
                             for k, v in user_profiles.items()},
            'user_game_history': {k: [{**g, 'timestamp': g['timestamp'].isoformat()} 
                                       for g in v] 
                                  for k, v in user_game_history.items()}
        }
        with open('userbot_data.json', 'w') as f:
            json.dump(data, f, indent=2)
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def load_data():
    """Load data from file"""
    global allowed_groups, user_balances, user_profiles, user_game_history
    try:
        with open('userbot_data.json', 'r') as f:
            data = json.load(f)
        
        allowed_groups = set(data.get('allowed_groups', []))
        user_balances = defaultdict(float, {int(k): float(v) for k, v in data.get('user_balances', {}).items()})
        
        profiles = data.get('user_profiles', {})
        for k, v in profiles.items():
            v['registration_date'] = datetime.fromisoformat(v['registration_date'])
            v['game_counts'] = defaultdict(int, v['game_counts'])
            user_profiles[int(k)] = v
        
        history = data.get('user_game_history', {})
        for k, v in history.items():
            for game in v:
                game['timestamp'] = datetime.fromisoformat(game['timestamp'])
            user_game_history[int(k)] = v
        
        logger.info(f"Data loaded: {len(allowed_groups)} groups, {len(user_balances)} users")
    except FileNotFoundError:
        logger.info("No existing data file found, starting fresh")
    except Exception as e:
        logger.error(f"Error loading data: {e}")

# ========== TELEGRAM CLIENT ==========
client = TelegramClient('userbot_session', API_ID, API_HASH)

@client.on(events.NewMessage(pattern='/addgroup', incoming=True))
async def add_group(event):
    """Admin adds a group by chat ID"""
    if event.is_private:
        try:
            parts = event.message.text.split()
            if len(parts) < 2:
                await event.reply(
                    "📝 **Add Group**\n\n"
                    "Usage: `/addgroup <chat_id>`\n"
                    "Example: `/addgroup -1001234567890`\n\n"
                    "💡 To get chat ID:\n"
                    "1. Forward a message from the group to @userinfobot\n"
                    "2. It will show you the chat ID"
                )
                return
            
            chat_id = int(parts[1])
            
            try:
                chat = await client.get_entity(chat_id)
                allowed_groups.add(chat_id)
                save_data()
                
                await event.reply(
                    f"✅ **Group Added Successfully!**\n\n"
                    f"📝 Chat ID: `{chat_id}`\n"
                    f"📛 Name: {chat.title}\n"
                    f"🎮 Total groups: {len(allowed_groups)}\n\n"
                    f"Userbot is now active in this group!"
                )
                
                await client.send_message(
                    chat_id,
                    "🎮 **Game Bot Activated!**\n\n"
                    "⚙️ Available Commands:\n\n"
                    "/dice       → 🎲 Roll a Dice\n"
                    "/arrow      → 🎯 Throw a Dart\n"
                    "/bowl       → 🎳 Bowling Score\n"
                    "/football   → ⚽ Shoot a Ball\n"
                    "/basket     → 🏀 Throw a Basketball\n"
                    "/deposit    → 💳 Add stars to play\n"
                    "/bal        → 💰 Check your balance\n"
                    "/tip        → 💸 Send stars to others\n\n"
                    "💬 Type /help for full command list!"
                )
                
            except ValueError:
                await event.reply("❌ Invalid chat ID! Chat not found.")
            except Exception as e:
                await event.reply(f"❌ Error accessing chat: {str(e)}")
                
        except ValueError:
            await event.reply("❌ Invalid chat ID format! Must be a number.")
        except Exception as e:
            logger.error(f"Add group error: {e}")
            await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/removegroup', incoming=True))
async def remove_group(event):
    """Admin removes a group"""
    if event.is_private:
        try:
            parts = event.message.text.split()
            if len(parts) < 2:
                await event.reply(
                    "📝 **Remove Group**\n\n"
                    "Usage: `/removegroup <chat_id>`\n"
                    "Example: `/removegroup -1001234567890`"
                )
                return
            
            chat_id = int(parts[1])
            
            if chat_id in allowed_groups:
                allowed_groups.remove(chat_id)
                save_data()
                
                await event.reply(
                    f"✅ **Group Removed!**\n\n"
                    f"📝 Chat ID: `{chat_id}`\n"
                    f"🎮 Remaining groups: {len(allowed_groups)}"
                )
            else:
                await event.reply("❌ This group is not in the allowed list!")
                
        except ValueError:
            await event.reply("❌ Invalid chat ID format!")
        except Exception as e:
            logger.error(f"Remove group error: {e}")
            await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/listgroups', incoming=True))
async def list_groups(event):
    """Admin lists all allowed groups"""
    if event.is_private:
        if not allowed_groups:
            await event.reply("📝 No groups added yet!\n\nUse /addgroup to add groups.")
            return
        
        msg = f"📝 **Allowed Groups** ({len(allowed_groups)}):\n\n"
        for idx, chat_id in enumerate(allowed_groups, 1):
            try:
                chat = await client.get_entity(chat_id)
                msg += f"{idx}. {chat.title}\n   ID: `{chat_id}`\n\n"
            except:
                msg += f"{idx}. Chat ID: `{chat_id}`\n\n"
        
        await event.reply(msg)

@client.on(events.NewMessage(pattern='/bal', incoming=True))
async def balance_command(event):
    """Check balance"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    user_id = event.sender_id
    balance = user_balances.get(user_id, 0)
    balance_usd = balance * STARS_TO_USD
    
    user = await event.get_sender()
    username = user.first_name
    
    await event.reply(
        f"💰 **Balance for {username}**\n\n"
        f"⭐ Stars: **{balance:,.0f}**\n"
        f"💵 USD: **${balance_usd:.2f}**"
    )

@client.on(events.NewMessage(pattern='/deposit', incoming=True))
async def deposit_command(event):
    """Deposit stars"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    try:
        parts = event.message.text.split()
        
        if len(parts) < 2:
            await event.reply(
                "💳 **Deposit Stars**\n\n"
                "Usage: `/deposit <amount>`\n"
                "Example: `/deposit 100`\n\n"
                "💡 Minimum: 1 ⭐\n"
                "💡 Maximum: 2500 ⭐"
            )
            return
        
        amount = int(parts[1])
        
        if amount < 1:
            await event.reply("❌ Minimum deposit is 1 ⭐")
            return
        
        if amount > 2500:
            await event.reply("❌ Maximum deposit is 2500 ⭐")
            return
        
        user_id = event.sender_id
        
        payment_id = f"pay_{user_id}_{int(datetime.now().timestamp())}"
        pending_payments[payment_id] = {
            'user_id': user_id,
            'amount': amount,
            'chat_id': event.chat_id,
            'timestamp': datetime.now()
        }
        
        await event.reply(
            f"💳 **Processing Deposit Request...**\n\n"
            f"⭐ Amount: **{amount}**\n"
            f"💵 USD: **${amount * STARS_TO_USD:.2f}**\n\n"
            f"⏳ Sending invoice from bot..."
        )
        
        success = await send_invoice_via_bot(user_id, amount, payment_id)
        
        if success:
            await asyncio.sleep(1)
            await client.send_message(
                event.chat_id,
                f"✅ **Invoice sent!**\n\n"
                f"📬 Check your PM from @{BOT_USERNAME}\n"
                f"💳 Click the invoice to pay {amount} ⭐"
            )
        else:
            await event.reply(
                f"❌ **Failed to send invoice!**\n\n"
                f"Make sure you've started @{BOT_USERNAME}"
            )
            del pending_payments[payment_id]
        
    except ValueError:
        await event.reply("❌ Invalid amount! Please enter a number.")
    except Exception as e:
        logger.error(f"Deposit error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

async def send_invoice_via_bot(user_id, amount, payment_id):
    """Send Telegram Stars invoice"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
        
        payload = {
            "chat_id": user_id,
            "title": f"Deposit {amount} Stars",
            "description": f"Add {amount} ⭐ to your game balance",
            "payload": payment_id,
            "currency": "XTR",
            "prices": [{"label": "Stars", "amount": amount}]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                
                if result.get("ok"):
                    logger.info(f"Invoice sent to user {user_id} for {amount} stars")
                    return True
                else:
                    logger.error(f"Failed to send invoice: {result}")
                    return False
    except Exception as e:
        logger.error(f"Send invoice error: {e}")
        return False

async def check_payment_status():
    """Monitor payments and auto-confirm"""
    while True:
        try:
            await asyncio.sleep(2)
            
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"offset": -1, "timeout": 1}) as response:
                    result = await response.json()
                    
                    if not result.get("ok"):
                        continue
                    
                    updates = result.get("result", [])
                    
                    for update in updates:
                        if "message" in update:
                            message = update["message"]
                            
                            if "successful_payment" in message:
                                payment = message["successful_payment"]
                                payment_id = payment.get("invoice_payload")
                                user_id = message["from"]["id"]
                                amount = payment["total_amount"]
                                
                                if payment_id in pending_payments:
                                    payment_info = pending_payments[payment_id]
                                    
                                    if payment_info['user_id'] == user_id and payment_info['amount'] == amount:
                                        user_balances[user_id] += amount
                                        save_data()
                                        
                                        chat_id = payment_info['chat_id']
                                        
                                        try:
                                            user = await client.get_entity(user_id)
                                            username = user.first_name
                                            
                                            await client.send_message(
                                                chat_id,
                                                f"✅ **Payment Confirmed!**\n\n"
                                                f"👤 Player: {username}\n"
                                                f"💰 Added: **{amount} ⭐**\n"
                                                f"💳 New balance: **{user_balances[user_id]:,.0f} ⭐**\n\n"
                                                f"🎮 Ready to play!"
                                            )
                                        except Exception as e:
                                            logger.error(f"Notification error: {e}")
                                        
                                        try:
                                            await client.send_message(
                                                user_id,
                                                f"✅ **Deposit Successful!**\n\n"
                                                f"💰 Added: **{amount} ⭐**\n"
                                                f"💳 New balance: **{user_balances[user_id]:,.0f} ⭐**"
                                            )
                                        except:
                                            pass
                                        
                                        del pending_payments[payment_id]
                                        logger.info(f"Payment confirmed: {user_id} paid {amount} stars")
        
        except Exception as e:
            logger.error(f"Payment check error: {e}")
            await asyncio.sleep(5)

@client.on(events.NewMessage(pattern='/tip', incoming=True))
async def tip_command(event):
    """Tip stars to another user"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    try:
        tipper_id = event.sender_id
        tipper = await event.get_sender()
        tipper_name = tipper.first_name
        
        parts = event.message.text.split()
        
        if len(parts) < 2:
            await event.reply(
                "💸 **Tip Stars**\n\n"
                "Usage:\n"
                "• `/tip <amount>` - Reply to a message\n"
                "• `/tip <amount> @username` - Tip by username\n\n"
                "Examples:\n"
                "• `/tip 100` (reply to someone)\n"
                "• `/tip 500 @john`\n\n"
                f"💰 Your balance: **{user_balances.get(tipper_id, 0):,.0f} ⭐**"
            )
            return
        
        try:
            amount = int(parts[1])
        except ValueError:
            await event.reply("❌ Invalid amount! Please enter a number.")
            return
        
        if amount < 1:
            await event.reply("❌ Minimum tip is 1 ⭐")
            return
        
        if not is_admin(tipper_id):
            tipper_balance = user_balances.get(tipper_id, 0)
            if tipper_balance < amount:
                await event.reply(
                    f"❌ **Insufficient balance!**\n\n"
                    f"Your balance: **{tipper_balance:,.0f} ⭐**\n"
                    f"Tip amount: **{amount} ⭐**"
                )
                return
        
        recipient_id = None
        recipient_name = None
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            recipient_id = reply_msg.sender_id
            recipient = await reply_msg.get_sender()
            recipient_name = recipient.first_name
        elif len(parts) >= 3:
            username = parts[2].lstrip('@')
            try:
                recipient = await client.get_entity(username)
                recipient_id = recipient.id
                recipient_name = recipient.first_name
            except Exception as e:
                await event.reply(f"❌ User @{username} not found!")
                return
        
        if not recipient_id:
            await event.reply(
                "❌ **No recipient found!**\n\n"
                "Please either:\n"
                "1. Reply to someone's message\n"
                "2. Mention username: `/tip 100 @username`"
            )
            return
        
        if recipient_id == tipper_id:
            await event.reply("❌ You can't tip yourself!")
            return
        
        if not is_admin(tipper_id):
            user_balances[tipper_id] -= amount
        else:
            ensure_admin_balance()
        
        user_balances[recipient_id] = user_balances.get(recipient_id, 0) + amount
        
        get_or_create_profile(tipper_id, tipper_name)
        get_or_create_profile(recipient_id, recipient_name)
        
        save_data()
        
        success_msg = (
            f"💸 **Tip Successful!**\n\n"
            f"👤 From: {tipper_name}\n"
            f"👤 To: {recipient_name}\n"
            f"💰 Amount: **{amount} ⭐** (${amount * STARS_TO_USD:.2f})\n\n"
        )
        
        if not is_admin(tipper_id):
            tipper_new_balance = user_balances.get(tipper_id, 0)
            success_msg += f"💳 Your new balance: **{tipper_new_balance:,.0f} ⭐**\n"
        
        recipient_new_balance = user_balances.get(recipient_id, 0)
        success_msg += f"🎁 {recipient_name}'s balance: **{recipient_new_balance:,.0f} ⭐**"
        
        await event.reply(success_msg)
        
        try:
            await client.send_message(
                recipient_id,
                f"🎁 **You received a tip!**\n\n"
                f"👤 From: {tipper_name}\n"
                f"💰 Amount: **{amount} ⭐** (${amount * STARS_TO_USD:.2f})\n"
                f"💳 Your new balance: **{recipient_new_balance:,.0f} ⭐**"
            )
        except:
            pass
        
        logger.info(f"Tip: {tipper_name} → {recipient_name}: {amount} stars")
        
    except Exception as e:
        logger.error(f"Tip error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/rain', incoming=True))
async def rain_command(event):
    """Rain stars to multiple users (admin only)"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    if not is_admin(event.sender_id):
        await event.reply("❌ This command is only for admins!")
        return
    
    try:
        parts = event.message.text.split()
        
        if len(parts) < 3:
            await event.reply(
                "🌧️ **Rain Stars**\n\n"
                "Usage: `/rain <amount> <users>`\n"
                "Example: `/rain 100 10`"
            )
            return
        
        amount_per_user = int(parts[1])
        num_users = int(parts[2])
        
        if amount_per_user < 1:
            await event.reply("❌ Amount must be at least 1 ⭐")
            return
        
        if num_users < 1 or num_users > 50:
            await event.reply("❌ Users must be between 1 and 50")
            return
        
        active_users = {}
        async for message in client.iter_messages(event.chat_id, limit=100):
            if message.sender_id and message.sender_id != event.sender_id:
                if message.sender_id not in active_users:
                    try:
                        user = await message.get_sender()
                        if user and not user.bot:
                            active_users[message.sender_id] = user.first_name
                    except:
                        pass
            
            if len(active_users) >= num_users:
                break
        
        if not active_users:
            await event.reply("❌ No active users found!")
            return
        
        selected_users = list(active_users.items())[:num_users]
        total_amount = amount_per_user * len(selected_users)
        
        rain_msg = "🌧️ **STAR RAIN!** 🌧️\n\n"
        
        for user_id, username in selected_users:
            user_balances[user_id] = user_balances.get(user_id, 0) + amount_per_user
            get_or_create_profile(user_id, username)
            rain_msg += f"💰 {username}: +{amount_per_user} ⭐\n"
        
        ensure_admin_balance()
        save_data()
        
        rain_msg += (
            f"\n**═══════════════════**\n"
            f"👥 Recipients: {len(selected_users)}\n"
            f"💸 Per user: {amount_per_user} ⭐\n"
            f"💰 Total: {total_amount} ⭐\n"
            f"**═══════════════════**"
        )
        
        await event.reply(rain_msg)
        
    except ValueError:
        await event.reply("❌ Invalid parameters!")
    except Exception as e:
        logger.error(f"Rain error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/addbal', incoming=True))
async def addbal_command(event):
    """Admin adds balance to user"""
    if not is_admin(event.sender_id):
        return
    
    try:
        parts = event.message.text.split()
        
        if len(parts) < 3:
            await event.reply(
                "💰 **Add Balance**\n\n"
                "Usage: `/addbal <user_id> <amount>`\n"
                "Example: `/addbal 123456789 1000`"
            )
            return
        
        user_id = int(parts[1])
        amount = int(parts[2])
        
        if amount < 1:
            await event.reply("❌ Amount must be positive!")
            return
        
        user_balances[user_id] = user_balances.get(user_id, 0) + amount
        save_data()
        
        try:
            user = await client.get_entity(user_id)
            username = user.first_name
        except:
            username = "Unknown"
        
        await event.reply(
            f"✅ **Balance Added!**\n\n"
            f"👤 User: {username}\n"
            f"💰 Added: **{amount} ⭐**\n"
            f"💳 New balance: **{user_balances[user_id]:,.0f} ⭐**"
        )
        
        try:
            await client.send_message(
                user_id,
                f"🎁 **Balance Added!**\n\n"
                f"💰 You received: **{amount} ⭐**\n"
                f"💳 Your new balance: **{user_balances[user_id]:,.0f} ⭐**"
            )
        except:
            pass
        
    except ValueError:
        await event.reply("❌ Invalid parameters!")
    except Exception as e:
        logger.error(f"Add balance error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/removebal', incoming=True))
async def removebal_command(event):
    """Admin removes balance from user"""
    if not is_admin(event.sender_id):
        return
    
    try:
        parts = event.message.text.split()
        
        if len(parts) < 3:
            await event.reply(
                "💸 **Remove Balance**\n\n"
                "Usage: `/removebal <user_id> <amount>`\n"
                "Example: `/removebal 123456789 500`"
            )
            return
        
        user_id = int(parts[1])
        amount = int(parts[2])
        
        if amount < 1:
            await event.reply("❌ Amount must be positive!")
            return
        
        current_balance = user_balances.get(user_id, 0)
        new_balance = max(0, current_balance - amount)
        user_balances[user_id] = new_balance
        save_data()
        
        try:
            user = await client.get_entity(user_id)
            username = user.first_name
        except:
            username = "Unknown"
        
        await event.reply(
            f"✅ **Balance Removed!**\n\n"
            f"👤 User: {username}\n"
            f"💸 Removed: **{amount} ⭐**\n"
            f"💳 New balance: **{new_balance:,.0f} ⭐**"
        )
        
    except ValueError:
        await event.reply("❌ Invalid parameters!")
    except Exception as e:
        logger.error(f"Remove balance error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/profile', incoming=True))
async def profile_command(event):
    """View profile"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    user_id = event.sender_id
    user = await event.get_sender()
    username = user.first_name
    
    profile = get_or_create_profile(user_id, username)
    balance = user_balances.get(user_id, 0)
    balance_usd = balance * STARS_TO_USD
    
    rank_level = get_user_rank(profile['xp'])
    rank_info = get_rank_info(rank_level)
    
    if rank_level < 20:
        next_rank_info = get_rank_info(rank_level + 1)
        rank_display = f"{rank_info['emoji']} {rank_info['name']} (Lvl {rank_level})\n📊 {profile['xp']}/{next_rank_info['xp_required']} XP"
    else:
        rank_display = f"{rank_info['emoji']} {rank_info['name']} (MAX)\n🌌 {profile['xp']} XP"
    
    fav_game = profile.get('favorite_game')
    if fav_game and fav_game in GAME_TYPES:
        fav_game_display = f"{GAME_TYPES[fav_game]['icon']} {GAME_TYPES[fav_game]['name']}"
    else:
        fav_game_display = "None"
    
    biggest_win = profile.get('biggest_win', 0)
    biggest_win_display = f"${biggest_win * STARS_TO_USD:.2f}" if biggest_win > 0 else "None"
    
    total_bets_usd = profile.get('total_bets', 0) * STARS_TO_USD
    total_wins_usd = profile.get('total_wins', 0) * STARS_TO_USD
    
    await event.reply(
        f"👤 **Profile: {username}**\n\n"
        f"⬆️ Rank: {rank_display}\n"
        f"💰 Balance: ${balance_usd:.2f}\n\n"
        f"⚡️ Total games: {profile.get('total_games', 0)}\n"
        f"💵 Total bets: ${total_bets_usd:.2f}\n"
        f"🏆 Total wins: ${total_wins_usd:.2f}\n\n"
        f"🎲 Favorite: {fav_game_display}\n"
        f"🎉 Biggest win: {biggest_win_display}"
    )

@client.on(events.NewMessage(pattern='/history', incoming=True))
async def history_command(event):
    """View game history"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    user_id = event.sender_id
    profile = get_or_create_profile(user_id)
    history = user_game_history.get(user_id, [])
    
    total_games = profile.get('total_games', 0)
    games_won = profile.get('games_won', 0)
    games_lost = profile.get('games_lost', 0)
    total_bets = profile.get('total_bets', 0)
    total_wins = profile.get('total_wins', 0)
    total_losses = profile.get('total_losses', 0)
    
    win_rate = (games_won / total_games * 100) if total_games > 0 else 0
    net_profit = (total_wins - total_losses) * STARS_TO_USD
    
    msg = (
        f"📊 **Game History**\n\n"
        f"🎮 Total: {total_games}\n"
        f"✅ Won: {games_won}\n"
        f"❌ Lost: {games_lost}\n"
        f"📈 Win Rate: {win_rate:.1f}%\n\n"
        f"💰 Financial:\n"
        f"💵 Bets: ${total_bets * STARS_TO_USD:.2f}\n"
        f"🏆 Wins: ${total_wins * STARS_TO_USD:.2f}\n"
        f"📉 Losses: ${total_losses * STARS_TO_USD:.2f}\n"
        f"{'📈' if net_profit >= 0 else '📉'} Net: ${net_profit:.2f}\n"
    )
    
    if history:
        msg += "\n📜 **Recent Games:**\n"
        for game in list(reversed(history))[:5]:
            game_type = game['game_type']
            game_info = GAME_TYPES.get(game_type, {'icon': '🎮', 'name': 'Unknown'})
            status = "✅" if game['won'] else "❌"
            bet_usd = game['bet_amount'] * STARS_TO_USD
            timestamp = game['timestamp'].strftime("%m/%d %H:%M")
            msg += f"{game_info['icon']} {status} ${bet_usd:.2f} - {timestamp}\n"
    
    await event.reply(msg)

async def start_game(event, game_type):
    """Start a game"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    user_id = event.sender_id
    chat_id = event.chat_id
    
    async with game_locks[user_id]:
        if user_id in user_games:
            await event.reply("❌ You already have an active game!")
            return
        
        try:
            parts = event.message.text.split()
            
            if len(parts) < 2:
                game_info = GAME_TYPES[game_type]
                await event.reply(
                    f"{game_info['icon']} **{game_info['name']} Game**\n\n"
                    f"Usage: `/{game_type} <bet> [rounds] [throws]`\n\n"
                    f"Examples:\n"
                    f"• `/{game_type} 100`\n"
                    f"• `/{game_type} 50 3`\n"
                    f"• `/{game_type} 100 2 3`\n\n"
                    f"💰 Balance: **{user_balances.get(user_id, 0):,.0f} ⭐**"
                )
                return
            
            bet_amount = int(parts[1])
            rounds = int(parts[2]) if len(parts) > 2 else 1
            throws = int(parts[3]) if len(parts) > 3 else 1
            
            if bet_amount < 1:
                await event.reply("❌ Bet must be at least 1 ⭐")
                return
            
            if rounds < 1 or rounds > 3:
                await event.reply("❌ Rounds must be 1-3")
                return
            
            if throws < 1 or throws > 3:
                await event.reply("❌ Throws must be 1-3")
                return
            
            balance = user_balances.get(user_id, 0)
            if balance < bet_amount:
                await event.reply(
                    f"❌ **Insufficient balance!**\n\n"
                    f"Balance: **{balance:,.0f} ⭐**\n"
                    f"Bet: **{bet_amount} ⭐**"
                )
                return
            
            user_balances[user_id] -= bet_amount
            save_data()
            
            user = await event.get_sender()
            username = user.first_name
            
            game = Game(
                user_id=user_id,
                username=username,
                bet_amount=bet_amount,
                rounds=rounds,
                throw_count=throws,
                game_type=game_type,
                chat_id=chat_id
            )
            
            user_games[user_id] = game
            
            game_info = GAME_TYPES[game_type]
            
            await event.reply(
                f"{game_info['icon']} **═══════════════════**\n"
                f"**GAME STARTED!**\n"
                f"**═══════════════════**\n\n"
                f"👤 Player: **{username}**\n"
                f"💰 Bet: **{bet_amount} ⭐**\n"
                f"🔄 Rounds: **{rounds}**\n"
                f"🎯 Throws: **{throws}**\n"
                f"🎮 Game: **{game_info['name']}**\n\n"
                f"**═══════════════════**\n"
                f"🎲 **Round 1:** Send {throws}x {game_info['emoji']}\n"
                f"**═══════════════════**"
            )
            
        except ValueError:
            await event.reply("❌ Invalid parameters!")
        except Exception as e:
            logger.error(f"Start game error: {e}")
            await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/dice'))
async def dice_command(event):
    await start_game(event, 'dice')

@client.on(events.NewMessage(pattern='/arrow'))
async def arrow_command(event):
    await start_game(event, 'arrow')

@client.on(events.NewMessage(pattern='/bowl'))
async def bowl_command(event):
    await start_game(event, 'bowl')

@client.on(events.NewMessage(pattern='/football'))
async def football_command(event):
    await start_game(event, 'football')

@client.on(events.NewMessage(pattern='/basket'))
async def basket_command(event):
    await start_game(event, 'basket')

@client.on(events.NewMessage)
async def handle_dice(event):
    """Handle dice messages"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    if not event.dice:
        return
    
    user_id = event.sender_id
    
    if user_id not in user_games:
        return
    
    game = user_games[user_id]
    game_info = GAME_TYPES[game.game_type]
    
    if event.dice.emoticon != game_info['emoji']:
        return
    
    try:
        user_value = event.dice.value
        game.user_results.append(user_value)
        
        if len(game.user_results) % game.throw_count == 0:
            await asyncio.sleep(1)
            
            bot_results = []
            for _ in range(game.throw_count):
                bot_msg = await client.send_message(game.chat_id, file=event.dice)
                bot_results.append(random.randint(1, game_info['max_value']))
                await asyncio.sleep(0.5)
            
            game.bot_results.extend(bot_results)
            
            round_start = game.current_round * game.throw_count
            user_round_total = sum(game.user_results[round_start:round_start + game.throw_count])
            bot_round_total = sum(game.bot_results[round_start:round_start + game.throw_count])
            
            game.current_round += 1
            
            if user_round_total > bot_round_total:
                game.user_score += 1
                round_result = "✅ You won this round!"
            elif bot_round_total > user_round_total:
                game.bot_score += 1
                round_result = "❌ Bot won this round!"
            else:
                round_result = "🤝 Tie!"
            
            await asyncio.sleep(1.5)
            
            if game.current_round < game.total_rounds:
                await client.send_message(
                    game.chat_id,
                    f"**Round {game.current_round} Results:**\n\n"
                    f"👤 You: **{user_round_total}**\n"
                    f"🤖 Bot: **{bot_round_total}**\n\n"
                    f"{round_result}\n\n"
                    f"📊 Score: **{game.user_score}** - **{game.bot_score}**\n\n"
                    f"🎲 Round {game.current_round + 1}: Send {game.throw_count}x {game_info['emoji']}"
                )
            else:
                user = await client.get_entity(user_id)
                username = user.first_name
                
                if game.user_score > game.bot_score:
                    winnings = game.bet_amount * 2
                    user_balances[user_id] += winnings
                    update_game_stats(user_id, game.game_type, game.bet_amount, winnings, True)
                    result_text = f"🎉 **{username} WON!** 🎉\n\n💰 Winnings: **{winnings} ⭐**"
                elif game.bot_score > game.user_score:
                    update_game_stats(user_id, game.game_type, game.bet_amount, 0, False)
                    result_text = f"😔 **{username} lost!**\n\n💸 Lost: **{game.bet_amount} ⭐**"
                else:
                    user_balances[user_id] += game.bet_amount
                    result_text = f"🤝 **Tie!**\n\n💰 Returned: **{game.bet_amount} ⭐**"
                
                save_data()
                balance = user_balances.get(user_id, 0)
                
                await client.send_message(
                    game.chat_id,
                    f"**Final Results:**\n\n"
                    f"👤 You: **{user_round_total}**\n"
                    f"🤖 Bot: **{bot_round_total}**\n\n"
                    f"{round_result}\n\n"
                    f"📊 Final: **{game.user_score}** - **{game.bot_score}**\n\n"
                    f"{result_text}\n\n"
                    f"💰 Balance: **{balance:,.0f} ⭐**"
                )
                
                del user_games[user_id]
    
    except Exception as e:
        logger.error(f"Handle dice error: {e}")
        await client.send_message(game.chat_id, f"❌ Error: {str(e)}")
        if user_id in user_games:
            user_balances[user_id] += game.bet_amount
            save_data()
            del user_games[user_id]

@client.on(events.NewMessage(pattern='/cancel'))
async def cancel_game(event):
    """Cancel active game"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    user_id = event.sender_id
    
    if user_id in user_games:
        game = user_games[user_id]
        user_balances[user_id] += game.bet_amount
        save_data()
        del user_games[user_id]
        await event.reply("❌ Game cancelled. Bet refunded.")
    else:
        await event.reply("❌ No active game.")

@client.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    """Show help"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    help_msg = (
        "🎮 **Game Bot Help**\n\n"
        "**Games:**\n"
        "🎲 `/dice <bet>` - Dice\n"
        "🎯 `/arrow <bet>` - Darts\n"
        "🎳 `/bowl <bet>` - Bowling\n"
        "⚽ `/football <bet>` - Football\n"
        "🏀 `/basket <bet>` - Basketball\n\n"
        "**Account:**\n"
        "💳 `/deposit <amount>` - Add stars\n"
        "💰 `/bal` - Check balance\n"
        "👤 `/profile` - View profile\n"
        "📊 `/history` - Game history\n\n"
        "**Social:**\n"
        "💸 `/tip <amount>` - Tip (reply)\n"
        "💸 `/tip <amount> @user` - Tip user\n\n"
        "**How to Play:**\n"
        "1. `/deposit 100` - Add stars\n"
        "2. `/dice 50` - Start game\n"
        "3. Send dice emoji 🎲\n"
        "4. Highest score wins!"
    )
    
    if is_admin(event.sender_id):
        help_msg += (
            "\n\n**👑 Admin:**\n"
            "🌧️ `/rain <amt> <users>`\n"
            "💰 `/addbal <id> <amt>`\n"
            "💸 `/removebal <id> <amt>`\n"
            "📢 `/broadcast <msg>`\n"
            "📊 `/status`"
        )
    
    await event.reply(help_msg)

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    """Bot status"""
    if event.is_private:
        await event.reply(
            f"📊 **Bot Status**\n\n"
            f"👥 Users: {len(user_balances)}\n"
            f"🎮 Active games: {len(user_games)}\n"
            f"📝 Groups: {len(allowed_groups)}\n"
            f"💰 Total balance: {sum(user_balances.values()):,.0f} ⭐\n"
            f"⏳ Pending: {len(pending_payments)}\n\n"
            f"✅ Running!"
        )

@client.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_command(event):
    """Broadcast to groups"""
    if not event.is_private:
        return
    
    try:
        parts = event.message.text.split(maxsplit=1)
        if len(parts) < 2:
            await event.reply("Usage: `/broadcast <message>`")
            return
        
        message = parts[1]
        success = 0
        failed = 0
        
        for chat_id in allowed_groups:
            try:
                await client.send_message(chat_id, f"📢 **Announcement**\n\n{message}")
                success += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Broadcast failed: {e}")
                failed += 1
        
        await event.reply(f"✅ Sent: {success}\n❌ Failed: {failed}")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    """Bot statistics"""
    if event.is_group and event.chat_id not in allowed_groups:
        return
    
    total_users = len(user_profiles)
    total_games = sum(p.get('total_games', 0) for p in user_profiles.values())
    total_bets = sum(p.get('total_bets', 0) for p in user_profiles.values())
    total_wins = sum(p.get('total_wins', 0) for p in user_profiles.values())
    
    top_players = sorted(
        user_profiles.items(),
        key=lambda x: x[1].get('xp', 0),
        reverse=True
    )[:5]
    
    stats_msg = (
        f"📊 **Statistics**\n\n"
        f"👥 Players: {total_users}\n"
        f"🎮 Games: {total_games}\n"
        f"💵 Wagered: ${total_bets * STARS_TO_USD:.2f}\n"
        f"🏆 Won: ${total_wins * STARS_TO_USD:.2f}\n\n"
    )
    
    if top_players:
        stats_msg += "🏆 **Top Players:**\n\n"
        for idx, (uid, profile) in enumerate(top_players, 1):
            rank_level = get_user_rank(profile['xp'])
            rank_info = get_rank_info(rank_level)
            username = profile.get('username', 'Unknown')
            stats_msg += f"{idx}. {rank_info['emoji']} {username} - {profile['xp']} XP\n"
    
    await event.reply(stats_msg)

@client.on(events.NewMessage(pattern='/cleardata'))
async def clear_data(event):
    """Clear user data"""
    if not event.is_private:
        return
    
    try:
        parts = event.message.text.split()
        if len(parts) < 2:
            await event.reply("Usage: `/cleardata <user_id>`")
            return
        
        user_id = int(parts[1])
        
        if user_id in user_balances:
            del user_balances[user_id]
        if user_id in user_profiles:
            del user_profiles[user_id]
        if user_id in user_game_history:
            del user_game_history[user_id]
        if user_id in user_games:
            del user_games[user_id]
        
        save_data()
        await event.reply(f"✅ Data cleared for user `{user_id}`")
    except ValueError:
        await event.reply("❌ Invalid user ID!")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")

async def cleanup_pending_payments():
    """Cleanup expired payments"""
    while True:
        try:
            await asyncio.sleep(600)
            now = datetime.now()
            expired = []
            
            for payment_id, info in pending_payments.items():
                if (now - info['timestamp']).seconds > 600:
                    expired.append(payment_id)
            
            for payment_id in expired:
                del pending_payments[payment_id]
            
            if expired:
                logger.info(f"Cleaned {len(expired)} expired payments")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    """Main function"""
    load_data()
    ensure_admin_balance()
    
    asyncio.create_task(cleanup_pending_payments())
    asyncio.create_task(check_payment_status())
    
    await client.start(phone=PHONE_NUMBER)
    logger.info("Userbot started!")
    
    me = await client.get_me()
    logger.info(f"Logged in as: {me.first_name} (@{me.username})")
    
    admin_status = "✅ Enabled" if ADMIN_USER_ID != 0 else "⚠️ Not set"
    
    await client.send_message(
        'me',
        f"✅ **Userbot Started!**\n\n"
        f"👤 Account: {me.first_name}\n"
        f"🎮 Groups: {len(allowed_groups)}\n"
        f"👥 Users: {len(user_balances)}\n"
        f"🤖 Bot: @{BOT_USERNAME}\n"
        f"👑 Admin: {admin_status}\n\n"
        f"💳 Auto-payment: ✅\n"
        f"💸 Tipping: ✅\n\n"
        f"Use /help for commands!"
    )
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        save_data()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        save_data()
