import logging
from telethon import TelegramClient, events, Button
from telethon.tl.custom import Message
import asyncio
import os
import re
from datetime import datetime
from collections import defaultdict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Userbot credentials (get from https://my.telegram.org)
API_ID = int(os.environ.get("API_ID", "28782318"))
API_HASH = os.environ.get("API_HASH", "ea72ed0d16604c27198d5dd1a53f2a69")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "+919958369729")

# Your main bot username (without @)
MAIN_BOT_USERNAME = os.environ.get("MAIN_BOT_USERNAME", "@Giveawaysedbot")

# Game emojis
GAME_EMOJIS = {
    'dice': '🎲',
    'bowl': '🎳',
    'arrow': '🎯',
    'football': '⚽',
    'basket': '🏀'
}

# Store active games per group
group_games = {}
user_pending_payments = defaultdict(dict)

class GroupGame:
    def __init__(self, user_id, username, game_type, bet_amount, rounds, throws):
        self.user_id = user_id
        self.username = username
        self.game_type = game_type
        self.bet_amount = bet_amount
        self.total_rounds = rounds
        self.throw_count = throws
        self.current_round = 0
        self.user_results = []
        self.bot_results = []
        self.user_score = 0
        self.bot_score = 0

# Initialize the userbot client
client = TelegramClient('userbot_session', API_ID, API_HASH)

@client.on(events.NewMessage(pattern=r'^/start$'))
async def start_handler(event: events.NewMessage.Event):
    """Handle /start command in groups"""
    if not event.is_group:
        return
    
    chat_id = event.chat_id
    user = await event.get_sender()
    user_id = user.id
    username = user.username or user.first_name
    
    welcome_text = (
        f"🐱 <b>Welcome to Lenrao Game, {username}!</b>\n\n"
        f"⭐️ Lenrao Game - Play mini-games and win Stars!\n\n"
        f"<b>📢 How to start:</b>\n"
        f"1. Choose a game: /dice /bowl /arrow /football /basket\n"
        f"2. Select your bet amount\n"
        f"3. Make payment in bot DM\n"
        f"4. Play and win!\n\n"
        f"💡 All payments are processed securely through @{MAIN_BOT_USERNAME}"
    )
    
    await event.reply(
        welcome_text,
        parse_mode='html',
        link_preview=False
    )

@client.on(events.NewMessage(pattern=r'^/(dice|bowl|arrow|football|basket)$'))
async def game_handler(event: events.NewMessage.Event):
    """Handle game commands in groups"""
    if not event.is_group:
        return
    
    game_type = event.pattern_match.group(1)
    user = await event.get_sender()
    user_id = user.id
    username = user.username or user.first_name
    chat_id = event.chat_id
    
    # Check if user already has an active game
    game_key = f"{chat_id}_{user_id}"
    if game_key in group_games:
        await event.reply(
            f"❌ {username}, you already have an active game! Finish it first.",
            parse_mode='html'
        )
        return
    
    game_names = {
        'dice': '🎲 Dice',
        'bowl': '🎳 Bowling',
        'arrow': '🎯 Darts',
        'football': '⚽ Football',
        'basket': '🏀 Basketball'
    }
    
    # Create betting buttons
    buttons = [
        [
            Button.inline("10 ⭐", f"bet_{game_type}_10_{user_id}"),
            Button.inline("25 ⭐", f"bet_{game_type}_25_{user_id}"),
        ],
        [
            Button.inline("50 ⭐", f"bet_{game_type}_50_{user_id}"),
            Button.inline("100 ⭐", f"bet_{game_type}_100_{user_id}"),
        ]
    ]
    
    await event.reply(
        f"{game_names[game_type]} <b>Game</b>\n\n"
        f"👤 Player: {username}\n"
        f"💰 Select your bet amount:",
        buttons=buttons,
        parse_mode='html'
    )

