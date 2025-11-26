import os
import re
import random
import string
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

# Bot token - replace with your actual bot token
BOT_TOKEN = "8222109440:AAEUDliYuyGgBcbXzJTuk6zJJKop32ZdM2o"

# File paths for persistence
ADMINS_FILE = "bot_admins.json"
DEALS_FILE = "confirmed_deals.json"
STATS_FILE = "bot_stats.json"

# Store bot admins (chat_id as key)
bot_admins = set()

# Store pending deals temporarily (group_chat_id -> list of deals)
pending_deals = {}

# Store confirmed deals with escrow admin info (trade_id -> deal info)
confirmed_deals = {}

# Store stats
stats = {
    'total_deals': 0,
    'total_volume': 0.0,
    'total_fees': 0.0,
    'confirmed_deals': 0,
    'completed_deals': 0,
    'total_released': 0.0
}

def load_data():
    """Load all data from JSON files"""
    global bot_admins, confirmed_deals, stats
    
    # Load admins
    try:
        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, 'r') as f:
                bot_admins = set(json.load(f))
    except Exception as e:
        print(f"Error loading admins: {e}")
    
    # Load confirmed deals
    try:
        if os.path.exists(DEALS_FILE):
            with open(DEALS_FILE, 'r') as f:
                confirmed_deals = json.load(f)
    except Exception as e:
        print(f"Error loading deals: {e}")
    
    # Load stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
    except Exception as e:
        print(f"Error loading stats: {e}")

def save_admins():
    """Save admins to JSON file"""
    try:
        with open(ADMINS_FILE, 'w') as f:
            json.dump(list(bot_admins), f, indent=2)
    except Exception as e:
        print(f"Error saving admins: {e}")

def save_deals():
    """Save confirmed deals to JSON file"""
    try:
        with open(DEALS_FILE, 'w') as f:
            json.dump(confirmed_deals, f, indent=2)
    except Exception as e:
        print(f"Error saving deals: {e}")

def save_stats():
    """Save stats to JSON file"""
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"Error saving stats: {e}")

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
    except Exception as e:
        print(f"Error parsing deal form: {e}")
        return None

def extract_amount_number(amount_str):
    """Extract numeric value from amount string"""
    match = re.search(r'[\d.]+', amount_str)
    return float(match.group()) if match else 0

def is_bot_admin(user_id):
    """Check if user is a bot admin"""
    return user_id in bot_admins

