import logging
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
)
from telegram.constants import ParseMode
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8110271943:AAHq6YIH3XUHJf1E1brsDNzsR9I-_pvf3qw"
GAME_BOT_USERNAME = "@Giveawaysedbot"  # Replace with your game bot username

# Admin tracking
group_admins = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send start message"""
    await update.message.reply_html(
        "🤖 <b>Group Manager Bot</b>\n\n"
        "Add me to your group and make me admin!\n\n"
        "<b>Commands:</b>\n"
        "👥 <b>User Management:</b>\n"
        "/ban - Ban a user\n"
        "/unban - Unban a user\n"
        "/kick - Kick a user\n"
        "/mute - Mute a user\n"
        "/unmute - Unmute a user\n"
        "/tmute - Temporary mute\n\n"
        "⚙️ <b>Settings:</b>\n"
        "/welcome - Toggle welcome message\n"
        "/setwelcome - Set custom welcome\n\n"
        "📊 <b>Info:</b>\n"
        "/info - User info\n"
        "/admins - List admins"
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        user_mention = member.mention_html()
        
        # Create inline button to start game bot
        keyboard = [
            [InlineKeyboardButton("🎮 Play Games", url=f"https://t.me/{GAME_BOT_USERNAME.replace('@', '')}?start=group")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"🎮 Hey {user_mention}!\n\n"
            f"Play: 🎲 /dice 🎳 /bowl 🎯 /arrow 🥅 /football 🏀 /basket\n\n"
            f"Win 💎"
        )
        
        await update.message.reply_html(
            welcome_text,
            reply_markup=reply_markup
        )

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user is admin"""
    chat_id = update.effective_chat.id
    
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def get_user_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract user from command"""
    # Reply to a message
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    
    # User ID or username provided
    if context.args and len(context.args) > 0:
        user_identifier = context.args[0]
        
        try:
            # Try as user ID
            if user_identifier.isdigit():
                user_id = int(user_identifier)
                member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                return member.user
            
            # Try as username
            if user_identifier.startswith('@'):
                user_identifier = user_identifier[1:]
            
            # Search in chat
            return None  # Username lookup requires more complex logic
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    return None

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user from the group"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    # Check if command sender is admin
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ You need to be an admin to use this command!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        await update.message.reply_html(
            "❌ <b>Usage:</b>\n"
            "Reply to a user's message: /ban\n"
            "Or: /ban <user_id>\n"
            "Or: /ban @username"
        )
        return
    
    # Check if target is admin
    if await is_admin(update, context, user.id):
        await update.message.reply_text("❌ Cannot ban an admin!")
        return
    
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_html(
            f"🔨 <b>Banned!</b>\n"
            f"User: {user.mention_html()}\n"
            f"By: {update.effective_user.mention_html()}"
        )
    except Exception as e:
        logger.error(f"Ban error: {e}")
        await update.message.reply_text(f"❌ Failed to ban user: {str(e)}")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user from the group"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ You need to be an admin to use this command!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        await update.message.reply_html(
            "❌ <b>Usage:</b>\n"
            "Reply to a user's message: /unban\n"
            "Or: /unban <user_id>"
        )
        return
    
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_html(
            f"✅ <b>Unbanned!</b>\n"
            f"User: {user.mention_html()}\n"
            f"By: {update.effective_user.mention_html()}"
        )
    except Exception as e:
        logger.error(f"Unban error: {e}")
        await update.message.reply_text(f"❌ Failed to unban user: {str(e)}")

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick a user from the group"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ You need to be an admin to use this command!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        await update.message.reply_html(
            "❌ <b>Usage:</b>\n"
            "Reply to a user's message: /kick\n"
            "Or: /kick <user_id>\n"
            "Or: /kick @username"
        )
        return
    
    if await is_admin(update, context, user.id):
        await update.message.reply_text("❌ Cannot kick an admin!")
        return
    
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_html(
            f"👢 <b>Kicked!</b>\n"
            f"User: {user.mention_html()}\n"
            f"By: {update.effective_user.mention_html()}"
        )
    except Exception as e:
        logger.error(f"Kick error: {e}")
        await update.message.reply_text(f"❌ Failed to kick user: {str(e)}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user in the group"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ You need to be an admin to use this command!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        await update.message.reply_html(
            "❌ <b>Usage:</b>\n"
            "Reply to a user's message: /mute\n"
            "Or: /mute <user_id>\n"
            "Or: /mute @username"
        )
        return
    
    if await is_admin(update, context, user.id):
        await update.message.reply_text("❌ Cannot mute an admin!")
        return
    
    try:
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user.id,
            permissions
        )
        await update.message.reply_html(
            f"🔇 <b>Muted!</b>\n"
            f"User: {user.mention_html()}\n"
            f"By: {update.effective_user.mention_html()}"
        )
    except Exception as e:
        logger.error(f"Mute error: {e}")
        await update.message.reply_text(f"❌ Failed to mute user: {str(e)}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute a user in the group"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ You need to be an admin to use this command!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        await update.message.reply_html(
            "❌ <b>Usage:</b>\n"
            "Reply to a user's message: /unmute\n"
            "Or: /unmute <user_id>"
        )
        return
    
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False
        )
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user.id,
            permissions
        )
        await update.message.reply_html(
            f"🔊 <b>Unmuted!</b>\n"
            f"User: {user.mention_html()}\n"
            f"By: {update.effective_user.mention_html()}"
        )
    except Exception as e:
        logger.error(f"Unmute error: {e}")
        await update.message.reply_text(f"❌ Failed to unmute user: {str(e)}")

async def temp_mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Temporarily mute a user"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ You need to be an admin to use this command!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        await update.message.reply_html(
            "❌ <b>Usage:</b>\n"
            "Reply to a user's message: /tmute <duration>\n"
            "Examples:\n"
            "/tmute 5m - Mute for 5 minutes\n"
            "/tmute 2h - Mute for 2 hours\n"
            "/tmute 1d - Mute for 1 day"
        )
        return
    
    if await is_admin(update, context, user.id):
        await update.message.reply_text("❌ Cannot mute an admin!")
        return
    
    # Parse duration
    if not context.args or (update.message.reply_to_message and len(context.args) < 1):
        duration_arg = context.args[0] if context.args else None
    else:
        duration_arg = context.args[1] if len(context.args) > 1 else context.args[0]
    
    if not duration_arg:
        await update.message.reply_text("❌ Please specify duration (e.g., 5m, 2h, 1d)")
        return
    
    try:
        # Parse duration
        duration_str = duration_arg.lower()
        if duration_str.endswith('m'):
            minutes = int(duration_str[:-1])
            until_date = datetime.now() + timedelta(minutes=minutes)
            duration_text = f"{minutes} minute{'s' if minutes > 1 else ''}"
        elif duration_str.endswith('h'):
            hours = int(duration_str[:-1])
            until_date = datetime.now() + timedelta(hours=hours)
            duration_text = f"{hours} hour{'s' if hours > 1 else ''}"
        elif duration_str.endswith('d'):
            days = int(duration_str[:-1])
            until_date = datetime.now() + timedelta(days=days)
            duration_text = f"{days} day{'s' if days > 1 else ''}"
        else:
            await update.message.reply_text("❌ Invalid duration format! Use: 5m, 2h, or 1d")
            return
        
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user.id,
            permissions,
            until_date=until_date
        )
        await update.message.reply_html(
            f"🔇 <b>Temporarily Muted!</b>\n"
            f"User: {user.mention_html()}\n"
            f"Duration: {duration_text}\n"
            f"By: {update.effective_user.mention_html()}"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid duration format!")
    except Exception as e:
        logger.error(f"Temp mute error: {e}")
        await update.message.reply_text(f"❌ Failed to mute user: {str(e)}")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user information"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    user = await get_user_from_message(update, context)
    
    if not user:
        user = update.effective_user
    
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user.id)
        
        status_emoji = {
            'creator': '👑',
            'administrator': '⭐',
            'member': '👤',
            'restricted': '🔇',
            'left': '👋',
            'kicked': '🚫'
        }
        
        info_text = (
            f"👤 <b>User Info</b>\n\n"
            f"Name: {user.mention_html()}\n"
            f"ID: <code>{user.id}</code>\n"
            f"Username: @{user.username if user.username else 'None'}\n"
            f"Status: {status_emoji.get(member.status, '❓')} {member.status.title()}"
        )
        
        await update.message.reply_html(info_text)
    except Exception as e:
        logger.error(f"User info error: {e}")
        await update.message.reply_text("❌ Failed to get user info")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all group admins"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        
        admin_list = "👥 <b>Group Admins:</b>\n\n"
        
        for admin in admins:
            user = admin.user
            if admin.status == 'creator':
                admin_list += f"👑 {user.mention_html()} (Owner)\n"
            else:
                admin_list += f"⭐ {user.mention_html()}\n"
        
        await update.message.reply_html(admin_list)
    except Exception as e:
        logger.error(f"List admins error: {e}")
        await update.message.reply_text("❌ Failed to get admin list")

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("unmute", unmute_user))
    application.add_handler(CommandHandler("tmute", temp_mute_user))
    application.add_handler(CommandHandler("info", user_info))
    application.add_handler(CommandHandler("admins", list_admins))
    
    # Welcome new members
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Start bot
    logger.info("Group Manager Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