@client.on(events.CallbackQuery(pattern=r'^bet_(\w+)_(\d+)_(\d+)$'))
async def bet_callback(event: events.CallbackQuery.Event):
    """Handle bet selection"""
    if not event.is_group:
        return
    
    user = await event.get_sender()
    user_id = user.id
    
    # Extract data from callback
    match = re.match(r'^bet_(\w+)_(\d+)_(\d+)$', event.data.decode())
    game_type = match.group(1)
    bet_amount = int(match.group(2))
    button_user_id = int(match.group(3))
    
    # Check if the user clicking is the same as the one who started
    if user_id != button_user_id:
        await event.answer("❌ This is not your game!", alert=True)
        return
    
    username = user.username or user.first_name
    
    # Ask for rounds
    buttons = [
        [
            Button.inline("1 Round", f"rounds_{game_type}_{bet_amount}_1_{user_id}"),
            Button.inline("2 Rounds", f"rounds_{game_type}_{bet_amount}_2_{user_id}"),
        ],
        [
            Button.inline("3 Rounds", f"rounds_{game_type}_{bet_amount}_3_{user_id}"),
        ]
    ]
    
    await event.edit(
        f"💰 Bet: <b>{bet_amount} ⭐</b>\n\n"
        f"🔄 Select number of rounds:",
        buttons=buttons,
        parse_mode='html'
    )

@client.on(events.CallbackQuery(pattern=r'^rounds_(\w+)_(\d+)_(\d+)_(\d+)$'))
async def rounds_callback(event: events.CallbackQuery.Event):
    """Handle rounds selection"""
    if not event.is_group:
        return
    
    user = await event.get_sender()
    user_id = user.id
    
    match = re.match(r'^rounds_(\w+)_(\d+)_(\d+)_(\d+)$', event.data.decode())
    game_type = match.group(1)
    bet_amount = int(match.group(2))
    rounds = int(match.group(3))
    button_user_id = int(match.group(4))
    
    if user_id != button_user_id:
        await event.answer("❌ This is not your game!", alert=True)
        return
    
    # Ask for throws
    buttons = [
        [
            Button.inline("1 Throw", f"throws_{game_type}_{bet_amount}_{rounds}_1_{user_id}"),
            Button.inline("2 Throws", f"throws_{game_type}_{bet_amount}_{rounds}_2_{user_id}"),
        ],
        [
            Button.inline("3 Throws", f"throws_{game_type}_{bet_amount}_{rounds}_3_{user_id}"),
        ]
    ]
    
    await event.edit(
        f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
        f"🔄 Rounds: <b>{rounds}</b>\n\n"
        f"🎯 Select throws per round:",
        buttons=buttons,
        parse_mode='html'
    )

@client.on(events.CallbackQuery(pattern=r'^throws_(\w+)_(\d+)_(\d+)_(\d+)_(\d+)$'))
async def throws_callback(event: events.CallbackQuery.Event):
    """Handle throws selection and create payment button"""
    if not event.is_group:
        return
    
    user = await event.get_sender()
    user_id = user.id
    
    match = re.match(r'^throws_(\w+)_(\d+)_(\d+)_(\d+)_(\d+)$', event.data.decode())
    game_type = match.group(1)
    bet_amount = int(match.group(2))
    rounds = int(match.group(3))
    throws = int(match.group(4))
    button_user_id = int(match.group(5))
    
    if user_id != button_user_id:
        await event.answer("❌ This is not your game!", alert=True)
        return
    
    username = user.username or user.first_name
    chat_id = event.chat_id
    
    # Store pending payment info
    payment_key = f"{chat_id}_{user_id}"
    user_pending_payments[payment_key] = {
        'game_type': game_type,
        'bet_amount': bet_amount,
        'rounds': rounds,
        'throws': throws,
        'username': username
    }
    
    # Create payment button that opens the main bot
    payment_button = [
        [Button.url(
            f"💳 Pay {bet_amount} ⭐",
            f"https://t.me/{MAIN_BOT_USERNAME}?start=grouppay_{chat_id}_{user_id}_{game_type}_{bet_amount}_{rounds}_{throws}"
        )]
    ]
    
    await event.edit(
        f"🎮 <b>Game Configuration Complete!</b>\n\n"
        f"👤 Player: {username}\n"
        f"💰 Bet: <b>{bet_amount} ⭐</b>\n"
        f"🔄 Rounds: <b>{rounds}</b>\n"
        f"🎯 Throws: <b>{throws}</b>\n\n"
        f"💳 Click the button below to pay in bot DM:",
        buttons=payment_button,
        parse_mode='html'
    )

