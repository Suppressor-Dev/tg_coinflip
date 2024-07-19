import logging
import random
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, AIORateLimiter
from database import create_connection

# Bot only works in this topic
ALLOWED_CHAT_ID = -1001234567890  # Replace with your specific chat ID

# Define conversation states
ROLL = 0

logging.basicConfig(filename='bot_activity.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_command_allowed(update):
        return ConversationHandler.END

    user = update.effective_user
    chat_id = update.effective_chat.id
    user_stats = get_user_stats(user.id, chat_id)
    
    if not user_stats:
        user_stats = {
            'user_id': user.id,
            'chat_id': chat_id,
            'username': user.username,
            'balance': 1000,
            'total_rolls': 0,
            'total_won': 0,
            'total_lost': 0
        }

    if not context.args:
        await update.message.reply_text("Please enter a wager amount with the /roll command. For example: /roll 100")
        return ConversationHandler.END

    try:
        wager_amount = int(context.args[0])
        if wager_amount <= 0 or wager_amount > user_stats['balance']:
            await update.message.reply_text(f"Please enter a valid wager amount between 1 and {user_stats['balance']}.")
            return ConversationHandler.END
        
        context.user_data['wager'] = wager_amount
        await update.message.reply_text(
            f"You've wagered {wager_amount}. Your current balance is {user_stats['balance']}. Please reply with the 🎲 emoji to roll the dice!"
        )
        return ROLL
    except ValueError:
        await update.message.reply_text("Please enter a valid number after /roll command.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels and ends the conversation."""
    user = update.message.from_user
    await update.message.reply_text(
        "Roll cancelled. You can start a new game with /roll."
    )
    return 

async def handle_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.dice or update.message.dice.emoji != "🎲":
        await update.message.reply_text("Please send the 🎲 emoji to roll the dice.")
        return ROLL

    user = update.effective_user
    chat_id = update.effective_chat.id
    wager_amount = context.user_data.get('wager')

    if wager_amount is None:
        await update.message.reply_text("Something went wrong. Please start over with /roll.")
        return ConversationHandler.END

    dice_value = update.message.dice.value

    if dice_value > 3:  # Win condition: rolling 4, 5, or 6
        winnings = int(wager_amount * 1.5)
        balance_change = winnings - wager_amount
        won = True
        result_message = f"🎉 You rolled a {dice_value} and won! You receive {winnings} (1.5x your wager)."
    else:
        balance_change = -wager_amount
        won = False
        result_message = f"😔 You rolled a {dice_value} and lost your wager of {wager_amount}."

    update_user_stats(user.id, chat_id, user.username, balance_change, won)
    user_stats = get_user_stats(user.id, chat_id)
    
    result_message += f"\nYour new balance is {user_stats['balance']}."
    await update.message.reply_text(result_message)
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
    user_stats = get_user_stats(user.id, chat_id)
    
    if not user_stats or user_stats['total_rolls'] == 0:
        await update.message.reply_text("You haven't rolled any dice in this chat yet!")
        return

    stats_message = f"📊 Stats for {user.username} in this chat:\n\n" \
                    f"Current Balance: {user_stats['balance']}\n" \
                    f"Total Rolls: {user_stats['total_rolls']}\n" \
                    f"Total Won: {user_stats['total_won']}\n" \
                    f"Total Lost: {user_stats['total_lost']}\n"

    await update.message.reply_text(stats_message)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_command_allowed(update):
        await update.message.reply_text("This bot can only be used in the allowed chat.")
        return

    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, balance FROM users WHERE chat_id = ? ORDER BY balance DESC LIMIT 5", (ALLOWED_CHAT_ID,))
    top_users = cur.fetchall()
    conn.close()

    if not top_users:
        await update.message.reply_text("No users have played in this chat yet!")
        return

    leaderboard_text = "🏆 Leaderboard 🏆\n\n"
    for i, (user_id, username, balance) in enumerate(top_users, start=1):
        leaderboard_text += f"{i}. {username}: {balance} balance\n"

    await update.message.reply_text(leaderboard_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"An error occurred: {context.error}")

# to check topic ID
# async def debug_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     thread_id = update.effective_message.message_thread_id
#     await update.message.reply_text(f"The topic ID is: {thread_id}")
#     print(f"Debug - Topic ID: {thread_id}")



def main():
    nest_asyncio.apply()
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    application = Application.builder().token('BOT Token here').build()

    roll_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('roll', roll)],
        states={
            ROLL: [MessageHandler(filters.Dice.ALL, handle_roll)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(roll_conv_handler)
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

def is_command_allowed(update: Update) -> bool:
    # Allow in private chats
    if update.effective_chat.type == 'private':
        return True
    # Allow in the specific chat only
    if update.effective_chat.id == ALLOWED_CHAT_ID:
        return True
    
    return False

def get_user_stats(user_id, chat_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
    user = cur.fetchone()
    conn.close()
    if user:
        return {
            'user_id': user[0],
            'chat_id': user[1],
            'username': user[2],
            'balance': user[3],
            'total_rolls': user[4],
            'total_won': user[5],
            'total_lost': user[6]
        }
    return None

def update_user_stats(user_id, chat_id, username, balance_change, won):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, chat_id, username, balance, total_rolls, total_won, total_lost)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(user_id, chat_id) DO UPDATE SET
        balance = balance + ?,
        total_rolls = total_rolls + 1,
        total_won = total_won + ?,
        total_lost = total_lost + ?,
        username = ?
    """, (user_id, chat_id, username, 1000 + balance_change, 
          1 if won else 0, 0 if won else 1, 
          balance_change, 1 if won else 0, 0 if won else 1, username))
    conn.commit()
    conn.close()
    
    # Log the update
    logging.info(f"Updated stats for user {username} (ID: {user_id}) in chat {chat_id}: Balance change: {balance_change}, Won: {won}")

if __name__ == '__main__':
    main()
