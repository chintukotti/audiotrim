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

TOKEN = os.environ.get("TOKEN")

START_TIME, END_TIME = range(2)
user_audio = {}
user_filename = {}

# ------------------ HELPER FUNCTION ------------------

def mmss_to_milliseconds(time_str: str) -> int:
    """
    Converts mm:ss to milliseconds
    Example: 01:30 -> 90000 ms
    """
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError
    minutes = int(parts[0])
    seconds = int(parts[1])
    if seconds < 0 or seconds >= 60:
        raise ValueError
    return (minutes * 60 + seconds) * 1000

# ------------------ START COMMAND ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *Audio Trim Bot*\n\n"
        "Send me any audio file (mp3 / voice / document).\n"
        "Then enter time in this format:\n\n"
        "`mm:ss`  (Example: `01:30`)\n\n"
        "I will trim and send audio with the *same file name* ✅",
        parse_mode="Markdown"
    )

# ------------------ AUDIO HANDLER ------------------

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.audio:
        audio = msg.audio
        filename = msg.audio.file_name or "audio.mp3"
    elif msg.voice:
        audio = msg.voice
        filename = "voice_note.mp3"
    elif msg.document:
        audio = msg.document
        filename = msg.document.file_name or "audio.mp3"
    else:
        await msg.reply_text("❌ Unsupported file type.")
        return ConversationHandler.END

    file = await audio.get_file()

    input_path = f"{msg.from_user.id}_input"
    await file.download_to_drive(input_path)

    user_audio[msg.from_user.id] = input_path
    user_filename[msg.from_user.id] = filename

    await msg.reply_text(
        "⏱️ Enter *START time* in `mm:ss` format\n"
        "Example: `01:30`",
        parse_mode="Markdown"
    )
    return START_TIME

# ------------------ GET START TIME ------------------

async def get_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_ms = mmss_to_milliseconds(update.message.text)
        context.user_data["start_ms"] = start_ms
    except Exception:
        await update.message.reply_text(
            "❌ Invalid format.\nUse `mm:ss` (Example: `01:30`)",
            parse_mode="Markdown"
        )
        return START_TIME

    await update.message.reply_text(
        "⏱️ Enter *END time* in `mm:ss` format",
        parse_mode="Markdown"
    )
    return END_TIME

# ------------------ GET END TIME & TRIM ------------------

async def get_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end_ms = mmss_to_milliseconds(update.message.text)
        start_ms = context.user_data["start_ms"]
        if end_ms <= start_ms:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "❌ End time must be greater than start time.\n"
            "Use `mm:ss` format.",
            parse_mode="Markdown"
        )
        return END_TIME

    user_id = update.message.from_user.id
    input_audio = user_audio.get(user_id)
    original_name = user_filename.get(user_id, "trimmed_audio.mp3")

    # Create output file name
    output_file = f"trimmed_{original_name}"

    try:
        audio = AudioSegment.from_file(input_audio)
        trimmed_audio = audio[start_ms:end_ms]
        trimmed_audio.export(output_file, format="mp3")

        await update.message.reply_audio(
            audio=open(output_file, "rb"),
            filename=original_name,
            caption="✅ Trimmed audio"
        )

    except Exception as e:
        await update.message.reply_text("❌ Error while processing audio.")
        print(e)

    finally:
        if input_audio and os.path.exists(input_audio):
            os.remove(input_audio)
        if os.path.exists(output_file):
            os.remove(output_file)

    return ConversationHandler.END

# ------------------ MAIN ------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
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
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
