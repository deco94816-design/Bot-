"""
Telegram Stars Payment & Gift Bot
==================================
- User sends /pingme -> pays 1 star -> receives 100 stars gift
- Admin sends "1" -> bot sends gift directly (no payment needed)

Setup:
1. Get bot token from @BotFather
2. Enable Stars payments: @BotFather -> Your Bot -> Payments -> Telegram Stars
3. Get your admin ID from @userinfobot
4. Install: pip install python-telegram-bot[all]
5. Set BOT_TOKEN and ADMIN_IDS below
6. Run: python telegram_stars_bot.py
"""

import logging
import os
from telegram import (
    Update,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# ============================================
# CONFIGURATION - EDIT THESE VALUES
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8005843558:AAF9Lr7wGjhLb9Eubz2hluYVaNV9orpQlj0")
ADMIN_IDS = [5709159932]  # Replace with your Telegram user ID(s)

PAYMENT_AMOUNT = 1   # User pays 1 star
GIFT_AMOUNT = 100    # Bot gifts 100 stars
# ============================================

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============================================
# USER COMMANDS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"🌟 Use /pingme to pay {PAYMENT_AMOUNT} Star and receive {GIFT_AMOUNT} Stars gift!\n\n"
        f"Commands:\n"
        f"/pingme - Pay 1 Star & Get 100 Stars Gift\n"
        f"/help - Show help message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    await update.message.reply_text(
        "🌟 Telegram Stars Bot 🌟\n\n"
        "How it works:\n"
        "1. Send /pingme command\n"
        "2. Pay 1 Telegram Star\n"
        "3. Receive 100 Stars as a gift!\n\n"
        "Note: You need Telegram Stars to use this bot."
    )


async def pingme_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pingme command - Create Stars payment invoice."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    logger.info(f"User {user.id} ({user.first_name}) requested /pingme")
    
    # Create invoice for 1 Star payment
    title = "🌟 Stars Gift Activation"
    description = f"Pay {PAYMENT_AMOUNT} Star to receive {GIFT_AMOUNT} Stars gift!"
    payload = f"stars_gift_{user.id}"
    currency = "XTR"  # XTR is Telegram Stars currency
    prices = [LabeledPrice("Star Payment", PAYMENT_AMOUNT)]
    
    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Empty for Telegram Stars
            currency=currency,
            prices=prices,
            start_parameter="stars_gift",
        )
        logger.info(f"Invoice sent to user {user.id}")
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        await update.message.reply_text(
            "❌ Error creating payment. Please try again later."
        )


# ============================================
# PAYMENT HANDLERS
# ============================================

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pre-checkout query - Validate payment before processing."""
    query = update.pre_checkout_query
    
    if query.invoice_payload.startswith("stars_gift_"):
        await query.answer(ok=True)
        logger.info(f"Pre-checkout approved for user {query.from_user.id}")
    else:
        await query.answer(ok=False, error_message="Invalid payment request!")
        logger.warning(f"Pre-checkout rejected for user {query.from_user.id}")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful payment - Send stars gift to user."""
    user = update.effective_user
    payment = update.message.successful_payment
    
    logger.info(
        f"Successful payment from user {user.id}: "
        f"{payment.total_amount} {payment.currency}"
    )
    
    await update.message.reply_text(
        f"✅ Payment of {payment.total_amount} Star received!\n\n"
        f"🎁 Processing your {GIFT_AMOUNT} Stars gift..."
    )
    
    # Send the stars gift
    await send_stars_gift(context, user.id, update.effective_chat.id)


# ============================================
# GIFT SENDING FUNCTION
# ============================================

async def send_stars_gift(
    context: ContextTypes.DEFAULT_TYPE, 
    user_id: int, 
    chat_id: int
) -> None:
    """Send stars gift to a user using Telegram's gift system."""
    try:
        # Get available gifts from Telegram
        gifts = await context.bot.get_available_gifts()
        
        if gifts and gifts.gifts:
            selected_gift = None
            
            # Find a suitable gift
            for gift in gifts.gifts:
                if hasattr(gift, 'star_count') and gift.star_count <= GIFT_AMOUNT:
                    selected_gift = gift
                    break
            
            # Use first available if no exact match
            if not selected_gift and gifts.gifts:
                selected_gift = gifts.gifts[0]
            
            if selected_gift:
                # Send the gift to user
                await context.bot.send_gift(
                    user_id=user_id,
                    gift_id=selected_gift.id,
                    text="🎉 Congratulations! Here's your Stars gift!",
                )
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎁 Gift sent successfully!\n"
                         f"Gift ID: {selected_gift.id}\n"
                         f"Thank you for using our bot! 🌟"
                )
                logger.info(f"Gift {selected_gift.id} sent to user {user_id}")
                return
        
        # No gifts available
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ No gifts currently available. "
                 "Your payment has been recorded and gift will be sent soon!"
        )
        logger.warning(f"No gifts available to send to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error sending gift to user {user_id}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Gift delivery pending. Error: {str(e)}"
        )


# ============================================
# ADMIN FUNCTIONS
# ============================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all text messages - Check for admin '1' command."""
    user = update.effective_user
    message_text = update.message.text.strip()
    
    # Admin sends "1" -> bypass payment and send gift
    if user.id in ADMIN_IDS and message_text == "1":
        logger.info(f"Admin {user.id} triggered gift via '1' message")
        
        await update.message.reply_text(
            "🔐 Admin command received!\n"
            f"📤 Sending {GIFT_AMOUNT} Stars gift..."
        )
        
        await send_stars_gift(context, user.id, update.effective_chat.id)
        return
    
    # Regular users
    await update.message.reply_text(
        "ℹ️ Use /pingme to start the Stars payment process!\n"
        "Or /help for more information."
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel."""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized.")
        return
    
    await update.message.reply_text(
        "🔐 Admin Panel 🔐\n\n"
        "Commands:\n"
        "• Send '1' - Quick gift to yourself\n"
        "• /sendgift <user_id> - Send gift to user\n\n"
        f"Your Admin ID: {user.id}"
    )


async def sendgift_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to send gift to a specific user."""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /sendgift <user_id>\n"
            "Example: /sendgift 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        await update.message.reply_text(
            f"📤 Sending {GIFT_AMOUNT} Stars gift to user {target_user_id}..."
        )
        await send_stars_gift(context, target_user_id, update.effective_chat.id)
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


# ============================================
# ERROR HANDLER
# ============================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")


# ============================================
# MAIN FUNCTION
# ============================================

def main() -> None:
    """Start the bot."""
    print("🤖 Starting Telegram Stars Bot...")
    print(f"📋 Admin IDs: {ADMIN_IDS}")
    print(f"💰 Payment: {PAYMENT_AMOUNT} Star -> Gift: {GIFT_AMOUNT} Stars")
    print("-" * 50)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("pingme", pingme_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("sendgift", sendgift_command))
    
    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )
    
    # Text message handler (for admin "1" command)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
