import logging
import random
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8251256866:AAHXY8QYy0ZdP-89Eyxa7kv-i4Rn2_tmF84"
ADMIN_IDS = [5709159932]  # Replace with your Telegram user ID
STARS_TO_TICKETS_RATIO = 2  # 1 Star = 2 Tickets

# Star packages for quick selection
STAR_PACKAGES = [
    {"stars": 1, "tickets": 2},
    {"stars": 5, "tickets": 10},
    {"stars": 10, "tickets": 20},
    {"stars": 25, "tickets": 50},
]

# In-memory storage (replace with database in production)
users_data = {}  # {user_id: {"tickets": int, "stars_paid": int, "username": str}}
giveaway_active = False
total_pot = 0
banned_users = set()
announcement_groups = set()  # Store group chat IDs for announcements

# Confirmation image
CONFIRMATION_IMAGE = "https://i.pinimg.com/736x/d4/fc/6a/d4fc6a3e8f8e8c0c8f8e8c0c8f8e8c0c.jpg"

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def is_banned(user_id: int) -> bool:
    """Check if user is banned"""
    return user_id in banned_users

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with participate button"""
    welcome_text = (
        "👋 **Welcome to the Nft Giveaway Bot!**\n"
        "_Hosted by @swizzmm_\n\n"
        "💎 Pay Stars to join the giveaway.\n"
        "🎟️ **1 Star = 2 Tickets** — More tickets = Higher chances.\n\n"
        "**Commands:**\n"
        "├─ /join `<stars>` – Enter the giveaway\n"
        "├─ /mytickets – Check your tickets\n"
        "├─ /leaderboard – Top participants\n"
        "└─ /rules – Giveaway details\n\n"
        "Good luck! 🎁"
    )
    
    # Add participate button
    keyboard = [[InlineKeyboardButton("🎯 Participate Now", callback_data="show_packages")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /join command - show packages menu"""
    user = update.effective_user
    user_id = user.id
    
    # Check if banned
    if is_banned(user_id):
        await update.message.reply_text("❌ You are banned from this giveaway.")
        return
    
    # Check if giveaway is active
    if not giveaway_active:
        await update.message.reply_text("❌ No active giveaway at the moment. Please wait for admin to start one!")
        return
    
    # Show packages menu
    await show_star_packages(update, context)

async def show_star_packages(update, context: ContextTypes.DEFAULT_TYPE):
    """Show star packages selection menu"""
    packages_text = (
        "⭐ **SELECT YOUR PACKAGE** ⭐\n\n"
        "Choose how many Stars you want to spend:\n"
        "💎 Remember: **1 Star = 2 Tickets**\n\n"
        "👇 Select a package or enter custom amount:"
    )
    
    # Create inline keyboard with packages
    keyboard = []
    for package in STAR_PACKAGES:
        stars = package["stars"]
        tickets = package["tickets"]
        keyboard.append([InlineKeyboardButton(
            f"⭐ {stars} Stars → 🎟️ {tickets} Tickets",
            callback_data=f"package_{stars}"
        )])
    
    # Add custom amount button
    keyboard.append([InlineKeyboardButton("✏️ Custom Amount", callback_data="custom_amount")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or edit message
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.edit_text(
            packages_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            packages_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

async def send_giveaway_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, stars: int):
    """Send payment invoice for giveaway entry"""
    tickets = stars * STARS_TO_TICKETS_RATIO
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    title = f"⭐ Giveaway Entry - {stars} Stars"
    description = f"🎟️ Get {tickets} tickets for the giveaway! (1 Star = 2 Tickets)"
    payload = f"giveaway_{stars}_{user.id}"
    currency = "XTR"
    
    prices = [LabeledPrice(label=f"{stars} Stars Entry", amount=stars)]
    
    try:
        # Send invoice
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency=currency,
            prices=prices,
        )
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        message = update.callback_query.message if hasattr(update, 'callback_query') else update.message
        await message.reply_text("❌ Error creating payment. Please try again.")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer pre-checkout query"""
    query = update.pre_checkout_query
    
    # Check if giveaway is still active
    if not giveaway_active:
        await query.answer(ok=False, error_message="Giveaway has ended.")
        return
    
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment"""
    global total_pot
    
    payment = update.message.successful_payment
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    
    # Extract stars from payload
    payload_parts = payment.invoice_payload.split("_")
    stars = int(payload_parts[1])
    tickets = stars * STARS_TO_TICKETS_RATIO
    
    # Initialize user data if not exists
    if user_id not in users_data:
        users_data[user_id] = {"tickets": 0, "stars_paid": 0, "username": username}
    
    # Update user data
    users_data[user_id]["tickets"] += tickets
    users_data[user_id]["stars_paid"] += stars
    users_data[user_id]["username"] = username
    
    # Update total pot
    total_pot += stars
    
    logger.info(f"User {user_id} ({username}) paid {stars} Stars, earned {tickets} tickets")
    
    # Delete/clear invoice message
    try:
        await update.message.delete()
    except:
        pass
    
    # Send confirmation to user with custom image
    confirmation_text = (
        f"✅ **Payment received!**\n\n"
        f"You paid **{stars} Stars** and earned **{tickets} tickets!**\n\n"
        f"🎟️ Total tickets: **{users_data[user_id]['tickets']}**\n"
        f"💰 Total Stars paid: **{users_data[user_id]['stars_paid']}**\n\n"
        f"Your entry is added to the leaderboard.\n"
        f"Best of luck 🍀\n\n"
        f"_Hosted by @swizzmm_"
    )
    
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=CONFIRMATION_IMAGE,
            caption=confirmation_text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error sending confirmation image: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=confirmation_text,
            parse_mode="Markdown"
        )
    
    # Send announcement to all registered groups
    await send_group_announcement(context, user, stars, tickets)

