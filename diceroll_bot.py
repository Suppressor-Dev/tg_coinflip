import logging
import random
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

class UserStats:
    def __init__(self):
        self.balance = 1000 # Starting balance
        self.points = 0
        self.total_rolls = 0
        self.total_won = 0
        self.total_lost = 0

# Use a nested defaultdict: chat_id -> user_id -> UserStats
chat_user_stats = defaultdict(lambda: defaultdict(UserStats))
pending_wagers = {}

# Bot only works in this topic
ALLOWED_TOPIC_ID = 320
COIN_EMOJI = "🪙"

# Define conversation states
WAGER, ROLL = range(2)

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_command_allowed(update):
        return ConversationHandler.END

    user = update.effective_user
    chat_id = update.effective_chat.id

    # Check if user exists in stats, if not, initialize
    if user.id not in chat_user_stats[chat_id]:
        chat_user_stats[chat_id][user.id] = UserStats()

    stats = chat_user_stats[chat_id][user.id]

    await update.message.reply_text(
        f"Your current balance is {stats.balance}. How much would you like to wager?", 
        reply_markup=ForceReply()
    )
    return WAGER

async def wager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    stats = chat_user_stats[chat_id][user.id]

    try:
        wager_amount = int(update.message.text)
        if wager_amount <= 0 or wager_amount > stats.balance:
            await update.message.reply_text(
                "Please enter a valid wager amount within your balance.",
                reply_markup=ForceReply()
            )
            return WAGER
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number.",
            reply_markup=ForceReply()
        )
        return WAGER

    pending_wagers[(chat_id, user.id)] = wager_amount
    
    await update.message.reply_text(
        f"You've wagered {wager_amount}. Please send the 🎲 emoji to roll the dice!",
        reply_markup=ForceReply()
    )
    return ROLL

async def handle_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.dice is None or update.message.dice.emoji != "🎲":
        await update.message.reply_text("Please send the 🎲 emoji to roll the dice.")
        return ROLL

    user = update.effective_user
    chat_id = update.effective_chat.id
    stats = chat_user_stats[chat_id][user.id]
    wager_amount = pending_wagers.pop((chat_id, user.id), None)

    if wager_amount is None:
        await update.message.reply_text("Something went wrong. Please start over with /roll.")
        return ConversationHandler.END

    dice_value = update.message.dice.value

    stats.total_rolls += 1
    if dice_value > 3:  # Win condition: rolling 4, 5, or 6
        winnings = int(wager_amount * 1.5)
        stats.balance += (winnings - wager_amount)
        stats.total_won += winnings - wager_amount
        result_message = f"🎉 You rolled a {dice_value} and won! You receive {winnings}."
    else:
        stats.balance -= wager_amount
        stats.total_lost += wager_amount
        result_message = f"😔 You rolled a {dice_value} and lost your wager of {wager_amount}."

    result_message += f"\nYour new balance is {stats.balance}."
    await update.message.reply_text(result_message)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Roll cancelled.")
    return ConversationHandler.END



# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Define a few command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome to the Dice Roll Game Bot! Use /roll to start.')

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_command_allowed(update):
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    stats = chat_user_stats[chat_id][user.id]
    
    if stats.total_rolls == 0:
        await update.message.reply_text("You haven't rolled any dice in this chat yet!")
        return

    stats_message = f"📊 Stats for {user.first_name} in this chat:\n\n" \
                    f"Current Balance: {stats.balance}\n" \
                    f"Total Rolls: {stats.total_rolls}\n" \
                    f"Total Won: {stats.total_won}\n" \
                    f"Total Lost: {stats.total_lost}\n"

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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"An error occurred: {context.error}")

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

    roll_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('roll', roll)],
        states={
            WAGER: [MessageHandler(filters.TEXT & ~filters.COMMAND, wager)],
            ROLL: [MessageHandler(filters.Dice, handle_roll)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(roll_conv_handler)
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_error_handler(error_handler)
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
