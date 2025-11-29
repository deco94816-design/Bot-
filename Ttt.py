from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError, 
    PhoneNumberInvalidError,
    FloodWaitError,
    ChatWriteForbiddenError,
    UserBannedInChannelError
)
import asyncio
import json
import os
from datetime import datetime

# Admin Configuration
ADMIN_ID = 5709159932

# Catch words for auto-reply
CATCH_WORDS = ['dm me', 'pm me', 'inbox me', 'message me', 'dm', 'pm', 'inbox', 'private message']

# Auto-reply message
AUTO_REPLY_MESSAGE = "⚠️ I'm limited! Please add me to contact or tag me: @{username}"

# Configuration file
CONFIG_FILE = 'userbots_config.json'

def load_config():
    """Load userbot configuration from JSON file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Config file is corrupted. Creating new one.")
            return {'userbots': []}
    return {'userbots': []}

def save_config(config):
    """Save userbot configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"❌ Error saving config: {str(e)}")
        return False

def log_message(phone, message):
    """Log messages with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{phone}] {message}")

def check_catch_words(text):
    """Check if message contains any catch words"""
    if not text:
        return False
    text_lower = text.lower()
    return any(word in text_lower for word in CATCH_WORDS)

async def get_all_groups(client):
    """Get all groups the userbot is part of with error handling"""
    groups = []
    try:
        result = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=200,
            hash=0
        ))
        
        for chat in result.chats:
            try:
                if hasattr(chat, 'megagroup') and not getattr(chat, 'broadcast', False):
                    groups.append(chat)
            except Exception as e:
                log_message(getattr(client, 'phone', 'Unknown'), f"Error processing chat: {str(e)}")
                continue
    
    except Exception as e:
        log_message(getattr(client, 'phone', 'Unknown'), f"Error fetching groups: {str(e)}")
    
    return groups

async def send_to_all_groups(client, message, interval, task_id):
    """Send message to all groups with specified interval and error handling"""
    while True:
        try:
            groups = await get_all_groups(client)
            
            if not groups:
                log_message(client.phone, "⚠️ No groups found to broadcast!")
                await asyncio.sleep(interval * 60)
                continue
            
            success_count = 0
            error_count = 0
            
            for group in groups:
                try:
                    sent_msg = await client.send_message(group.id, message)
                    
                    # Store message ID for tracking replies
                    if not hasattr(client, 'sent_messages'):
                        client.sent_messages = {}
                    client.sent_messages[sent_msg.id] = {
                        'chat_id': group.id,
                        'message': message
                    }
                    
                    success_count += 1
                    log_message(client.phone, f"✓ Sent to: {group.title}")
                    
                    # Small delay between groups to avoid flood
                    await asyncio.sleep(2)
                    
                except FloodWaitError as e:
                    log_message(client.phone, f"⏳ Flood wait for {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                    
                except ChatWriteForbiddenError:
                    log_message(client.phone, f"✗ No permission in: {group.title}")
                    error_count += 1
                    
                except UserBannedInChannelError:
                    log_message(client.phone, f"✗ Banned in: {group.title}")
                    error_count += 1
                    
                except Exception as e:
                    log_message(client.phone, f"✗ Error in {group.title}: {str(e)}")
                    error_count += 1
            
            log_message(client.phone, f"📊 Broadcast complete - Success: {success_count}, Errors: {error_count}")
            log_message(client.phone, f"⏳ Waiting {interval} minutes before next broadcast...")
            
            await asyncio.sleep(interval * 60)
            
        except Exception as e:
            log_message(client.phone, f"❌ Critical error in broadcast loop: {str(e)}")
            await asyncio.sleep(60)

async def start_userbot(bot_info, active_tasks):
    """Initialize and start a single userbot with error handling"""
    session_name = f"sessions/userbot_{bot_info['phone'].replace('+', '').replace(' ', '')}"
    
    # Create sessions directory if not exists
    os.makedirs('sessions', exist_ok=True)
    
    try:
        client = TelegramClient(
            session_name,
            bot_info['api_id'],
            bot_info['api_hash']
        )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            try:
                await client.start(phone=bot_info['phone'])
            except SessionPasswordNeededError:
                print(f"\n⚠️ 2FA enabled for {bot_info['phone']}")
                password = input("Enter your 2FA password: ")
                await client.start(phone=bot_info['phone'], password=password)
            except PhoneCodeInvalidError:
                print(f"❌ Invalid verification code for {bot_info['phone']}")
                return None
            except PhoneNumberInvalidError:
                print(f"❌ Invalid phone number: {bot_info['phone']}")
                return None
        
        me = await client.get_me()
        client.phone = bot_info['phone']
        client.username = me.username or me.first_name
        client.sent_messages = {}
        client.waiting_for_interval = False
        client.broadcast_message = None
        
        log_message(client.phone, f"✓ Started: {me.first_name} (@{me.username or 'no_username'})")
        
        # Handle replies to userbot messages (auto-reply functionality)
        @client.on(events.NewMessage(incoming=True))
        async def reply_handler(event):
            """Handle replies to userbot messages with catch words"""
            try:
                # Skip if message is from admin or from self
                if event.sender_id == ADMIN_ID or event.sender_id == me.id:
                    return
                
                # Check if this is a reply
                if event.is_reply:
                    replied_msg = await event.get_reply_message()
                    
                    # Check if reply is to our userbot message
                    if replied_msg and replied_msg.sender_id == me.id:
                        message_text = event.message.text
                        
                        # Check for catch words
                        if check_catch_words(message_text):
                            try:
                                # Get sender info
                                sender = await event.get_sender()
                                sender_mention = f"[{sender.first_name}](tg://user?id={sender.id})"
                                
                                # Send auto-reply
                                auto_reply = AUTO_REPLY_MESSAGE.format(username=client.username)
                                auto_reply += f"\n\n👤 Replying to: {sender_mention}"
                                
                                await event.reply(auto_reply)
                                log_message(client.phone, f"🤖 Auto-replied to {sender.first_name} in {event.chat.title if hasattr(event.chat, 'title') else 'Unknown'}")
                                
                            except Exception as e:
                                log_message(client.phone, f"❌ Error sending auto-reply: {str(e)}")
                
            except Exception as e:
                log_message(client.phone, f"❌ Error in reply handler: {str(e)}")
        
        @client.on(events.NewMessage(from_users=ADMIN_ID, pattern='/start'))
        async def start_handler(event):
            """Handle /start command from admin"""
            try:
                groups = await get_all_groups(client)
                await event.respond(
                    f"🤖 **Userbot Active**\n\n"
                    f"📱 Phone: `{client.phone}`\n"
                    f"👤 Name: {me.first_name}\n"
                    f"🆔 Username: @{client.username}\n"
                    f"🎯 Groups: {len(groups)}\n\n"
                    f"📝 Send me any message to broadcast!\n"
                    f"📋 Use /help for commands"
                )
            except Exception as e:
                log_message(client.phone, f"❌ Error in start handler: {str(e)}")
        
        @client.on(events.NewMessage(from_users=ADMIN_ID, pattern='/help'))
        async def help_handler(event):
            """Show help message"""
            try:
                await event.respond(
                    f"📚 **Userbot Commands**\n\n"
                    f"🔹 `/start` - Show userbot info\n"
                    f"🔹 `/status` - View current status\n"
                    f"🔹 `/stop` - Stop all broadcasts\n"
                    f"🔹 `/groups` - List all groups\n"
                    f"🔹 `/help` - Show this message\n\n"
                    f"💬 **Broadcasting:**\n"
                    f"1️⃣ Send your message\n"
                    f"2️⃣ Send interval: 1, 2, 3, 5, or 10\n\n"
                    f"🤖 **Auto-Reply:**\n"
                    f"Catch words: {', '.join(CATCH_WORDS[:5])}"
                )
            except Exception as e:
                log_message(client.phone, f"❌ Error in help handler: {str(e)}")
        
        @client.on(events.NewMessage(from_users=ADMIN_ID))
        async def message_handler(event):
            """Handle messages from admin"""
            try:
                msg_text = event.message.text
                
                if not msg_text:
                    return
                
                # Ignore commands
                if msg_text.startswith('/'):
                    return
                
                # Check if waiting for interval
                if client.waiting_for_interval:
                    # Try to parse interval
                    try:
                        interval = int(msg_text.strip())
                        
                        if interval not in [1, 2, 3, 5, 10]:
                            await event.respond(
                                f"❌ Invalid interval!\n\n"
                                f"Please send: **1**, **2**, **3**, **5**, or **10**"
                            )
                            return
                        
                        # Show confirmation
                        groups = await get_all_groups(client)
                        
                        await event.respond(
                            f"📊 **Broadcast Summary**\n\n"
                            f"📱 Userbot: `{client.phone}`\n"
                            f"👤 Name: {me.first_name}\n"
                            f"📝 Message: `{client.broadcast_message[:80]}...`\n"
                            f"🎯 Target Groups: {len(groups)}\n"
                            f"⏱ Interval: {interval} minute(s)\n"
                            f"🤖 Auto-reply: Enabled\n\n"
                            f"✅ Send **yes** to confirm\n"
                            f"❌ Send **no** to cancel"
                        )
                        
                        client.pending_interval = interval
                        client.waiting_for_interval = False
                        client.waiting_for_confirmation = True
                        
                    except ValueError:
                        await event.respond(
                            f"❌ Invalid number!\n\n"
                            f"Please send: **1**, **2**, **3**, **5**, or **10**"
                        )
                    return
                
                # Check if waiting for confirmation
                if hasattr(client, 'waiting_for_confirmation') and client.waiting_for_confirmation:
                    response = msg_text.strip().lower()
                    
                    if response in ['yes', 'y', 'confirm']:
                        interval = client.pending_interval
                        
                        await event.respond(
                            f"✅ **Broadcasting Started!**\n\n"
                            f"📱 Userbot: `{client.phone}`\n"
                            f"⏱ Interval: {interval} minute(s)\n"
                            f"🔄 Status: Active\n"
                            f"🤖 Auto-reply: Active\n\n"
                            f"Use /stop to stop broadcasting."
                        )
                        
                        # Start broadcasting task
                        task_id = f"{client.phone}_{interval}"
                        if task_id in active_tasks:
                            active_tasks[task_id].cancel()
                            log_message(client.phone, "⚠️ Cancelled previous task")
                        
                        task = asyncio.create_task(
                            send_to_all_groups(client, client.broadcast_message, interval, task_id)
                        )
                        active_tasks[task_id] = task
                        log_message(client.phone, f"✓ Started broadcast with {interval}min interval")
                        
                        client.waiting_for_confirmation = False
                        client.pending_interval = None
                        
                    elif response in ['no', 'n', 'cancel']:
                        await event.respond("❌ Broadcast cancelled.")
                        client.waiting_for_confirmation = False
                        client.pending_interval = None
                        client.broadcast_message = None
                    else:
                        await event.respond("Please send **yes** to confirm or **no** to cancel")
                    
                    return
                
                # Store the message to broadcast
                client.broadcast_message = msg_text
                client.waiting_for_interval = True
                
                groups = await get_all_groups(client)
                
                await event.respond(
                    f"📢 **Message Received!**\n\n"
                    f"📝 Preview: `{client.broadcast_message[:100]}{'...' if len(client.broadcast_message) > 100 else ''}`\n"
                    f"🎯 Target: {len(groups)} groups\n\n"
                    f"⏱ **Select broadcast interval:**\n"
                    f"Send: **1** (1 min), **2** (2 min), **3** (3 min), **5** (5 min), or **10** (10 min)"
                )
                
            except Exception as e:
                log_message(client.phone, f"❌ Error in message handler: {str(e)}")
                await event.respond(f"❌ Error: {str(e)}")
        
        @client.on(events.NewMessage(from_users=ADMIN_ID, pattern='/stop'))
        async def stop_handler(event):
            """Stop all broadcasting tasks for this userbot"""
            try:
                stopped = 0
                for task_id in list(active_tasks.keys()):
                    if task_id.startswith(client.phone):
                        active_tasks[task_id].cancel()
                        del active_tasks[task_id]
                        stopped += 1
                
                # Reset states
                client.waiting_for_interval = False
                client.waiting_for_confirmation = False
                client.broadcast_message = None
                client.pending_interval = None
                
                if stopped > 0:
                    await event.respond(f"🛑 Stopped {stopped} broadcasting task(s)!")
                    log_message(client.phone, f"🛑 Stopped {stopped} task(s)")
                else:
                    await event.respond("ℹ️ No active broadcasts to stop.")
            except Exception as e:
                log_message(client.phone, f"❌ Error in stop handler: {str(e)}")
        
        @client.on(events.NewMessage(from_users=ADMIN_ID, pattern='/status'))
        async def status_handler(event):
            """Show status of this userbot"""
            try:
                groups = await get_all_groups(client)
                active = sum(1 for tid in active_tasks.keys() if tid.startswith(client.phone))
                
                await event.respond(
                    f"📊 **Userbot Status**\n\n"
                    f"📱 Phone: `{client.phone}`\n"
                    f"👤 Name: {me.first_name}\n"
                    f"🆔 Username: @{client.username}\n"
                    f"🎯 Groups: {len(groups)}\n"
                    f"🔄 Active Broadcasts: {active}\n"
                    f"🤖 Auto-reply: Enabled\n"
                    f"✅ Status: Online"
                )
            except Exception as e:
                log_message(client.phone, f"❌ Error in status handler: {str(e)}")
        
        @client.on(events.NewMessage(from_users=ADMIN_ID, pattern='/groups'))
        async def groups_handler(event):
            """List all groups"""
            try:
                groups = await get_all_groups(client)
                
                if not groups:
                    await event.respond("ℹ️ No groups found.")
                    return
                
                groups_list = "\n".join([f"📁 {i+1}. {g.title}" for i, g in enumerate(groups[:20])])
                
                await event.respond(
                    f"📂 **Groups List** ({len(groups)} total)\n\n"
                    f"{groups_list}\n\n"
                    f"{'...' if len(groups) > 20 else ''}"
                )
            except Exception as e:
                log_message(client.phone, f"❌ Error in groups handler: {str(e)}")
        
        return client
        
    except Exception as e:
        log_message(bot_info.get('phone', 'Unknown'), f"❌ Fatal error starting userbot: {str(e)}")
        return None

async def main():
    """Main function to run all userbots"""
    print("=" * 60)
    print("         TELEGRAM USERBOT MANAGER v2.1")
    print("=" * 60)
    
    # Load existing config
    config = load_config()
    
    # Ask if user wants to add new bots or use existing
    if config['userbots']:
        print(f"\n✓ Found {len(config['userbots'])} existing userbot(s)")
        choice = input("Use existing config? (y/n): ").lower()
        
        if choice != 'y':
            num_bots = int(input("\nHow many NEW userbots to add? "))
            
            for i in range(num_bots):
                print(f"\n--- New Userbot {i+1} ---")
                api_id = input(f"API ID: ")
                api_hash = input(f"API Hash: ")
                phone = input(f"Phone (+1234567890): ")
                
                config['userbots'].append({
                    'api_id': api_id,
                    'api_hash': api_hash,
                    'phone': phone
                })
            
            save_config(config)
    else:
        num_bots = int(input("\nHow many userbots do you want to create? "))
        
        print("\n" + "=" * 60)
        print("          ENTER CREDENTIALS FOR EACH USERBOT")
        print("=" * 60)
        
        for i in range(num_bots):
            print(f"\n--- Userbot {i+1} ---")
            api_id = input(f"API ID: ")
            api_hash = input(f"API Hash: ")
            phone = input(f"Phone (+1234567890): ")
            
            config['userbots'].append({
                'api_id': api_id,
                'api_hash': api_hash,
                'phone': phone
            })
        
        save_config(config)
    
    print("\n" + "=" * 60)
    print("              STARTING USERBOTS...")
    print("=" * 60 + "\n")
    
    clients = []
    active_tasks = {}
    
    # Start all userbots
    for bot_info in config['userbots']:
        try:
            client = await start_userbot(bot_info, active_tasks)
            if client:
                clients.append(client)
        except Exception as e:
            print(f"✗ Failed to start {bot_info['phone']}: {str(e)}")
    
    if not clients:
        print("\n❌ No userbots started successfully!")
        return
    
    print("\n" + "=" * 60)
    print("           ALL USERBOTS ARE RUNNING!")
    print("=" * 60)
    print(f"\n👤 Admin ID: {ADMIN_ID}")
    print(f"🤖 Active Userbots: {len(clients)}")
    print(f"🔧 Config File: {CONFIG_FILE}")
    print("\n📱 Commands:")
    print("  /start  - Show userbot info")
    print("  /status - Show current status")
    print("  /stop   - Stop broadcasting")
    print("  /groups - List all groups")
    print("  /help   - Show all commands")
    print("\n💬 Send your message, then send interval (1, 2, 3, 5, or 10)")
    print(f"\n🤖 Auto-reply enabled for: {', '.join(CATCH_WORDS[:3])}...")
    print("=" * 60 + "\n")
    
    # Keep the script running
    try:
        await asyncio.gather(*[client.run_until_disconnected() for client in clients])
    except KeyboardInterrupt:
        print("\n\n⚠️ Shutting down...")
        for task in active_tasks.values():
            task.cancel()
        print("✓ All tasks stopped. Goodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Program terminated by user.")
