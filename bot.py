import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from pydub import AudioSegment

TOKEN = os.environ.get("6623259150:AAHObkFS2mYhPu3hbAhZzDduDbOCdhTDWKw")

START, END = range(2)
user_audio = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Audio Trim Bot\n\n"
        "Send me any audio file.\n"
        "I will ask start and end time in minutes."
    )

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio = update.message.audio or update.message.voice or update.message.document
    file = await audio.get_file()

    file_path = f"{update.message.from_user.id}.mp3"
    await file.download_to_drive(file_path)

    user_audio[update.message.from_user.id] = file_path
    await update.message.reply_text("⏱️ Enter START time (in minutes, e.g., 1.5)")
    return START

async def get_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["start"] = float(update.message.text)
    await update.message.reply_text("⏱️ Enter END time (in minutes)")
    return END

async def get_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = context.user_data["start"]
    end = float(update.message.text)

    user_id = update.message.from_user.id
    input_audio = user_audio[user_id]

    audio = AudioSegment.from_file(input_audio)
    trimmed = audio[start*60*1000:end*60*1000]

    output = f"trimmed_{user_id}.mp3"
    trimmed.export(output, format="mp3")

    await update.message.reply_audio(audio=open(output, "rb"))

    os.remove(input_audio)
    os.remove(output)

    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, audio_handler)],
        states={
            START: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_start)],
            END: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_end)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
