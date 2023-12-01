import os
import re
import ssl
import time
import pickle as p
import atexit as a
import smtplib
import threading
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler
from telegram.ext.filters import TEXT, Document
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

load_dotenv()

try:
    open('users.dat', 'x')
except:
    pass

with open("users.dat", "rb") as f:
    try:
        users = p.load(f)
    except:
        users = {}
    print(f"Users: {users}")

try:
    open('stats.dat', 'x')
except:
    pass

with open("stats.dat", "rb") as f:
    try:
        user_stats = p.load(f)
    except:
        user_stats = {"total_sent": 0, "sent_this_month": 0, "monthly_users": [], "total_users": []}
    print(f"Stats: {user_stats}")

TOKEN = os.getenv("TELEGRAM_TOKEN")
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SUPPORTED_FILETYPES = ["application/pdf", "application/epub+zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword", "application/rtf", "text/html", "text/plain", "application/zip", "image/jpeg", "image/gif", "image/bmp", "image/png"]
CALLBACK_SUPPORTED = "supported_filetypes"
CALLBACK_BACK = "back"
KOFI_URL = "https://ko-fi.com/gabrielsparkes"

def first_of_month():
    print("Started checking date")
    while True:
        today = datetime.today().day
        if today == 1:
            print("Today is first of month")
            user_stats["monthly_users"] = []
            user_stats["sent_this_month"] = 0
            with open("stats.dat", "wb") as f:
                p.dump(user_stats, f)
        time.sleep(86400)

def is_valid_email(text: str):
    pattern = r'^[a-zA-Z0-9._%+-]+@kindle\.com$'
    if re.match(pattern, text):
        return True
    else:
        return False
    
def send_mail(send_from: str, send_to: str, text: str, subject: str, file: str, file_name: str):
    s = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context())

    message = MIMEMultipart()
    message['From'] = send_from
    message['To'] = send_to
    message['Date'] = formatdate(localtime=True)
    message['Subject'] = subject
    message.attach(MIMEText(text))

    with open(file, "rb") as f:
        part = MIMEApplication(f.read(), Name=f.name)
    part['Content-Disposition'] = f'attachment; filename="{file_name}"'
    message.attach(part)

    with s:
        s.login(KINDLE_EMAIL, EMAIL_PASSWORD)
        s.sendmail(send_from, send_to, message.as_string())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id] = {}
    buttons = [[InlineKeyboardButton("View supported filetypes", callback_data=CALLBACK_SUPPORTED)], [InlineKeyboardButton("Support me", KOFI_URL)]]
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"Hello {update.effective_user.first_name}!\nI can help you send documents to your kindle!\nSend /setup for a tutorial on how to enable this bot to send files to your kindle email", parse_mode="HTML", reply_markup=keyboard)

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id]["setting"] = True
    await update.message.reply_text(f"<b><i>Setup</i></b>\nGo to your <a href=\"https://amazon.com/myk\">Manage Your Content and Devices page</a>, then navigate to <b>Preferences</b> and click <b>Personal Document Settings</b>. Make a note of your kindle's email address, which you may also modify.\nIn the <b>Approved Personal Document E-mail List</b> section, add {KINDLE_EMAIL}\nNow just send me your kindle email and we're done! 😉\nIf you want me to <b>forget</b> your email address, send /forget at any time", parse_mode="HTML")

async def set_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id]["setting"] = True
    await update.message.reply_text("OK, send me your email in the next message")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if users[user_id]["setting"]:
        users[user_id]["setting"] = False
        await update.message.reply_text("Cancelled")
    else:
        await update.message.reply_text("Nothing to cancel!")

async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if "email" in users[user_id]:
        del users[user_id]["email"]
        await update.message.reply_text("Your email address has been removed")
    else:
        await update.message.reply_text("Nothing to forget!")

