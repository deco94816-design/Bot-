 import logging
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8251256866:AAFMgG9Csq-7avh7IaTJeK61G3CN3c21v1Y"
WITHDRAWAL_FEE_STARS = 25

# Store pending withdrawals (in production, use a database)
pending_withdrawals = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Welcome! Use /withdraw to initiate an NFT withdrawal."
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /withdraw command."""
    user_id = update.effective_user.id
    
    # Send withdrawal notice
    notice_text = (
        "⚠️ *Withdrawal Notice*\n\n"
        f"To complete your NFT withdrawal, a {WITHDRAWAL_FEE_STARS}-star withdrawal fee is required.\n"
        "Please make the payment, and your NFT will be transferred instantly."
    )
    
    # Create payment button
    keyboard = [
        [InlineKeyboardButton(
            f"💳 Pay {WITHDRAWAL_FEE_STARS} Stars", 
            callback_data=f"pay_withdraw_{user_id}"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        notice_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("pay_withdraw_"):
        user_id = int(query.data.split("_")[-1])
        
        # Store withdrawal request
        pending_withdrawals[user_id] = {
            'status': 'pending',
            'message_id': query.message.message_id
        }
        
        # Create invoice for Telegram Stars
        title = "NFT Withdrawal Fee"
        description = "Payment required to process your NFT withdrawal"
        payload = f"withdraw_{user_id}"
        currency = "XTR"  # Telegram Stars currency code
        
        prices = [LabeledPrice("Withdrawal Fee", WITHDRAWAL_FEE_STARS)]
        
        # Send invoice
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Empty for Telegram Stars
            currency=currency,
            prices=prices,
            start_parameter=f"withdraw_{user_id}"
        )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout query."""
    query = update.pre_checkout_query
    
    # Always approve (you can add validation here)
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment."""
    user_id = update.effective_user.id
    payment_info = update.message.successful_payment
    
    # Verify payment
    if payment_info.total_amount == WITHDRAWAL_FEE_STARS:
        # Process withdrawal
        if user_id in pending_withdrawals:
            pending_withdrawals[user_id]['status'] = 'completed'
        
        # Send confirmation
        confirmation_text = (
            "✅ *Payment Successful!*\n\n"
            f"Your {WITHDRAWAL_FEE_STARS} Stars payment has been received.\n"
            "Your NFT withdrawal is being processed and will be transferred shortly.\n\n"
            f"Transaction ID: `{payment_info.telegram_payment_charge_id}`"
        )
        
        await update.message.reply_text(
            confirmation_text,
            parse_mode='Markdown'
        )
        
        # Here you would implement the actual NFT transfer logic
        await process_nft_withdrawal(user_id, context)
    else:
        await update.message.reply_text(
            "⚠️ Payment amount mismatch. Please contact support."
        )

async def process_nft_withdrawal(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Process the actual NFT withdrawal (implement your logic here)."""
    # This is where you'd implement your NFT transfer logic
    # For now, just send a completion message
    await context.bot.send_message(
        chat_id=user_id,
        text="🎉 *NFT Withdrawal Complete!*\n\nYour NFT has been successfully transferred to your wallet.",
        parse_mode='Markdown'
    )
    
    # Clean up pending withdrawal
    if user_id in pending_withdrawals:
        del pending_withdrawals[user_id]

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(MessageHandler(filters.StatusUpdate.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    
    # Add callback query handler for buttons
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Run the bot
    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
