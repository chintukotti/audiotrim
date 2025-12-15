import os
import asyncio
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

SPINNER = ["⏳", "🔄", "🔃", "⌛"]

# ------------------ HELPERS ------------------

def mmss_to_milliseconds(time_str: str) -> int:
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError
    minutes = int(parts[0])
    seconds = int(parts[1])
    if seconds < 0 or seconds >= 60:
        raise ValueError
    return (minutes * 60 + seconds) * 1000

def progress_bar(percent: int) -> str:
    blocks = percent // 10
    return f"[{'█' * blocks}{'░' * (10 - blocks)}] {percent}%"

async def animate(message, text, start_percent, end_percent):
    for percent in range(start_percent, end_percent + 1, 2):
        emoji = SPINNER[percent % len(SPINNER)]
        await message.edit_text(
            f"{text} {emoji}\n{progress_bar(percent)}"
        )
        await asyncio.sleep(0.15)

# ------------------ START ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *Audio Trim Bot*\n\n"
        "Send any audio file.\n"
        "Use time format `mm:ss`\n\n"
        "Example: `01:30`",
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

    # STEP 1: Show static downloading message
    progress_msg = await msg.reply_text(
        "📥 Downloading audio...\n" + progress_bar(5)
    )

    # STEP 2: Download audio (NO animation here)
    file = await audio.get_file()
    input_path = f"{msg.from_user.id}_input"
    await file.download_to_drive(input_path)

    user_audio[msg.from_user.id] = input_path
    user_filename[msg.from_user.id] = filename

    # STEP 3: Animate AFTER download completes
    await animate(progress_msg, "📥 Audio received", 20, 30)

    await msg.reply_text(
        "⏱️ Enter *START time* in `mm:ss`\nExample: `01:30`",
        parse_mode="Markdown"
    )
    return START_TIME

# ------------------ START TIME ------------------

async def get_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["start_ms"] = mmss_to_milliseconds(update.message.text)
    except Exception:
        await update.message.reply_text(
            "❌ Invalid format. Use `mm:ss`",
            parse_mode="Markdown"
        )
        return START_TIME

    await update.message.reply_text(
        "⏱️ Enter *END time* in `mm:ss`",
        parse_mode="Markdown"
    )
    return END_TIME

# ------------------ END TIME & TRIM ------------------

async def get_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    try:
        end_ms = mmss_to_milliseconds(update.message.text)
        start_ms = context.user_data["start_ms"]
        if end_ms <= start_ms:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ End time must be greater than start time.")
        return END_TIME

    progress_msg = await update.message.reply_text(
        "✂️ Processing audio...\n" + progress_bar(40)
    )

    await animate(progress_msg, "✂️ Trimming audio", 40, 60)

    input_audio = user_audio[user_id]
    original_name = user_filename[user_id]
    output_file = f"trimmed_{original_name}"

    try:
        audio = AudioSegment.from_file(input_audio)
        trimmed_audio = audio[start_ms:end_ms]

        await animate(progress_msg, "💾 Exporting audio", 70, 80)
        trimmed_audio.export(output_file, format="mp3")

        await animate(progress_msg, "📤 Uploading audio", 90, 95)

        await update.message.reply_audio(
            audio=open(output_file, "rb"),
            filename=original_name,
            caption="✅ Trimmed audio ready"
        )

        await progress_msg.edit_text("🎉 Done!\n" + progress_bar(100))

    except Exception as e:
        await progress_msg.edit_text("❌ Error while processing audio.")
        print(e)

    finally:
        if os.path.exists(input_audio):
            os.remove(input_audio)
        if os.path.exists(output_file):
            os.remove(output_file)

    return ConversationHandler.END

# ------------------ MAIN ------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
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
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