async def send_group_announcement(context: ContextTypes.DEFAULT_TYPE, user, stars: int, tickets: int):
    """Send beautiful announcement to all groups"""
    # Create user mention with name
    user_link = f"[{user.first_name}](tg://user?id={user.id})"
    
    # Add username if available
    if user.username:
        user_display = f"{user_link} (@{user.username})"
    else:
        user_display = user_link
    
    # Calculate current position in leaderboard
    sorted_users = sorted(users_data.items(), key=lambda x: x[1]["tickets"], reverse=True)
    position = next((idx + 1 for idx, (uid, _) in enumerate(sorted_users) if uid == user.id), 0)
    
    announcement_text = (
        f"🎉 **NEW ENTRY!** 🎉\n\n"
        f"🌟 {user_display} just joined!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Stars:** `{stars}`\n"
        f"🎟️ **Tickets:** `{tickets}`\n"
        f"📊 **Rank:** #{position}\n"
        f"💰 **Total Pot:** `{total_pot}` ⭐\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 Join now and increase your chances!\n"
        f"Use /join to participate\n\n"
        f"_Hosted by @swizzmm_"
    )
    
    # Send to all registered groups
    for group_id in announcement_groups:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=announcement_text,
                parse_mode="Markdown"
            )
            logger.info(f"Announcement sent to group {group_id}")
        except Exception as e:
            logger.error(f"Failed to send announcement to group {group_id}: {e}")
            # Remove group if bot was kicked/blocked
            if "bot was kicked" in str(e).lower() or "chat not found" in str(e).lower():
                announcement_groups.discard(group_id)