async def document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {}
    if not "email" in users[user_id]:
        await update.message.reply_text("Email is not set!")
    else:
        await update.message.reply_text("Working on it...")
        try:
            mime_type = update.message.document.mime_type
            if mime_type not in SUPPORTED_FILETYPES:
                await update.message.reply_text("It looks like your file is not supported by kindle. Remember that PDF and EPUB files have the best support")
                return
            to = users[user_id]["email"]
            file_id = update.message.document.file_id
            file = await context.bot.get_file(file_id)
            file_name = update.message.document.file_name
            path = await file.download_to_drive()
            send_mail(KINDLE_EMAIL, to, "Here's your file! :)", "Your file, sent via @sendtokindle_robot on telegram", path, file_name)
            os.remove(path)
            await update.message.reply_text("Your file has been sent successfully! Please wait a minute or two for it to show up on your device")
            user_stats["total_sent"] += 1
            user_stats["sent_this_month"] += 1
            if user_id not in user_stats["monthly_users"]:
                user_stats["monthly_users"].append(user_id)
            if user_id not in user_stats["total_users"]:
                user_stats["total_users"].append(user_id)
        except Exception as e:
            await update.message.reply_text("An error occurred 😞")
            print(e)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE, user_stats=user_stats) -> None:
    if user_stats == {}:
        user_stats = {"total_sent": 0, "sent_this_month": 0, "monthly_users": [], "total_users": []}
    await update.message.reply_text(f"<b><i>Stats</i></b>\n<b>Total number of documents sent: </b><i>{user_stats['total_sent']}</i>\n<b>Number of documents sent this month: </b><i>{user_stats['sent_this_month']}</i>\n<b>Total number of users: </b><i>{len(user_stats['total_users'])}</i>\n<b>Number of users this month: </b><i>{len(user_stats['monthly_users'])}</i>", parse_mode="HTML")

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {}
    if not "setting" in users[user_id]:
        users[user_id]["setting"] = False
    if not "id" in users[user_id]:
        users[user_id]["id"] = user_id
    if users[user_id]["setting"]:
        if is_valid_email(update.message.text):
            users[user_id]["email"] = update.message.text
            await update.message.reply_text(f"Successfully set your email to <i>{update.message.text}</i>!", parse_mode="HTML")
            users[user_id]["setting"] = False
        else:
            await update.message.reply_text("Please enter a valid kindle email address (must end in '@kindle.com'!)")

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == CALLBACK_SUPPORTED:
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=CALLBACK_BACK)]]
        keyboard = InlineKeyboardMarkup(buttons)
        await update.callback_query.message.edit_text("The following filetypes are currently supported: EPUB (.epub), Adobe PDF (.pdf), Microsoft Word (.doc, .docx), Rich Text Format (.rtf), HTML (.htm, .html), text documents (.txt), compressed documents (.zip), JPEG images (.jpg), GIF (.gif), Bitmap (.bmp), PNG (.png).\n<b>If you send a file with a filetype other than the ones listed, I won't be able to forward it</b>", parse_mode="HTML", reply_markup=keyboard)
    elif data == CALLBACK_BACK:
        buttons = [[InlineKeyboardButton("View supported filetypes", callback_data=CALLBACK_SUPPORTED)], [InlineKeyboardButton("Support me", KOFI_URL)]]
        keyboard = InlineKeyboardMarkup(buttons)
        await update.callback_query.message.edit_text(f"Hello {update.effective_user.first_name}!\nI can help you send your documents to your kindle!\nSend /setup for a tutorial on how to enable this bot to send it files and to set your kindle's email", reply_markup=keyboard)

def exit_handler():
    with open("users.dat", "wb") as f:
        p.dump(users, f)
    with open("stats.dat", "wb") as f:
        p.dump(user_stats, f)
    print("Goodbye!")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setup", setup))
app.add_handler(CommandHandler("set", set_email))
app.add_handler(CommandHandler("cancel", cancel))
app.add_handler(CommandHandler("forget", forget))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(TEXT, message))
app.add_handler(MessageHandler(Document.ALL, document))
app.add_handler(CallbackQueryHandler(callback))
a.register(exit_handler)

thread = threading.Thread(target=first_of_month)
thread.daemon = True
thread.start()

app.run_polling()