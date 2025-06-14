import logging
import re
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = '7783040596:AAGseC6xwxmMhIj5Vekh7tIkimivMVXYlbg'

def escape(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def extract_email(text: str) -> str:
    m = re.search('<b>(.*?)</b>', text)
    return m.group(1) if m else "Unknown"

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📩 Send me an Instagram username or email to attempt a reset.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    username_input = update.message.text.strip()
    telegram_username = update.effective_user.username or "Unknown"
    time_now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    logging.info(f"User @{telegram_username} requested reset for: {username_input}")

    success, result = send_reset_request(username_input)

    if success:
        caption = (
            f"{escape('📗 *Instagram Reset Request Sent Successfully*')}

"
            f"{escape('🧑‍💻 *User:*')} [@{escape(telegram_username)}](https://t.me/{escape(telegram_username)})
"
            f"{escape('📌 *Target Username:*')} `{escape(username_input)}`
"
            f"{escape('📒 *Masked Email:*')} `{escape(result)}`
"
            f"{escape('🕒 *Requested At:*')} {escape(time_now)}
"
            f"{escape('🌐 *Origin:*')} Telegram Bot
"
            f"{escape('📍 *Bot Name:*')} @{escape(context.bot.username)}

"
            f"{escape('✅ *Password reset link sent!*')}

"
            f"{escape('🔒 *Note:*')} {escape('Check the inbox & spam folder of the email above.')}

"
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

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
