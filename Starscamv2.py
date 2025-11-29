import logging
from telegram import Update, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TOPIC, SUBTOPIC, AMOUNT = range(3)

# User data keys
class UserData:
    TOPIC = 'topic'
    SUBTOPIC = 'subtopic'
    AMOUNT = 'amount'


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and ask for the main topic."""
    await update.message.reply_text(
        "👋 Welcome to the Payment Bot!\n\n"
        "Please enter the main topic for your payment:"
    )
    return TOPIC


async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the topic and ask for subtopic."""
    context.user_data[UserData.TOPIC] = update.message.text
    
    await update.message.reply_text(
        f"✅ Topic: {update.message.text}\n\n"
        "Now, please enter the subtopic:"
    )
    return SUBTOPIC


async def receive_subtopic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the subtopic and ask for amount."""
    context.user_data[UserData.SUBTOPIC] = update.message.text
    
    await update.message.reply_text(
        f"✅ Subtopic: {update.message.text}\n\n"
        "Please enter the amount in Telegram Stars (integer only):"
    )
    return AMOUNT


async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the amount and send payment invoice."""
    try:
        amount = int(update.message.text)
        
        if amount <= 0:
            await update.message.reply_text(
                "❌ Please enter a positive number for the amount."
            )
            return AMOUNT
        
        context.user_data[UserData.AMOUNT] = amount
        
        # Get stored data
        topic = context.user_data[UserData.TOPIC]
        subtopic = context.user_data[UserData.SUBTOPIC]
        
        # Create payment description
        title = topic
        description = f"Payment for {topic} under {subtopic} category"
        payload = f"payment_{update.effective_user.id}_{topic}_{subtopic}"
        
        # Send invoice
        # Note: For Telegram Stars, currency should be "XTR"
        await update.message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Empty for Telegram Stars
            currency="XTR",  # XTR is the currency code for Telegram Stars
            prices=[LabeledPrice(label=topic, amount=amount)]
        )
        
        await update.message.reply_text(
            "💫 Payment invoice sent! Please complete the payment."
        )
        
        # Clear user data
        context.user_data.clear()
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input! Please enter a valid integer for the amount."
        )
        return AMOUNT


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer the PreCheckoutQuery"""
    query = update.pre_checkout_query
    
    # Always approve for this example
    # In production, you might want to verify the payload or check inventory
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm the successful payment"""
    payment = update.message.successful_payment
    
    await update.message.reply_text(
        "✅ Payment Successful!\n\n"
        f"💫 Amount: {payment.total_amount} Stars\n"
        f"📝 Transaction ID: {payment.telegram_payment_charge_id}\n\n"
        "Thank you for your payment! 🎉\n\n"
        "Send /start to make another payment."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel and end the conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Payment process cancelled. Send /start to begin again."
    )
    return ConversationHandler.END


def main():
    """Start the bot."""
    # Bot token
    TOKEN = "8409890141:AAFiNOpHvmlaewds705PN2weMTSAbWQmiV0"
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topic)],
            SUBTOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_subtopic)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )
    
    # Start the bot
    print("🤖 Bot is running...")
    print("Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
