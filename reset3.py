import logging
import re
import requests
import asyncio
from time import time
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Your Bot Token ---
BOT_TOKEN = '8082069431:AAHun8oTXXPzqZvgCU-nkmUOQMe0ksVBaBQ'  # Replace with your actual token

# --- Escape Markdown V2 ---
def escape(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# --- Extract Masked Email from HTML Response ---
def extract_email(text: str) -> str:
    m = re.search('<b>(.*?)</b>', text)
    return m.group(1) if m else "Unknown"

# --- Send Password Reset Request to Instagram ---
def send_reset_request(username: str):
    try:
        response = requests.post(
            'https://www.instagram.com/accounts/account_recovery_send_ajax/',
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://www.instagram.com/accounts/password/reset/',
                'X-CSRFToken': 'csrftoken'
            },
            data={'email_or_username': username}
        )
        if response.status_code == 200:
            masked = extract_email(response.text)
            return True, masked
        return False, "Reset failed or username not found."
    except Exception as e:
        return False, str(e)

# --- /start Handler ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use /reset to begin an Instagram reset request.")

# --- /reset Handler ---
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_username"] = True
    context.user_data["reset_start_time"] = time()
    context.user_data["reset_username"] = update.effective_user.username or "Unknown"

    keyboard = [[InlineKeyboardButton("❌ Cancel Reset", callback_data="cancel_reset")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text("⏳ Countdown starting...", reply_markup=reply_markup)
    context.user_data["countdown_message_id"] = msg.message_id
    context.user_data["countdown_chat_id"] = msg.chat.id

    asyncio.create_task(countdown_timer(context, 60))

# --- Countdown Timer with Spinner + Bar + Cancel Button ---
async def countdown_timer(context, seconds):
    spinner = ['|', '/', '-', '\\']
    bar_length = 30
    username = context.user_data.get("reset_username", "Unknown")

    for remaining in range(seconds - 1, -1, -1):
        await asyncio.sleep(1)

        if not context.user_data.get("awaiting_username"):
            return

        try:
            percent = int(((seconds - remaining) / seconds) * 100)
            filled = int((percent / 100) * bar_length)
            bar = '▓' * filled + '░' * (bar_length - filled)
            spin = spinner[remaining % len(spinner)]

            text = (
                f"*👤 User:* @{username}\n"
                f"🔄 *{remaining}s* {spin}\n"
                f"`[{bar}] {percent}%`\n"
                f"📨 *Please send the Instagram username or email...*"
            )

            keyboard = [[InlineKeyboardButton("❌ Cancel Reset", callback_data="cancel_reset")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.edit_message_text(
                chat_id=context.user_data["countdown_chat_id"],
                message_id=context.user_data["countdown_message_id"],
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.warning(f"Countdown edit failed: {e}")

    # Timeout reached
    context.user_data["awaiting_username"] = False
    try:
        await context.bot.edit_message_text(
            chat_id=context.user_data["countdown_chat_id"],
            message_id=context.user_data["countdown_message_id"],
            text="⏳ *Timeout expired.* Please send /reset again.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.warning(f"Timeout message failed: {e}")

# --- Inline Cancel Button Handler ---
async def cancel_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_username"] = False
    for key in ["reset_start_time", "countdown_message_id", "countdown_chat_id", "reset_username"]:
        context.user_data.pop(key, None)
    await query.edit_message_text("❌ *Reset canceled by user.*", parse_mode="Markdown")

# --- Handle Text (username input) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_username"):
        await update.message.reply_text("ℹ️ Please use /reset before sending an Instagram username.")
        return

    chat_id = update.effective_chat.id
    username_input = update.message.text.strip()
    telegram_username = update.effective_user.username or "Unknown"
    time_now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    logging.info(f"User @{telegram_username} requested reset for: {username_input}")
    context.user_data["awaiting_username"] = False

    success, result = send_reset_request(username_input)

    # Clean up
    for key in ["reset_start_time", "countdown_message_id", "countdown_chat_id", "reset_username"]:
        context.user_data.pop(key, None)

    if success:
        caption = (
            f"{escape('📗 *Instagram Reset Request Sent Successfully*')}\n\n"
            f"{escape('🧑‍💻 *User:*')} [@{escape(telegram_username)}](https://t.me/{escape(telegram_username)})\n"
            f"{escape('📌 *Target Username:*')} `{escape(username_input)}`\n"
            f"{escape('📒 *Masked Email:*')} `{escape(result)}`\n"
            f"{escape('🕒 *Requested At:*')} {escape(time_now)}\n"
            f"{escape('🌐 *Origin:*')} Telegram Bot\n"
            f"{escape('📍 *Bot Name:*')} @{escape(context.bot.username)}\n\n"
            f"{escape('✅ *Password reset link sent!*')}\n\n"
            f"{escape('🔒 *Note:*')} {escape('Check the inbox & spam folder of the email above.')}\n\n"
            f"{escape('🛡️ This request was triggered via Telegram bot for testing or account access help.')}"
        )

        await context.bot.send_photo(
            chat_id=chat_id,
            photo="https://upload.wikimedia.org/wikipedia/commons/thumb/9/96/Instagram.svg/800px-Instagram.svg.png",
            caption=caption,
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(f"❌ Failed: {result}")

# --- Main Function ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(cancel_reset, pattern="^cancel_reset$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 Bot is running...")
    app.run_polling()

# --- Entry Point ---
if __name__ == "__main__":
    main()
