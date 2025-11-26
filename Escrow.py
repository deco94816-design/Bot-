import os
import re
import random
import string
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

# Bot token - replace with your actual bot token
BOT_TOKEN = "8222109440:AAEUDliYuyGgBcbXzJTuk6zJJKop32ZdM2o"

# Store bot admins (chat_id as key)
bot_admins = set()

# Store pending deals temporarily (group_chat_id -> list of deals)
pending_deals = {}

# Store stats
stats = {
    'total_deals': 0,
    'total_volume': 0.0,
    'total_fees': 0.0,
    'confirmed_deals': 0
}

def generate_trade_id():
    """Generate a random trade ID like #TID1FGK6"""
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"#TID{random_part}"

def parse_deal_form(text):
    """Parse the deal form from user message"""
    try:
        lines = text.strip().split('\n')
        deal_info = {}
        
        for line in lines:
            if 'BUYER' in line.upper():
                deal_info['buyer'] = line.split(':', 1)[1].strip()
            elif 'SELLER' in line.upper():
                deal_info['seller'] = line.split(':', 1)[1].strip()
            elif 'DEAL AMOUNT' in line.upper():
                deal_info['amount'] = line.split(':', 1)[1].strip()
            elif 'TIME TO COMPLETE' in line.upper():
                deal_info['time'] = line.split(':', 1)[1].strip()
        
        return deal_info if len(deal_info) >= 3 else None
    except:
        return None

def extract_amount_number(amount_str):
    """Extract numeric value from amount string"""
    match = re.search(r'[\d.]+', amount_str)
    return float(match.group()) if match else 0

def is_bot_admin(user_id):
    """Check if user is a bot admin"""
    return user_id in bot_admins

async def delete_message(update: Update):
    """Delete the command message"""
    try:
        await update.message.delete()
    except BadRequest:
        pass  # Ignore if bot doesn't have permission to delete

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await delete_message(update)
    
    welcome_message = """
🤖 Welcome to Escrow Confirmation Bot!

📝 **For Users** - To create a deal, send a message with this format:

DEAL INFO:
BUYER: username
SELLER: username
DEAL AMOUNT: 100$
TIME TO COMPLETE DEAL: 24 hours

👮 **For Admins:**
/addadmin chat_id - Add a bot admin
/removeadmin chat_id - Remove a bot admin
/listadmins - List all bot admins
/add @username - Confirm deal and set escrow admin
/stats - View bot statistics

🔧 **Utility:**
/myid - Get your chat ID

💡 **Note:** All commands are deleted automatically for privacy!
    """
    sent_msg = await update.message.reply_text(welcome_message)
    
    # Delete the welcome message after 30 seconds in groups
    if update.message.chat.type != 'private':
        context.job_queue.run_once(
            lambda ctx: sent_msg.delete(),
            30
        )

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a bot admin - /addadmin chat_id"""
    await delete_message(update)
    
    user_id = update.message.from_user.id
    
    # First admin can be added by anyone, after that only admins can add
    if bot_admins and not is_bot_admin(user_id):
        msg = await update.message.reply_text("❌ Only bot admins can add new admins!")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)
        return
    
    if not context.args:
        msg = await update.message.reply_text("❌ Please specify a chat_id: /addadmin 123456789")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)
        return
    
    try:
        new_admin_id = int(context.args[0])
        bot_admins.add(new_admin_id)
        msg = await update.message.reply_text(f"✅ User {new_admin_id} has been added as bot admin!")
        context.job_queue.run_once(lambda ctx: msg.delete(), 10)
    except ValueError:
        msg = await update.message.reply_text("❌ Invalid chat_id. Please use a numeric ID.")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a bot admin - /removeadmin chat_id"""
    await delete_message(update)
    
    user_id = update.message.from_user.id
    
    if not is_bot_admin(user_id):
        msg = await update.message.reply_text("❌ Only bot admins can remove admins!")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)
        return
    
    if not context.args:
        msg = await update.message.reply_text("❌ Please specify a chat_id: /removeadmin 123456789")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)
        return
    
    try:
        admin_id = int(context.args[0])
        if admin_id in bot_admins:
            bot_admins.remove(admin_id)
            msg = await update.message.reply_text(f"✅ User {admin_id} has been removed from bot admins!")
            context.job_queue.run_once(lambda ctx: msg.delete(), 10)
        else:
            msg = await update.message.reply_text("❌ This user is not a bot admin.")
            context.job_queue.run_once(lambda ctx: msg.delete(), 5)
    except ValueError:
        msg = await update.message.reply_text("❌ Invalid chat_id. Please use a numeric ID.")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all bot admins"""
    await delete_message(update)
    
    if not bot_admins:
        msg = await update.message.reply_text("📋 No bot admins configured yet.")
        context.job_queue.run_once(lambda ctx: msg.delete(), 10)
        return
    
    admin_list = "\n".join([f"• {admin_id}" for admin_id in bot_admins])
    msg = await update.message.reply_text(f"👮 **Bot Admins:**\n\n{admin_list}", parse_mode='Markdown')
    context.job_queue.run_once(lambda ctx: msg.delete(), 15)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    await delete_message(update)
    
    stats_message = f"""
📊 **Bot Statistics**

✅ Total Deals Submitted: {stats['total_deals']}
🔒 Confirmed Deals: {stats['confirmed_deals']}
💰 Total Volume: ${stats['total_volume']:.2f}
💵 Total Fees Collected: ${stats['total_fees']:.2f}

