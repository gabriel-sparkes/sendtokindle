import os
import re
import ssl
import pickle as p
import atexit as a
import smtplib
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler
from telegram.ext.filters import TEXT, ATTACHMENT
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

TOKEN = os.getenv("TELEGRAM_TOKEN")
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def is_valid_email(text: str):
    pattern = r'^[a-zA-Z0-9._%+-]+@kindle\.com$'
    if re.match(pattern, text):
        return True
    else:
        return False
    
def send_mail(send_from: str, send_to: str, text:str, subject: str, file: str):
    s = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context())

    message = MIMEMultipart()
    message['From'] = send_from
    message['To'] = send_to
    message['Date'] = formatdate(localtime=True)
    message['Subject'] = subject
    message.attach(MIMEText(text))

    with open(file, "rb") as f:
        part = MIMEApplication(f.read(), Name=f.name)
    part['Content-Disposition'] = f'attachment; filename="{f.name}"'
    message.attach(part)

    with s:
        s.login(KINDLE_EMAIL, EMAIL_PASSWORD)
        s.sendmail(send_from, send_to, message.as_string())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id] = {}
    await update.message.reply_text(f"Hello {update.effective_user.first_name}!\nI can help you send your documents to your kindle!\nSend /setup for a tutorial on how to enable this bot to send it files and to set your kindle's email\nNB: I will forward any file you send me, but sending PDF and EPUB files only is <b>strongly recommended</b>", parse_mode="HTML")

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id]["setting"] = True
    await update.message.reply_text(f"<b><i>Setup</i></b>\nGo to your <a href=\"https://amazon.com/my\">Manage Your Content and Devices page</a>, then navigate to <b>Preferences</b> and click <b>Personal Document Settings</b>. Make a note of your kindle's email address, which you may also modify.\nIn the <b>Approved Personal Document E-mail List</b> section, add {KINDLE_EMAIL}\nNow just send me your kindle email and we're done! 😉\nIf you want me to <b>forget</b> your email address, send /forget at any time", parse_mode="HTML")

async def set_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users[update.effective_user.id]["setting"] = True
    await update.message.reply_text("OK, send me your email in the next message")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if users[update.effective_user.id]["setting"]:
        users[update.effective_user.id]["setting"] = False
        await update.message.reply_text("Cancelled")
    else:
        await update.message.reply_text("Nothing to cancel!")

async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "email" in users[update.effective_user.id]:
        del users[update.effective_user.id]["email"]
        await update.message.reply_text("Your email address has been removed")
    else:
        await update.message.reply_text("Nothing to forget!")
        
async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not "setting" in users[update.effective_user.id]:
        users[update.effective_user.id]["setting"] = False
    if users[update.effective_user.id]["setting"]:
        if is_valid_email(update.message.text):
            users[update.effective_user.id]["email"] = update.message.text
            await update.message.reply_text(f"Successfully set your email to <i>{update.message.text}</i>!", parse_mode="HTML")
            users[update.effective_user.id]["setting"] = False
        else:
            await update.message.reply_text("Please enter a valid kindle email address (must end in '@kindle.com'!)")

async def attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not "email" in users[update.effective_user.id]:
        await update.message.reply_text("Email is not set!")
    else:
        await update.message.reply_text("Working on it...")
        try:
            to = users[update.effective_user.id]["email"]
            file_id = update.message.effective_attachment.file_id
            file = await context.bot.get_file(file_id)
            path = await file.download_to_drive()
            send_mail(KINDLE_EMAIL, to, "Here's your file! :)", "Your file", path)
            os.remove(path)
            await update.message.reply_text("Your file has been sent successfully!")
        except Exception as e:
            await update.message.reply_text("An error occurred 😞")
            print(e)

def exit_handler():
    with open("users.dat", "wb") as f:
        p.dump(users, f)
    print("Goodbye!")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setup", setup))
app.add_handler(CommandHandler("set", set_email))
app.add_handler(CommandHandler("cancel", cancel))
app.add_handler(CommandHandler("forget", forget))
app.add_handler(MessageHandler(TEXT, message))
app.add_handler(MessageHandler(ATTACHMENT, attachment))
a.register(exit_handler)

app.run_polling()