async def delete_user_command(update: Update):
    """Delete only user's command message, not bot messages"""
    try:
        if not update.message.from_user.is_bot:
            await update.message.delete()
    except BadRequest as e:
        print(f"Could not delete message: {e}")
    except Exception as e:
        print(f"Error deleting message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await delete_user_command(update)
    
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
/done - Complete a deal (reply to confirmed deal)
/stats - View bot statistics

🔧 **Utility:**
/myid - Get your chat ID

💡 **Note:** All user commands are deleted automatically for privacy!
    """
    await update.message.reply_text(welcome_message)

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a bot admin - /addadmin chat_id"""
    await delete_user_command(update)
    
    user_id = update.message.from_user.id
    
    # First admin can be added by anyone, after that only admins can add
    if bot_admins and not is_bot_admin(user_id):
        await update.message.reply_text("❌ Only bot admins can add new admins!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Please specify a chat_id: /addadmin 123456789")
        return
    
    try:
        new_admin_id = int(context.args[0])
        bot_admins.add(new_admin_id)
        save_admins()
        await update.message.reply_text(f"✅ User {new_admin_id} has been added as bot admin!")
    except ValueError:
        await update.message.reply_text("❌ Invalid chat_id. Please use a numeric ID.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error adding admin: {str(e)}")

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a bot admin - /removeadmin chat_id"""
    await delete_user_command(update)
    
    user_id = update.message.from_user.id
    
    if not is_bot_admin(user_id):
        await update.message.reply_text("❌ Only bot admins can remove admins!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Please specify a chat_id: /removeadmin 123456789")
        return
    
    try:
        admin_id = int(context.args[0])
        if admin_id in bot_admins:
            bot_admins.remove(admin_id)
            save_admins()
            await update.message.reply_text(f"✅ User {admin_id} has been removed from bot admins!")
        else:
            await update.message.reply_text("❌ This user is not a bot admin.")
    except ValueError:
        await update.message.reply_text("❌ Invalid chat_id. Please use a numeric ID.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error removing admin: {str(e)}")

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all bot admins"""
    await delete_user_command(update)
    
    if not bot_admins:
        await update.message.reply_text("📋 No bot admins configured yet.")
        return
    
    admin_list = "\n".join([f"• {admin_id}" for admin_id in bot_admins])
    await update.message.reply_text(f"👮 **Bot Admins:**\n\n{admin_list}", parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    await delete_user_command(update)
    
    stats_message = f"""
📊 **Bot Statistics**

✅ Total Deals Submitted: {stats['total_deals']}
🔒 Confirmed Deals: {stats['confirmed_deals']}
✅ Completed Deals: {stats['completed_deals']}
💰 Total Volume: ${stats['total_volume']:.2f}
💵 Total Fees Collected: ${stats['total_fees']:.2f}
📤 Total Released: ${stats['total_released']:.2f}

⏳ Pending Deals: {sum(len(deals) for deals in pending_deals.values())}
🔄 Active Deals: {len(confirmed_deals)}
👮 Active Admins: {len(bot_admins)}
    """
    
    await update.message.reply_text(stats_message, parse_mode='Markdown')

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's chat ID"""
    await delete_user_command(update)
    
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "No username"
    await update.message.reply_text(
        f"👤 Your Chat ID: `{user_id}`\n👤 Username: @{username}", 
        parse_mode='Markdown'
    )

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
            save_stats()

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command from admin"""
    await delete_user_command(update)
    
    user_id = update.message.from_user.id
    
    # Check if user is bot admin
    if not is_bot_admin(user_id):
        await update.message.reply_text("❌ Only bot admins can confirm deals!")
        return
    
    message_text = update.message.text
    
    # Extract username from command
    username_match = re.search(r'@(\w+)', message_text)
    
    if not username_match:
        await update.message.reply_text("❌ Please specify a username: /add @username")
        return
    
    escrow_admin = username_match.group(0)
    
    # Check if replying to a message
    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text
        deal_info = parse_deal_form(replied_text)
        
        if deal_info:
            trade_id = generate_trade_id()
            amount = extract_amount_number(deal_info['amount'])
            received_amount = amount
            fee = received_amount * 0.01  # 1% of received amount
            release_amount = received_amount - fee  # Release amount after deducting 1% fee
            
            # Update stats
            stats['confirmed_deals'] += 1
            stats['total_volume'] += amount
            stats['total_fees'] += fee
            save_stats()
            
            # Store confirmed deal info
            confirmed_deals[trade_id] = {
                'buyer': deal_info['buyer'],
                'seller': deal_info['seller'],
                'amount': amount,
                'release_amount': release_amount,
                'escrow_admin': escrow_admin,
                'trade_id': trade_id
            }
            save_deals()
            
            confirmation_message = f"""
✅ **DEAL CONFIRMED**

💰 Deal Amount: {amount:.2f}$
📥 Received Amount: {received_amount:.2f}$
📤 Release/Refund Amount: {release_amount:.2f}$
🆔 Trade ID: {trade_id}

**Continue the Deal**
Buyer: {deal_info['buyer']}
Seller: {deal_info['seller']}

🛡 Escrowed By: {escrow_admin}
            """
            
            await update.message.reply_to_message.reply_text(confirmation_message, parse_mode='Markdown')
            
            # Remove from pending deals if exists
            chat_id = update.message.chat_id
            if chat_id in pending_deals:
                pending_deals[chat_id] = [d for d in pending_deals[chat_id] 
                                         if d['message_id'] != update.message.reply_to_message.message_id]
        else:
            await update.message.reply_text("❌ Could not find valid deal information in the replied message.")
    else:
        # Check for pending deals in this chat
        chat_id = update.message.chat_id
        if chat_id in pending_deals and pending_deals[chat_id]:
            deal = pending_deals[chat_id][-1]
            
            amount = extract_amount_number(deal['amount'])
            received_amount = amount
            fee = received_amount * 0.01  # 1% of received amount
            release_amount = received_amount - fee  # Release amount after deducting 1% fee
            
            # Update stats
            stats['confirmed_deals'] += 1
            stats['total_volume'] += amount
            stats['total_fees'] += fee
            save_stats()
            
            # Store confirmed deal info
            confirmed_deals[deal['trade_id']] = {
                'buyer': deal['buyer'],
                'seller': deal['seller'],
                'amount': amount,
                'release_amount': release_amount,
                'escrow_admin': escrow_admin,
                'trade_id': deal['trade_id']
            }
            save_deals()
            
            confirmation_message = f"""
✅ **DEAL CONFIRMED**

💰 Deal Amount: {amount:.2f}$
📥 Received Amount: {received_amount:.2f}$
📤 Release/Refund Amount: {release_amount:.2f}$
🆔 Trade ID: {deal['trade_id']}

**Continue the Deal**
Buyer: {deal['buyer']}
Seller: {deal['seller']}

🛡 Escrowed By: {escrow_admin}
            """
            
            await update.message.reply_text(confirmation_message, parse_mode='Markdown')
            
            # Remove the processed deal
            pending_deals[chat_id].pop()
        else:
            await update.message.reply_text("❌ No pending deals found in this chat. Please reply to a deal message.")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /done command from admin to complete deals"""
    await delete_user_command(update)
    
    user_id = update.message.from_user.id
    
    # Check if user is bot admin
    if not is_bot_admin(user_id):
        await update.message.reply_text("❌ Only bot admins can complete deals!")
        return
    
    # Check if replying to a message
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to a confirmed deal message with /done")
        return
    
    try:
        replied_text = update.message.reply_to_message.text
        
        # Debug: Print the replied text
        print(f"Replied text: {replied_text}")
        
        # Try multiple patterns to extract Trade ID
        trade_id_match = re.search(r'Trade ID:\s*(#TID[A-Z0-9]+)', replied_text, re.IGNORECASE)
        if not trade_id_match:
            trade_id_match = re.search(r'(#TID[A-Z0-9]+)', replied_text, re.IGNORECASE)
        
        if not trade_id_match:
            await update.message.reply_text(
                "❌ Could not find Trade ID in the replied message.\n"
                "Please make sure you're replying to a confirmed deal message.\n"
                f"Debug: Found {len(confirmed_deals)} active deals."
            )
            return
        
        trade_id = trade_id_match.group(1).upper()
        print(f"Found Trade ID: {trade_id}")
        print(f"Active deals: {list(confirmed_deals.keys())}")
        
        # Check if this trade exists in confirmed deals
        if trade_id not in confirmed_deals:
            await update.message.reply_text(
                f"❌ Trade {trade_id} not found or already completed.\n"
                f"Active deals: {len(confirmed_deals)}"
            )
            return
        
        deal = confirmed_deals[trade_id]
        
        # Update stats
        stats['completed_deals'] += 1
        stats['total_released'] += deal['release_amount']
        save_stats()
        
        completion_message = f"""
✅ **Deal Completed**
🆔 Trade ID: {trade_id}
📤 Released: ${deal['release_amount']:.2f}
ℹ️ Total Released: ${stats['total_released']:.2f}

Buyer: {deal['buyer']}
Seller: {deal['seller']}

🛡️ Escrowed By: {deal['escrow_admin']}
        """
        
        print(f"DEBUG - Deal release: ${deal['release_amount']:.2f}, Total released: ${stats['total_released']:.2f}")
        
        await update.message.reply_to_message.reply_text(completion_message, parse_mode='Markdown')
        
        # Remove from confirmed deals
        del confirmed_deals[trade_id]
        save_deals()
        
    except Exception as e:
        error_msg = f"❌ Error completing deal: {str(e)}"
        print(error_msg)
        await update.message.reply_text(error_msg)

def main():
    """Start the bot."""
    # Load data from JSON files
    load_data()
    
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
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deal_form))

    # Run the bot
    print("Bot is running...")
    print("⚠️ Make sure bot has 'Delete Messages' permission in your group!")
    print(f"📊 Loaded {len(bot_admins)} admins, {len(confirmed_deals)} active deals")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