async def mytickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's tickets"""
    user_id = update.effective_user.id
    
    if user_id not in users_data:
        await update.message.reply_text(
            "🎟️ You have **0 tickets**.\n\n"
            "Use `/join <stars>` to enter the giveaway!",
            parse_mode="Markdown"
        )
        return
    
    data = users_data[user_id]
    message = (
        f"🎟️ **Your Tickets**\n\n"
        f"Total Tickets: **{data['tickets']}**\n"
        f"Stars Paid: **{data['stars_paid']}** ⭐\n\n"
        f"_Good luck in the giveaway!_ 🍀"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top participants"""
    if not users_data:
        await update.message.reply_text("📊 No participants yet!\n\nBe the first to join the giveaway! 🎉")
        return
    
    # Sort by tickets (descending)
    sorted_users = sorted(users_data.items(), key=lambda x: x[1]["tickets"], reverse=True)[:10]
    
    leaderboard_text = "🏆 **LEADERBOARD - Top 10**\n\n"
    
    for idx, (user_id, data) in enumerate(sorted_users, 1):
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = f"{idx}."
        
        username = data.get('username', 'Unknown')
        tickets = data.get('tickets', 0)
        stars = data.get('stars_paid', 0)
        
        leaderboard_text += f"{medal} **{username}**\n"
        leaderboard_text += f"   └─ {tickets} tickets ({stars}⭐)\n\n"
    
    leaderboard_text += "━━━━━━━━━━━━━━━━━━━━\n"
    leaderboard_text += "_Hosted by @swizzmm_"
    
    await update.message.reply_text(leaderboard_text, parse_mode="Markdown")

async def pot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total pot"""
    message = (
        f"💰 **Total Pot**\n\n"
        f"⭐ Stars Collected: **{total_pot}**\n"
        f"🎟️ Total Tickets: **{sum(u['tickets'] for u in users_data.values())}**\n"
        f"👥 Participants: **{len(users_data)}**\n\n"
        f"_Hosted by @swizzmm_"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show giveaway rules"""
    rules_text = (
        "📜 **GIVEAWAY RULES**\n\n"
        "1️⃣ Pay Telegram Stars to join\n"
        "2️⃣ 1 Star = 2 Tickets\n"
        "3️⃣ More tickets = Higher winning chance\n"
        "4️⃣ Winner selected randomly (weighted)\n"
        "5️⃣ Winner announced in this chat\n"
        "6️⃣ No refunds after payment\n\n"
        "**Commands:**\n"
        "• `/join <stars>` - Enter giveaway\n"
        "• `/mytickets` - Check your tickets\n"
        "• `/leaderboard` - Top participants\n"
        "• `/pot` - Total prize pool\n\n"
        "_Hosted by @swizzmm_"
    )
    await update.message.reply_text(rules_text, parse_mode="Markdown")

# ============ ADMIN COMMANDS ============

async def startgiveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Start giveaway"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    global giveaway_active
    
    if giveaway_active:
        await update.message.reply_text("⚠️ Giveaway is already active!")
        return
    
    giveaway_active = True
    
    announcement = (
        "🎉 **GIVEAWAY STARTED!** 🎉\n\n"
        "💎 Pay Stars to join the giveaway!\n"
        "🎟️ 1 Star = 2 Tickets\n\n"
        "Use `/join <stars>` to enter!\n"
        "Example: `/join 10`\n\n"
        "_Hosted by @swizzmm_"
    )
    await update.message.reply_text(announcement, parse_mode="Markdown")

async def endgiveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: End giveaway"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    global giveaway_active
    
    if not giveaway_active:
        await update.message.reply_text("⚠️ No active giveaway!")
        return
    
    giveaway_active = False
    
    announcement = (
        "🛑 **GIVEAWAY ENDED!**\n\n"
        f"💰 Total Pot: **{total_pot}** ⭐\n"
        f"🎟️ Total Tickets: **{sum(u['tickets'] for u in users_data.values())}**\n"
        f"👥 Participants: **{len(users_data)}**\n\n"
        "Admin will pick winner soon!\n\n"
        "_Hosted by @swizzmm_"
    )
    await update.message.reply_text(announcement, parse_mode="Markdown")

async def pickwinner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Pick winner (weighted by tickets)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not users_data:
        await update.message.reply_text("❌ No participants!")
        return
    
    # Create weighted list
    tickets_list = []
    for user_id, data in users_data.items():
        tickets_list.extend([user_id] * data["tickets"])
    
    # Pick random winner
    winner_id = random.choice(tickets_list)
    winner_data = users_data[winner_id]
    
    winner_announcement = (
        "🎊 **WINNER ANNOUNCEMENT!** 🎊\n\n"
        f"🏆 Winner: **{winner_data['username']}**\n"
        f"🎟️ Tickets: **{winner_data['tickets']}**\n"
        f"⭐ Stars Paid: **{winner_data['stars_paid']}**\n\n"
        f"💰 Prize Pool: **{total_pot}** Stars\n\n"
        "Congratulations! 🎉\n\n"
        "_Hosted by @swizzmm_"
    )
    
    await update.message.reply_text(winner_announcement, parse_mode="Markdown")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Reset all data"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    global users_data, giveaway_active, total_pot
    
    users_data = {}
    giveaway_active = False
    total_pot = 0
    
    await update.message.reply_text("✅ All data reset successfully!")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Show bot balance"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    balance_text = (
        f"💰 **Bot Balance**\n\n"
        f"⭐ Total Collected: **{total_pot}** Stars\n"
        f"🎟️ Total Tickets: **{sum(u['tickets'] for u in users_data.values())}**\n"
        f"👥 Total Users: **{len(users_data)}**\n"
        f"🚫 Banned Users: **{len(banned_users)}**\n"
        f"📊 Giveaway Status: **{'Active' if giveaway_active else 'Inactive'}**"
    )
    await update.message.reply_text(balance_text, parse_mode="Markdown")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Ban a user"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode="Markdown")
        return
    
    try:
        user_id_to_ban = int(context.args[0])
        banned_users.add(user_id_to_ban)
        await update.message.reply_text(f"✅ User {user_id_to_ban} has been banned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Add current group for announcements"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    announcement_groups.add(chat.id)
    await update.message.reply_text(
        f"✅ Group added for announcements!\n\n"
        f"Group: {chat.title}\n"
        f"ID: `{chat.id}`\n\n"
        f"This group will receive notifications when users buy stars.",
        parse_mode="Markdown"
    )

async def removegroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Remove current group from announcements"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    chat = update.effective_chat
    if chat.id in announcement_groups:
        announcement_groups.discard(chat.id)
        await update.message.reply_text("✅ Group removed from announcements!")
    else:
        await update.message.reply_text("❌ This group is not in the announcement list.")

async def listgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: List all groups receiving announcements"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not announcement_groups:
        await update.message.reply_text("📋 No groups registered for announcements.")
        return
    
    groups_text = "📋 **Announcement Groups:**\n\n"
    for idx, group_id in enumerate(announcement_groups, 1):
        try:
            chat = await context.bot.get_chat(group_id)
            groups_text += f"{idx}. {chat.title}\n   ID: `{group_id}`\n\n"
        except:
            groups_text += f"{idx}. Unknown Group\n   ID: `{group_id}`\n\n"
    
    await update.message.reply_text(groups_text, parse_mode="Markdown")

# ============ CALLBACK HANDLERS ============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Check if banned
    if is_banned(user_id):
        await query.answer("❌ You are banned from this giveaway.", show_alert=True)
        return
    
    # Check if giveaway is active for participation actions
    if query.data in ["show_packages", "package_", "custom_amount"] and not giveaway_active:
        await query.answer("❌ No active giveaway!", show_alert=True)
        return
    
    if query.data == "show_packages":
        # Show star packages menu
        await show_star_packages(update, context)
    
    elif query.data.startswith("package_"):
        # User selected a package
        stars = int(query.data.split("_")[1])
        await send_giveaway_invoice(update, context, stars)
    
    elif query.data == "custom_amount":
        # Prompt for custom amount
        await query.message.reply_text(
            "✏️ **Enter Custom Amount**\n\n"
            "Please enter the number of Stars you want to spend:\n"
            "💎 Remember: **1 Star = 2 Tickets**\n\n"
            "Example: Send `15` to buy 15 Stars (30 tickets)\n"
            "Range: 1-2500 Stars",
            parse_mode="Markdown"
        )
        context.user_data['awaiting_custom_amount'] = True

async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom star amount input"""
    if not context.user_data.get('awaiting_custom_amount'):
        return
    
    user_id = update.effective_user.id
    
    # Check if banned
    if is_banned(user_id):
        await update.message.reply_text("❌ You are banned from this giveaway.")
        return
    
    # Check if giveaway is active
    if not giveaway_active:
        await update.message.reply_text("❌ No active giveaway!")
        return
    
    try:
        stars = int(update.message.text)
        if stars < 1:
            await update.message.reply_text("❌ Please enter a positive number of Stars.")
            return
        if stars > 2500:
            await update.message.reply_text("❌ Maximum 2500 Stars per transaction.")
            return
        
        context.user_data['awaiting_custom_amount'] = False
        await send_giveaway_invoice(update, context, stars)
        
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("mytickets", mytickets_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("pot", pot_command))
    application.add_handler(CommandHandler("rules", rules_command))
    
    # Admin commands
    application.add_handler(CommandHandler("startgiveaway", startgiveaway_command))
    application.add_handler(CommandHandler("endgiveaway", endgiveaway_command))
    application.add_handler(CommandHandler("pickwinner", pickwinner_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("addgroup", addgroup_command))
    application.add_handler(CommandHandler("removegroup", removegroup_command))
    application.add_handler(CommandHandler("listgroups", listgroups_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Custom amount handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_amount))
    
    logger.info("🤖 Giveaway Bot Started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
