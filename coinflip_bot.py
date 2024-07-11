import logging
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from collections import defaultdict

class UserStats:
    def __init__(self):
        self.points = 0
        self.total_flips = 0
        self.wins = 0

# Use a nested defaultdict: chat_id -> user_id -> UserStats
chat_user_stats = defaultdict(lambda: defaultdict(UserStats))

# Bot only works in this topic
ALLOWED_TOPIC_ID = 320

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Define a few command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome to the Coinflip Game Bot! Use /flip to play.')

async def flip(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_command_allowed(update):
        return  # Silently ignore the command if it's not in the allowed topic

    user = update.effective_user
    chat_id = update.effective_chat.id
    user_guess = ' '.join(context.args).lower()

    if user_guess not in ['heads', 'tails']:
        await update.message.reply_text('Please guess either "heads" or "tails".')
        return

    result = random.choice(['heads', 'tails'])
    stats = chat_user_stats[chat_id][user.id]
    stats.total_flips += 1

    if user_guess == result:
        stats.points += 1
        stats.wins += 1
        message = f'It\'s {result.capitalize()}! You guessed correctly! 🎉\nYou earned 1 point. Your total in this chat: {stats.points} points.'
    else:
        message = f'It\'s {result.capitalize()}! You guessed wrong. Better luck next time! 🍀\nYour total in this chat: {stats.points} points.'

    await update.message.reply_text(f'Flipping a coin... {message}')

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_command_allowed(update):
        return  # Silently ignore the command if it's not in the allowed topic

    user = update.effective_user
    chat_id = update.effective_chat.id
    stats = chat_user_stats[chat_id][user.id]
    
    if stats.total_flips == 0:
        await update.message.reply_text("You haven't played any games in this chat yet!")
        return

    win_percentage = (stats.wins / stats.total_flips) * 100 if stats.total_flips > 0 else 0
    
    stats_message = f"📊 Stats for {user.first_name} in this chat:\n\n" \
                    f"Total Points: {stats.points}\n" \
                    f"Total Flips: {stats.total_flips}\n" \
                    f"Wins: {stats.wins}\n" \
                    f"Losses: {stats.total_flips - stats.wins}\n" \
                    f"Win Percentage: {win_percentage:.2f}%"

    await update.message.reply_text(stats_message)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_command_allowed(update):
        return  # Silently ignore the command if it's not in the allowed topic

    chat_id = update.effective_chat.id
    chat_stats = chat_user_stats[chat_id]
    sorted_users = sorted(chat_stats.items(), key=lambda x: x[1].points, reverse=True)
    leaderboard_text = "🏆 Leaderboard for this chat 🏆\n\n"
    for i, (user_id, stats) in enumerate(sorted_users[:5], start=1):
        user = await context.bot.get_chat(user_id)
        leaderboard_text += f"{i}. {user.first_name}: {stats.points} points\n"
    await update.message.reply_text(leaderboard_text)

def is_command_allowed(update: Update) -> bool:
    # Allow in private chats
    if update.effective_chat.type == 'private':
        return True
    
    # Check for the specific topic in group chats
    if update.effective_message.message_thread_id == ALLOWED_TOPIC_ID:
        return True
    
    # Optionally, inform the user if they're using the wrong topic
    if update.effective_chat.type in ['group', 'supergroup']:
        update.message.reply_text("This command can only be used in the Coin Flip channel.")
    
    return False

# to check topic ID
# async def debug_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     thread_id = update.effective_message.message_thread_id
#     await update.message.reply_text(f"The topic ID is: {thread_id}")
#     print(f"Debug - Topic ID: {thread_id}")



def main():
    # Replace 'YOUR_BOT_TOKEN' with the actual token you received from BotFather
    application = Application.builder().token('7486047910:AAHFwpW3Ou2K5cCB1PBKANmSDN5B-XwQOiw').build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("flip", flip))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("stats", show_stats))
    # application.add_handler(CommandHandler("debug_topic", debug_topic))

    # Start the Bot
    application.run_polling()

def is_command_allowed(update: Update) -> bool:
    # Allow in private chats
    if update.effective_chat.type == 'private':
        return True
    
    # Check for the specific topic in group chats
    if update.effective_message.message_thread_id == ALLOWED_TOPIC_ID:
        return True
    
    return False

if __name__ == '__main__':
    main()
