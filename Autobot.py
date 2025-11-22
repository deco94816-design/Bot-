"""
Telegram Hinglish Userbot Gambling System
Two userbots that play dice games for money and chat naturally in Hinglish
"""

import asyncio
import random
import time
from telethon import TelegramClient, events
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction
import google.generativeai as genai
from datetime import datetime

# ==================== CONFIGURATION ====================
API_ID_1 = 28782318
API_HASH_1 = 'ea72ed0d16604c27198d5dd1a53f2a69'
PHONE_1 = '+919958369726'
SESSION_NAME_1 = 'userbot1'

API_ID_2 = 23024283
API_HASH_2 = '658d604b76eb60d7c99596b7440f90af'
PHONE_2 = '+919861492291'  # Add second phone number
SESSION_NAME_2 = 'userbot2'

TARGET_GROUP = '-1002208126961'  # Add your group username (e.g., '@mygamblinggroup') or ID
GEMINI_API_KEY = 'AIzaSyB7tUodWvArpYuIlalW8M6yvKgi9oLibL0'

BOT_1_NAME = "coderarisu"
BOT_2_NAME = "Gizmo"

# ==================== GEMINI AI SETUP ====================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# ==================== GAME CONFIGURATION ====================
GAMES = {
    '🎲': {'name': 'Dice', 'max_value': 6, 'rounds': 3},
    '🎯': {'name': 'Darts', 'max_value': 6, 'rounds': 2},
    '🏀': {'name': 'Basketball', 'max_value': 5, 'rounds': 2},
    '⚽': {'name': 'Football', 'max_value': 5, 'rounds': 2},
    '🎳': {'name': 'Bowling', 'max_value': 6, 'rounds': 2},
}

BET_AMOUNT = 10

# ==================== GLOBAL STATE ====================
conversation_history = []
bot1_wallet = 1000
bot2_wallet = 1000
last_user_message = None
last_user_name = None
game_in_progress = False

# ==================== AI RESPONSE GENERATOR ====================
def get_ai_response(bot_name, message, other_bot_name, is_user_reply=False):
    """Generate natural Hinglish response"""
    context = "\n".join(conversation_history[-8:])
    
    if is_user_reply:
        prompt = f"""You are {bot_name}, replying to a user in your Telegram group in natural Hinglish.

Rules:
1. Be friendly and casual with the user
2. Keep response SHORT (5-12 words)
3. Use Hinglish naturally (e.g., "haan bhai", "kya baat hai", "sahi hai yaar")
4. After replying, maybe suggest continuing the game with {other_bot_name}
5. Don't be formal, be like real friends

User said: {message}

Reply naturally as {bot_name}:"""
    else:
        prompt = f"""You are {bot_name}, playing gambling games with {other_bot_name} in Hinglish.

Rules:
1. Keep responses VERY SHORT (3-10 words)
2. React to game results naturally
3. Use casual Hinglish with emojis occasionally
4. Talk about money/bets naturally (e.g., "arre $10 gaye", "mast jeeta!", "aaj loss ho gaya")
5. Sometimes challenge for another round
6. Be competitive but friendly

Context: {context}

{other_bot_name}: {message}

Respond as {bot_name}:"""
    
    try:
        response = model.generate_content(prompt)
        reply = response.text.strip().strip('"').strip("'")
        return reply[:100]  # Keep it short
    except:
        fallbacks = ["haan bhai 😄", "sahi hai", "nice yaar", "arre waah!", "dekho yaar 😂", "mast hai"]
        return random.choice(fallbacks)

# ==================== TYPING ANIMATION ====================
async def simulate_typing(client, chat, duration=None):
    """Simulate typing"""
    if duration is None:
        duration = random.uniform(3, 6)
    try:
        await client(SetTypingRequest(peer=chat, action=SendMessageTypingAction()))
        await asyncio.sleep(duration)
    except:
        await asyncio.sleep(duration)

# ==================== USERBOT CLASS ====================
class GamblingUserbot:
    def __init__(self, api_id, api_hash, phone, session_name, bot_name, other_bot_name):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.bot_name = bot_name
        self.other_bot_name = other_bot_name
        self.wallet = 1000
        
    async def start(self):
        await self.client.start(phone=phone)
        print(f"✅ {self.bot_name} started! Wallet: ${self.wallet}")
        
        # Listen for user messages
        @self.client.on(events.NewMessage(chats=TARGET_GROUP))
        async def handler(event):
            global last_user_message, last_user_name, game_in_progress
            
            # Ignore own messages
            sender = await event.get_sender()
            if sender.id == (await self.client.get_me()).id:
                return
                
            # Check if it's the other bot
            other_bot_client = controller.bot2.client if self == controller.bot1 else controller.bot1.client
            other_bot_me = await other_bot_client.get_me()
            if sender.id == other_bot_me.id:
                return
            
            # User message detected
            if not game_in_progress:
                last_user_message = event.message.text
                last_user_name = sender.first_name or "bro"
                
                # Randomly one bot replies (70% chance)
                if random.random() < 0.7:
                    await asyncio.sleep(random.uniform(2, 5))
                    response = get_ai_response(self.bot_name, last_user_message, self.other_bot_name, is_user_reply=True)
                    await self.send_message(TARGET_GROUP, response)
        
    async def send_message(self, chat, message):
        typing_duration = random.uniform(3, 6)
        await simulate_typing(self.client, chat, typing_duration)
        await self.client.send_message(chat, message)
        conversation_history.append(f"{self.bot_name}: {message}")
        if len(conversation_history) > 30:
            conversation_history.pop(0)
        
    async def send_game(self, chat, emoji):
        await simulate_typing(self.client, chat, random.uniform(2, 4))
        message = await self.client.send_message(chat, emoji)
        await asyncio.sleep(4)  # Wait for animation
        
        try:
            full_message = await self.client.get_messages(chat, ids=message.id)
            if hasattr(full_message.media, 'value'):
                return full_message.media.value
        except:
            pass
        return random.randint(1, 6)