@client.on(events.NewMessage(pattern=r'^/confirm_payment (\d+) (\d+) (\w+) (\d+) (\d+) (\d+)$'))
async def confirm_payment(event: events.NewMessage.Event):
    """Confirm payment and start game (triggered by main bot via PM)"""
    # This message should come from the main bot or be sent by you manually
    # Format: /confirm_payment <chat_id> <user_id> <game_type> <bet_amount> <rounds> <throws>
    
    # Only accept from bot owner or specific bot
    if event.sender_id != (await client.get_me()).id:
        return
    
    parts = event.pattern_match.groups()
    chat_id = int(parts[0])
    user_id = int(parts[1])
    game_type = parts[2]
    bet_amount = int(parts[3])
    rounds = int(parts[4])
    throws = int(parts[5])
    
    # Get user info
    try:
        user = await client.get_entity(user_id)
        username = user.username or user.first_name
    except:
        await event.reply("❌ Could not find user")
        return
    
    # Create game
    game_key = f"{chat_id}_{user_id}"
    game = GroupGame(user_id, username, game_type, bet_amount, rounds, throws)
    group_games[game_key] = game
    
    # Send confirmation in group
    emoji = GAME_EMOJIS.get(game_type, '🎮')
    await client.send_message(
        chat_id,
        f"✅ <b>Payment confirmed!</b>\n\n"
        f"👤 Player: {username}\n"
        f"💰 Paid: <b>{bet_amount} ⭐</b>\n\n"
        f"🎮 <b>Game Started!</b>\n"
        f"Send {throws}x {emoji} to play Round 1!",
        parse_mode='html'
    )
    
    await event.reply(f"✅ Game started in group for {username}")

