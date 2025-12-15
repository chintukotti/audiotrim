import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from pydub import AudioSegment

# Read token from Railway service variable
TOKEN = os.environ.get("TOKEN")

# Conversation states
START_TIME, END_TIME = range(2)

# Store user audio temporarily
user_audio = {}

# ------------------ START COMMAND ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *Audio Trim Bot*\n\n"
        "Send me any audio file (mp3 / voice / document).\n"
        "I will ask start & end time in minutes.\n\n"
        "Example: `1.5` means 1 minute 30 seconds.",
        parse_mode="Markdown"
    )

# ------------------ AUDIO HANDLER ------------------

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.audio:
        audio = message.audio
    elif message.voice:
        audio = message.voice
    elif message.document:
        audio = message.document
    else:
        await message.reply_text("❌ Unsupported file type.")
        return ConversationHandler.END

    file = await audio.get_file()

    file_path = f"{message.from_user.id}_input"
    await file.download_to_drive(file_path)

    user_audio[message.from_user.id] = file_path

    await message.reply_text(
        "⏱️ Enter *START time* in minutes.\n"
        "Example: `1.5`",
        parse_mode="Markdown"
    )
    return START_TIME

# ------------------ GET START TIME ------------------

async def get_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_time = float(update.message.text)
        if start_time < 0:
            raise ValueError
        context.user_data["start_time"] = start_time
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number (example: 1.5)")
        return START_TIME

    await update.message.reply_text(
        "⏱️ Enter *END time* in minutes.",
        parse_mode="Markdown"
    )
    return END_TIME

# ------------------ GET END TIME & TRIM ------------------

async def get_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end_time = float(update.message.text)
        start_time = context.user_data["start_time"]
        if end_time <= start_time:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ End time must be greater than start time."
        )
        return END_TIME

    user_id = update.message.from_user.id
    input_audio = user_audio.get(user_id)

    try:
        audio = AudioSegment.from_file(input_audio)
        trimmed_audio = audio[start_time * 60 * 1000 : end_time * 60 * 1000]

        output_file = f"{user_id}_trimmed.mp3"
        trimmed_audio.export(output_file, format="mp3")

        await update.message.reply_audio(
            audio=open(output_file, "rb"),
            caption="✅ Trimmed audio"
        )

    except Exception as e:
        await update.message.reply_text("❌ Error while processing audio.")
        print(e)

    finally:
        # Clean up files
        if input_audio and os.path.exists(input_audio):
            os.remove(input_audio)
        if os.path.exists(f"{user_id}_trimmed.mp3"):
            os.remove(f"{user_id}_trimmed.mp3")

    return ConversationHandler.END

# ------------------ MAIN ------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.AUDIO | filters.VOICE | filters.Document.ALL,
                audio_handler
            )
        ],
        states={
            START_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_start_time)
            ],
            END_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_end_time)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conversation)

    app.run_polling()

if __name__ == "__main__":
    main()
