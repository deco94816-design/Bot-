import logging
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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y"
PROVIDER_TOKEN = ""  # Stars don't need provider token
ADMIN_ID = 5709159932  # Admin chat ID

# Game state storage (thread-safe for 100+ users)
user_games = {}
user_balances = defaultdict(int)
game_locks = defaultdict(asyncio.Lock)

# Game types configuration
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    user = update.effective_user
    
    # Check if admin
    is_admin = user.id == ADMIN_ID
    admin_text = "\n\n🔑 <b>Admin Commands:</b>\n/demo - Test all games without payment" if is_admin else ""
    
    welcome_text = (
        f"🎮 <b>Welcome to Multi-Game Bot, {user.mention_html()}!</b>\n\n"
        f"💰 <b>Commands:</b>\n"
        f"/deposit - Add Stars to balance\n"
        f"/custom <amount> - Custom deposit\n"
        f"/balance - Check balance\n\n"
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
    """Show help message"""
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
    """Check user balance"""
    user_id = update.effective_user.id
    balance = user_balances[user_id]
    await update.message.reply_html(
        f"💰 Your balance: <b>{balance} ⭐</b>"
    )

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit options"""
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

async def custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom deposit amount"""
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
        
        # Send invoice
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
    """Generic function to start any game"""
    user_id = update.effective_user.id
    
    async with game_locks[user_id]:
        # Check if user already has an active game
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
        
        # Store game type in context
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

# Game command handlers
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
    """Admin only - Demo all games without payment"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id != ADMIN_ID:
        await update.message.reply_html("❌ This command is only for administrators.")
        return
    
    # Check if already has active game
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        # Handle deposit
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
        
        # Handle demo game selection
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
        
        # Back to demo menu
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
        
        # Handle demo bet selection
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
        
        # Handle bet selection
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
        
        # Handle rounds selection
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
        
        # Handle throw count selection - start game
        if data.startswith("throws_"):
            async with game_locks[user_id]:
                parts = data.split("_")
                game_type = parts[1]
                throw_count = int(parts[2])
                bet_amount = context.user_data.get('bet_amount', 10)
                rounds = context.user_data.get('rounds', 1)
                is_demo = context.user_data.get('is_demo', False)
                
                # Deduct bet from balance (skip for demo)
                if not is_demo:
                    user_balances[user_id] -= bet_amount
                
                # Create game
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
                
                # Clear throw tracking
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
        
        # Handle withdraw
        if data == "withdraw":
            balance = user_balances[user_id]
            if balance < 10:
                await query.answer("❌ Minimum withdrawal is 10 ⭐", show_alert=True)
                return
            
            await query.answer("💰 Withdrawal feature coming soon!", show_alert=True)
            return
        
        # Handle check balance
        if data == "check_balance":
            balance = user_balances[user_id]
            await query.answer(f"💰 Your balance: {balance} ⭐", show_alert=True)
            return
        
        # Handle replay
        if data.startswith("replay_"):
            async with game_locks[user_id]:
                multiplier = 1 if data == "replay_same" else 2
                
                if user_id not in user_games:
                    await query.answer("❌ No previous game found!", show_alert=True)
                    return
                
                old_game = user_games[user_id]
                new_bet = old_game.bet_amount * multiplier
                balance = user_balances[user_id]
                
                # Skip balance check for demo mode
                if not old_game.is_demo and balance < new_bet:
                    await query.answer("❌ Insufficient balance!", show_alert=True)
                    return
                
                # Deduct bet (skip for demo)
                if not old_game.is_demo:
                    user_balances[user_id] -= new_bet
                
                # Create new game
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
                
                # Clear throw tracking
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
        
        # Cancel game
        if data == "cancel_game":
            await query.edit_message_text("❌ Game cancelled.")
            return
            
    except Exception as e:
        logger.error(f"Button callback error for user {user_id}: {e}")
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

async def handle_game_throw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user game throws (dice, bowl, arrow, football, basket)"""
    user_id = update.effective_user.id
    
    try:
        async with game_locks[user_id]:
            game = user_games.get(user_id)
            
            if not game:
                return
            
            # Check if waiting for throws
            if game.current_round >= game.total_rounds:
                return
            
            throw_message = update.message.dice
            game_info = GAME_TYPES[game.game_type]
            
            if not throw_message or throw_message.emoji != game_info['emoji']:
                await update.message.reply_text(f"❌ Please send {game_info['emoji']}")
                return
            
            # Initialize throw tracking
            if 'current_round_user_throws' not in context.user_data:
                context.user_data['current_round_user_throws'] = []
                context.user_data['current_round_bot_throws'] = []
            
            user_throws = context.user_data['current_round_user_throws']
            user_throws.append(throw_message.value)
            
            # Send bot throw immediately
            bot_throw_msg = await update.message.reply_dice(emoji=game_info['emoji'])
            
            # Wait for animation
            await asyncio.sleep(4)
            
            bot_throws = context.user_data['current_round_bot_throws']
            bot_throws.append(bot_throw_msg.dice.value)
            
            # Check if we have all throws for this round
            if len(user_throws) < game.throw_count:
                remaining = game.throw_count - len(user_throws)
                await update.message.reply_text(f"{game_info['emoji']} Send {remaining} more!")
                return
            
            # All throws collected, calculate round
            game.current_round += 1
            
            user_total = sum(user_throws)
            bot_total = sum(bot_throws)
            
            # Store results
            game.user_results.append(user_total)
            game.bot_results.append(bot_total)
            
            # Update scores
            if user_total > bot_total:
                game.user_score += 1
            elif bot_total > user_total:
                game.bot_score += 1
            
            # Clear throws for next round
            context.user_data['current_round_user_throws'] = []
            context.user_data['current_round_bot_throws'] = []
            
            # Show round stats (only scores)
            user_link = f'<a href="tg://user?id={user_id}">{game.username}</a>'
            
            stats_text = (
                f"🎳 <b>Score</b>\n\n"
                f"{user_link}: {game.user_score} points\n"
                f"🤖 Lenrao Game: {game.bot_score} points"
            )
            
            # Check if game is over
            if game.current_round >= game.total_rounds:
                await show_final_stats(update, game, context)
            else:
                keyboard = [[InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_html(
                    stats_text,
                    reply_markup=reply_markup
                )
                
                throw_emoji = game_info['emoji'] * game.throw_count
                await update.message.reply_text(f"{throw_emoji} Send your throws for next round!")
                
    except Exception as e:
        logger.error(f"Handle throw error for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred. Please start a new game.")
        # Clean up
        if user_id in user_games:
            del user_games[user_id]

async def show_final_stats(update: Update, game: Game, context: ContextTypes.DEFAULT_TYPE):
    """Show final game statistics"""
    try:
        user_link = f'<a href="tg://user?id={game.user_id}">{game.username}</a>'
        bot_name = "🤖 Lenrao Game"
        
        demo_badge = " 🔑" if game.is_demo else ""
        
        # Determine winner
        if game.user_score > game.bot_score:
            winner = user_link
            winner_score = game.user_score
            loser = bot_name
            loser_score = game.bot_score
            winnings = game.bet_amount * 2
            
            # Add winnings (skip for demo)
            if not game.is_demo:
                user_balances[game.user_id] += winnings
            
            result_emoji = "🎉"
            result_text = "YOU WIN!"
        elif game.bot_score > game.user_score:
            winner = bot_name
            winner_score = game.bot_score
            loser = user_link
            loser_score = game.user_score
            winnings = game.bet_amount * 2
            result_emoji = "😢"
            result_text = "YOU LOSE!"
        else:
            # Draw - return bet (skip for demo)
            if not game.is_demo:
                user_balances[game.user_id] += game.bet_amount
            winner = "DRAW"
            winner_score = game.user_score
            loser = ""
            loser_score = game.bot_score
            winnings = game.bet_amount
            result_emoji = "🤝"
            result_text = "IT'S A DRAW!"
        
        game_info = GAME_TYPES[game.game_type]
        
        # Build final stats
        stats_text = (
            f"{result_emoji} <b>{result_text}</b>{demo_badge}\n\n"
            f"🎮 <b>Game: {game_info['name']}</b>\n"
            f"💰 Bet: <b>{game.bet_amount} ⭐</b>\n"
            f"🎯 Rounds: <b>{game.total_rounds}</b>\n\n"
            f"📊 <b>Final Score:</b>\n"
            f"{user_link}: {game.user_score} points\n"
            f"{bot_name}: {game.bot_score} points\n\n"
        )
        
        if winner != "DRAW":
            stats_text += f"🏆 Winner: {winner}\n"
            if not game.is_demo:
                stats_text += f"💎 Winnings: <b>{winnings} ⭐</b>\n"
        else:
            if not game.is_demo:
                stats_text += f"💰 Bet returned: <b>{winnings} ⭐</b>\n"
        
        if not game.is_demo:
            stats_text += f"\n💰 New balance: <b>{user_balances[game.user_id]} ⭐</b>"
        
        # Replay buttons
        keyboard = [
            [
                InlineKeyboardButton("🔄 Play Again", callback_data="replay_same"),
                InlineKeyboardButton("⬆️ Double Bet", callback_data="replay_double"),
            ],
            [
                InlineKeyboardButton("💰 Balance", callback_data="check_balance"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            stats_text,
            reply_markup=reply_markup
        )
        
        # Clean up game
        del user_games[game.user_id]
        
    except Exception as e:
        logger.error(f"Show final stats error: {e}")
        await update.message.reply_text("❌ An error occurred displaying results.")
        if game.user_id in user_games:
            del user_games[game.user_id]

async def send_invoice(query, amount: int):
    """Send payment invoice"""
    try:
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
        await query.edit_message_text("💳 Invoice sent! Complete the payment below.")
    except Exception as e:
        logger.error(f"Send invoice error: {e}")
        await query.edit_message_text("❌ Failed to create invoice. Please try again.")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout query"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment"""
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    
    try:
        # Extract amount from payload
        payload_parts = payment.invoice_payload.split("_")
        amount = int(payload_parts[1])
        
        # Add to balance
        user_balances[user_id] += amount
        
        await update.message.reply_html(
            f"✅ <b>Payment successful!</b>\n\n"
            f"💰 Added: <b>{amount} ⭐</b>\n"
            f"💰 New balance: <b>{user_balances[user_id]} ⭐</b>\n\n"
            f"🎮 Ready to play! Use /dice, /bowl, /arrow, /football, or /basket"
        )
    except Exception as e:
        logger.error(f"Payment callback error: {e}")
        await update.message.reply_text("❌ Payment processed but an error occurred.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom deposit amount input"""
    user_id = update.effective_user.id
    
    # Check if waiting for custom amount
    if context.user_data.get('waiting_for_custom_amount'):
        try:
            amount = int(update.message.text)
            
            if amount < 1:
                await update.message.reply_html("❌ Minimum deposit is 1 ⭐")
                return
            
            if amount > 2500:
                await update.message.reply_html("❌ Maximum deposit is 2500 ⭐")
                return
            
            # Clear waiting flag
            context.user_data['waiting_for_custom_amount'] = False
            
            # Send invoice
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
            await update.message.reply_html("❌ Invalid amount! Please enter a number.")
        except Exception as e:
            logger.error(f"Custom amount input error: {e}")
            await update.message.reply_html("❌ An error occurred. Please try again.")

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("deposit", deposit_command))
    application.add_handler(CommandHandler("custom", custom_deposit))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("bowl", bowl_command))
    application.add_handler(CommandHandler("arrow", arrow_command))
    application.add_handler(CommandHandler("football", football_command))
    application.add_handler(CommandHandler("basket", basket_command))
    application.add_handler(CommandHandler("demo", demo_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Game throw handlers
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_game_throw))
    
    # Text message handler for custom deposit
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Start bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