@client.on(events.NewMessage)
async def handle_game_dice(event: events.NewMessage.Event):
    """Handle dice throws in active games"""
    if not event.is_group:
        return
    
    if not event.dice:
        return
    
    user = await event.get_sender()
    user_id = user.id
    username = user.username or user.first_name
    chat_id = event.chat_id
    
    game_key = f"{chat_id}_{user_id}"
    if game_key not in group_games:
        return
    
    game = group_games[game_key]
    emoji = GAME_EMOJIS.get(game.game_type)
    
    if event.dice.emoji != emoji:
        return
    
    user_value = event.dice.value
    game.user_results.append(user_value)
    
    # Check if round is complete
    if len(game.user_results) % game.throw_count == 0:
        await asyncio.sleep(0.5)
        
        # Bot throws
        bot_results = []
        for _ in range(game.throw_count):
            bot_msg = await event.reply(file=event.dice)
            bot_results.append(bot_msg.dice.value)
            await asyncio.sleep(0.3)
        
        game.bot_results.extend(bot_results)
        
        # Calculate round totals
        round_start = game.current_round * game.throw_count
        user_round_total = sum(game.user_results[round_start:round_start + game.throw_count])
        bot_round_total = sum(bot_results)
        
        game.current_round += 1
        
        # Determine round winner
        if user_round_total > bot_round_total:
            game.user_score += 1
            round_result = "✅ You won this round!"
        elif bot_round_total > user_round_total:
            game.bot_score += 1
            round_result = "❌ Bot won this round!"
        else:
            round_result = "🤝 This round is a tie!"
        
        await asyncio.sleep(2)
        
        # Check if game is complete
        if game.current_round < game.total_rounds:
            await event.reply(
                f"<b>Round {game.current_round} Results:</b>\n\n"
                f"👤 {username}: <b>{user_round_total}</b>\n"
                f"🤖 Bot: <b>{bot_round_total}</b>\n\n"
                f"{round_result}\n\n"
                f"📊 Score: <b>{game.user_score}</b> - <b>{game.bot_score}</b>\n\n"
                f"Send {game.throw_count}x {emoji} for Round {game.current_round + 1}!",
                parse_mode='html'
            )
        else:
            # Game complete
            if game.user_score > game.bot_score:
                winnings = game.bet_amount * 2
                result_text = f"🎉 <b>{username} WON!</b> 🎉\n\n💰 Winnings: <b>{winnings} ⭐</b>"
                result_emoji = "🏆"
            elif game.bot_score > game.user_score:
                result_text = f"😔 <b>{username} lost!</b>\n\n💸 Lost: <b>{game.bet_amount} ⭐</b>"
                result_emoji = "💔"
            else:
                result_text = f"🤝 <b>It's a tie!</b>\n\n💰 Bet returned: <b>{game.bet_amount} ⭐</b>"
                result_emoji = "🤝"
            
            await event.reply(
                f"{result_emoji} <b>GAME OVER</b> {result_emoji}\n\n"
                f"<b>Final Round Results:</b>\n"
                f"👤 {username}: <b>{user_round_total}</b>\n"
                f"🤖 Bot: <b>{bot_round_total}</b>\n\n"
                f"{round_result}\n\n"
                f"📊 Final Score: <b>{game.user_score}</b> - <b>{game.bot_score}</b>\n\n"
                f"{result_text}",
                parse_mode='html'
            )
            
            # Notify main bot to update balance
            # You'll need to implement this endpoint in your main bot
            
            # Clean up
            del group_games[game_key]

@client.on(events.NewMessage(pattern=r'^/balance$'))
async def balance_handler(event: events.NewMessage.Event):
    """Check balance in group"""
    if not event.is_group:
        return
    
    user = await event.get_sender()
    username = user.username or user.first_name
    
    # Direct user to bot DM for balance
    button = [[Button.url(
        "💰 Check Balance",
        f"https://t.me/{MAIN_BOT_USERNAME}?start=balance"
    )]]
    
    await event.reply(
        f"👤 {username}\n\n"
        f"💰 Click below to check your balance in bot DM:",
        buttons=button
    )

@client.on(events.NewMessage(pattern=r'^/help$'))
async def help_handler(event: events.NewMessage.Event):
    """Show help in group"""
    if not event.is_group:
        return
    
    help_text = (
        "🎯 <b>How to Play:</b>\n\n"
        "1️⃣ Choose game: /dice /bowl /arrow /football /basket\n"
        "2️⃣ Select bet, rounds, throws\n"
        "3️⃣ Pay in @{} DM\n"
        "4️⃣ Send emojis to play\n"
        "5️⃣ Win Stars!\n\n"
        "💡 <b>Commands:</b>\n"
        "/start - Welcome message\n"
        "/balance - Check balance\n"
        "/help - This message\n\n"
        "🎮 <b>Games:</b>\n"
        "🎲 /dice - Dice game\n"
        "🎳 /bowl - Bowling\n"
        "🎯 /arrow - Darts\n"
        "⚽ /football - Football\n"
        "🏀 /basket - Basketball"
    ).format(MAIN_BOT_USERNAME)
    
    await event.reply(help_text, parse_mode='html')

async def main():
    """Start the userbot"""
    await client.start(phone=PHONE_NUMBER)
    logger.info("Userbot started successfully!")
    
    me = await client.get_me()
    logger.info(f"Logged in as: {me.username or me.first_name} ({me.id})")
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    client.loop.run_until_complete(main())
