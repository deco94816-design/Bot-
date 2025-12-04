"""
Telegram Bot: Auto-Approve Join Requests
This bot automatically approves all join requests to a group and sends a private message to users.
"""

from telegram import Update
from telegram.ext import Application, ChatJoinRequestHandler, ContextTypes
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "8549254097:AAGfXYv0UF9H0I5ObdTjefnf-SciCa-Tu7Q"


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming join requests.
    Automatically approve the request and send a private message to the user.
    """
    try:
        chat_join_request = update.chat_join_request
        user = chat_join_request.from_user
        chat = chat_join_request.chat
        
        logger.info(f"Join request from {user.first_name} (ID: {user.id}) for chat {chat.title}")
        
        # Approve the join request
        await chat_join_request.approve()
        logger.info(f"Approved join request for {user.first_name}")
        
        # Send a private message to the user
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="✅ Your join request has been approved!\n\nPlease wait patiently. Welcome to the group! 🎉"
            )
            logger.info(f"Sent welcome message to {user.first_name}")
        except Exception as e:
            logger.warning(f"Could not send private message to {user.first_name}: {e}")
            # This might happen if the user hasn't started a chat with the bot
            
    except Exception as e:
        logger.error(f"Error handling join request: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register the join request handler
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Bot started successfully! Waiting for join requests...")
    application.run_polling(allowed_updates=["chat_join_request"])


if __name__ == "__main__":
    main()