⏳ Pending Deals: {sum(len(deals) for deals in pending_deals.values())}
👮 Active Admins: {len(bot_admins)}
    """
    
    msg = await update.message.reply_text(stats_message, parse_mode='Markdown')
    
    # Delete stats after 20 seconds in groups
    if update.message.chat.type != 'private':
        context.job_queue.run_once(lambda ctx: msg.delete(), 20)

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's chat ID"""
    await delete_message(update)
    
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "No username"
    msg = await update.message.reply_text(
        f"👤 Your Chat ID: `{user_id}`\n👤 Username: @{username}", 
        parse_mode='Markdown'
    )
    
    # Delete after 15 seconds in groups
    if update.message.chat.type != 'private':
        context.job_queue.run_once(lambda ctx: msg.delete(), 15)

async def handle_deal_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming deal forms"""
    message_text = update.message.text
    
    # Check if message contains deal info
    if 'DEAL INFO' in message_text.upper() or 'BUYER' in message_text.upper():
        deal_info = parse_deal_form(message_text)
        
        if deal_info:
            # Store the pending deal
            chat_id = update.message.chat_id
            trade_id = generate_trade_id()
            
            if chat_id not in pending_deals:
                pending_deals[chat_id] = []
            
            pending_deals[chat_id].append({
                'trade_id': trade_id,
                'buyer': deal_info['buyer'],
                'seller': deal_info['seller'],
                'amount': deal_info['amount'],
                'time': deal_info.get('time', 'Not specified'),
                'message_id': update.message.message_id,
                'user_id': update.message.from_user.id,
                'username': update.message.from_user.username or "Unknown"
            })
            
            # Update stats
            stats['total_deals'] += 1
            
            response = f"""
✅ Deal form received!

📋 Deal Details:
• Buyer: {deal_info['buyer']}
• Seller: {deal_info['seller']}
• Amount: {deal_info['amount']}
• Time: {deal_info.get('time', 'Not specified')}
• Trade ID: {trade_id}

⏳ Waiting for admin confirmation...
            """
            await update.message.reply_text(response)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command from admin"""
    # Delete the command message immediately
    await delete_message(update)
    
    user_id = update.message.from_user.id
    
    # Check if user is bot admin
    if not is_bot_admin(user_id):
        msg = await update.message.reply_text("❌ Only bot admins can confirm deals!")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)
        return
    
    message_text = update.message.text
    
    # Extract username from command
    username_match = re.search(r'@(\w+)', message_text)
    
    if not username_match:
        msg = await update.message.reply_text("❌ Please specify a username: /add @username")
        context.job_queue.run_once(lambda ctx: msg.delete(), 5)
        return
    
    escrow_admin = username_match.group(0)
    
    # Check if replying to a message
    if update.message.reply_to_message:
        # Try to find the deal from the replied message
        replied_text = update.message.reply_to_message.text
        deal_info = parse_deal_form(replied_text)
        
        if deal_info:
            trade_id = generate_trade_id()
            amount = extract_amount_number(deal_info['amount'])
            fee = amount * 0.01  # 1% fee
            release_amount = amount - fee
            
            # Update stats
            stats['confirmed_deals'] += 1
            stats['total_volume'] += amount
            stats['total_fees'] += fee
            
            confirmation_message = f"""
✅ **DEAL CONFIRMED**

💰 Deal Amount: {amount:.2f}$
📥 Received Amount: {amount:.2f}$
📤 Release/Refund Amount: {release_amount:.2f}$
🆔 Trade ID: {trade_id}

**Continue the Deal**
Buyer: {deal_info['buyer']}
Seller: {deal_info['seller']}

🛡 Escrowed By: {escrow_admin}

💵 Fee (1%): {fee:.2f}$
            """
            
            await update.message.reply_to_message.reply_text(confirmation_message, parse_mode='Markdown')
            
            # Remove from pending deals if exists
            chat_id = update.message.chat_id
            if chat_id in pending_deals:
                pending_deals[chat_id] = [d for d in pending_deals[chat_id] 
                                         if d['message_id'] != update.message.reply_to_message.message_id]
        else:
            msg = await update.message.reply_text("❌ Could not find valid deal information in the replied message.")
            context.job_queue.run_once(lambda ctx: msg.delete(), 5)
    else:
        # Check for pending deals in this chat
        chat_id = update.message.chat_id
        if chat_id in pending_deals and pending_deals[chat_id]:
            # Get the most recent pending deal
            deal = pending_deals[chat_id][-1]
            
            amount = extract_amount_number(deal['amount'])
            fee = amount * 0.01  # 1% fee
            release_amount = amount - fee
            
            # Update stats
            stats['confirmed_deals'] += 1
            stats['total_volume'] += amount
            stats['total_fees'] += fee
            
            confirmation_message = f"""
✅ **DEAL CONFIRMED**

💰 Deal Amount: {amount:.2f}$
📥 Received Amount: {amount:.2f}$
📤 Release/Refund Amount: {release_amount:.2f}$
🆔 Trade ID: {deal['trade_id']}

**Continue the Deal**
Buyer: {deal['buyer']}
Seller: {deal['seller']}

🛡 Escrowed By: {escrow_admin}

💵 Fee (1%): {fee:.2f}$
            """
            
            await update.message.reply_text(confirmation_message, parse_mode='Markdown')
            
            # Remove the processed deal
            pending_deals[chat_id].pop()
        else:
            msg = await update.message.reply_text("❌ No pending deals found in this chat. Please reply to a deal message.")
            context.job_queue.run_once(lambda ctx: msg.delete(), 5)

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("listadmins", list_admins_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("myid", get_my_id))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deal_form))

    # Run the bot
    print("Bot is running...")
    print("⚠️ Make sure bot has 'Delete Messages' permission in your group!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