# ==================== MASTER CONTROLLER ====================
class MasterController:
    def __init__(self):
        self.bot1 = GamblingUserbot(API_ID_1, API_HASH_1, PHONE_1, SESSION_NAME_1, BOT_1_NAME, BOT_2_NAME)
        self.bot2 = GamblingUserbot(API_ID_2, API_HASH_2, PHONE_2, SESSION_NAME_2, BOT_2_NAME, BOT_1_NAME)
        
    async def start(self):
        await self.bot1.start()
        await self.bot2.start()
        print(f"\n🎰 Gambling Bots Active!")
        print(f"💰 {BOT_1_NAME}: ${self.bot1.wallet}")
        print(f"💰 {BOT_2_NAME}: ${self.bot2.wallet}")
        print(f"📱 Group: {TARGET_GROUP}\n")
        
    async def play_game(self, game_emoji):
        global game_in_progress
        game_in_progress = True
        
        game = GAMES[game_emoji]
        rounds = game['rounds']
        
        # Announce game
        challenges = [
            f"chalo {game['name']} khelte hain! ${BET_AMOUNT} ka bet 🔥",
            f"ek round {game['name']}? ${BET_AMOUNT} lagao 💪",
            f"bro {game['name']} challenge! ${BET_AMOUNT} 🎮",
            f"game time! {game['name']} ${BET_AMOUNT} ka 😎"
        ]
        await self.bot1.send_message(TARGET_GROUP, random.choice(challenges))
        
        await asyncio.sleep(random.uniform(3, 6))
        
        # Accept challenge
        accepts = [
            f"done bhai! ${BET_AMOUNT} ready hai 💸",
            "chalega! let's see 😤",
            f"bet lagao ${BET_AMOUNT}! bring it on 🔥",
            "haan yaar! dekhte hain 💪"
        ]
        await self.bot2.send_message(TARGET_GROUP, random.choice(accepts))
        
        await asyncio.sleep(random.uniform(3, 5))
        
        # Play rounds
        bot1_total = 0
        bot2_total = 0
        
        for round_num in range(rounds):
            # Announce round
            if rounds > 1:
                await self.bot1.send_message(TARGET_GROUP, f"Round {round_num + 1}! {game_emoji}")
                await asyncio.sleep(random.uniform(2, 4))
            
            # Bot 1 plays
            bot1_score = await self.bot1.send_game(TARGET_GROUP, game_emoji)
            bot1_total += bot1_score
            
            await asyncio.sleep(random.uniform(4, 7))
            
            # Bot 1 reacts
            reacts = [
                f"ho gaya! dekho 😎",
                f"nice! 🔥",
                f"aaja yaar",
                f"beat this! 💪",
                "let's see 😏"
            ]
            await self.bot1.send_message(TARGET_GROUP, random.choice(reacts))
            
            await asyncio.sleep(random.uniform(3, 6))
            
            # Bot 2 plays
            bot2_score = await self.bot2.send_game(TARGET_GROUP, game_emoji)
            bot2_total += bot2_score
            
            await asyncio.sleep(random.uniform(4, 7))
            
            # Bot 2 reacts to round
            if bot2_score > bot1_score:
                reacts = ["arre waah! 🔥", "boom! 💥", "haha dekha? 😂", "mast tha! 😎"]
            elif bot2_score < bot1_score:
                reacts = ["arre yaar 😅", "damn! 😤", "uff 😬", "acha hua 😏"]
            else:
                reacts = ["tie! 😮", "same! 😄", "arre match ho gaya!"]
            await self.bot2.send_message(TARGET_GROUP, random.choice(reacts))
            
            await asyncio.sleep(random.uniform(3, 5))
        
        # Determine winner
        await asyncio.sleep(random.uniform(2, 4))
        
        if bot1_total > bot2_total:
            # Bot 1 wins
            self.bot1.wallet += BET_AMOUNT
            self.bot2.wallet -= BET_AMOUNT
            
            winner_msgs = [
                f"yesss! jeeta bhai! ${BET_AMOUNT} mine! 💰🔥",
                f"arre waah! ${BET_AMOUNT} aa gaye! 😎💸",
                f"boom! +${BET_AMOUNT}! mast tha! 🎉",
                f"haha! ${BET_AMOUNT} pocket mein! 💪😂"
            ]
            await self.bot1.send_message(TARGET_GROUP, random.choice(winner_msgs))
            
            await asyncio.sleep(random.uniform(4, 7))
            
            loser_msgs = [
                f"arre yaar ${BET_AMOUNT} gaye 😅💸",
                f"damn! -${BET_AMOUNT} 😤",
                f"bro lucky tha tu! ${BET_AMOUNT} le 😏",
                f"acha chalega, ${BET_AMOUNT} tera 😅"
            ]
            await self.bot2.send_message(TARGET_GROUP, random.choice(loser_msgs))
            
        elif bot2_total > bot1_total:
            # Bot 2 wins
            self.bot2.wallet += BET_AMOUNT
            self.bot1.wallet -= BET_AMOUNT
            
            winner_msgs = [
                f"haha! ${BET_AMOUNT} jeeta! 💰😂",
                f"boom! +${BET_AMOUNT}! easy tha! 🔥",
                f"yesss! ${BET_AMOUNT} aa gaye! 😎💸",
                f"dekha? ${BET_AMOUNT} mine! 💪🎉"
            ]
            await self.bot2.send_message(TARGET_GROUP, random.choice(winner_msgs))
            
            await asyncio.sleep(random.uniform(4, 7))
            
            loser_msgs = [
                f"uff ${BET_AMOUNT} gaye yaar 😅",
                f"nice bro! ${BET_AMOUNT} le 😏",
                f"damn -${BET_AMOUNT} 😤💸",
                f"acha khela! ${BET_AMOUNT} tera 😅"
            ]
            await self.bot1.send_message(TARGET_GROUP, random.choice(loser_msgs))
            
        else:
            # Tie
            tie_msgs = [
                f"arre tie! ${BET_AMOUNT} wapas 😮",
                "draw ho gaya yaar! 😄",
                f"same same! no money lost 😅",
                "barabar! koi nahi 😏"
            ]
            await self.bot1.send_message(TARGET_GROUP, random.choice(tie_msgs))
        
        await asyncio.sleep(random.uniform(3, 5))
        
        # Show wallets
        wallet_msg = f"💰 Wallets:\n{BOT_1_NAME}: ${self.bot1.wallet}\n{BOT_2_NAME}: ${self.bot2.wallet}"
        await self.bot1.send_message(TARGET_GROUP, wallet_msg)
        
        game_in_progress = False
        
    async def continuous_gambling(self):
        # Initial greeting
        greetings = [
            f"yo {BOT_2_NAME}! ready to gamble? 🎲💰",
            f"arre {BOT_2_NAME} bhai! game khelein? 🎮",
            f"{BOT_2_NAME}! let's make some money! 💸🔥"
        ]
        await self.bot1.send_message(TARGET_GROUP, random.choice(greetings))
        
        await asyncio.sleep(random.uniform(4, 7))
        
        responses = [
            "haan bhai! lets go! 💪",
            "chalega yaar! bring it! 🔥",
            "ready hun! game on! 😎"
        ]
        await self.bot2.send_message(TARGET_GROUP, random.choice(responses))
        
        while True:
            try:
                # Wait before next game
                await asyncio.sleep(random.uniform(25, 50))
                
                # Check if user interrupted
                if last_user_message:
                    await asyncio.sleep(random.uniform(5, 10))
                
                # Random game
                game_emoji = random.choice(list(GAMES.keys()))
                await self.play_game(game_emoji)
                
                # Sometimes chat between games
                if random.random() < 0.4:
                    await asyncio.sleep(random.uniform(8, 15))
                    
                    chats = [
                        "chalo ek aur round? 🎲",
                        "bhai aaj mast chal raha hai 😎",
                        "next game? 🔥",
                        "aur khelen? 💪",
                        "yaar bore nahi ho raha? 😄",
                        "one more! 🎮"
                    ]
                    
                    bot = random.choice([self.bot1, self.bot2])
                    await bot.send_message(TARGET_GROUP, random.choice(chats))
                    
                    await asyncio.sleep(random.uniform(4, 8))
                    
                    other = self.bot2 if bot == self.bot1 else self.bot1
                    replies = [
                        "haan chalega! 😄",
                        "bilkul bhai! 🔥",
                        "lets do it! 💪",
                        "yaar mast hai! 😎",
                        "done! 👍"
                    ]
                    await other.send_message(TARGET_GROUP, random.choice(replies))
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(10)

# ==================== MAIN ====================
controller = MasterController()

async def main():
    await controller.start()
    await controller.continuous_gambling()

if __name__ == "__main__":
    print("🎰 Starting Gambling Bots...")
    print("="*50)
    asyncio.run(main())
