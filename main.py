import os
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters
from pydub import AudioSegment
import re

# Your Telegram bot token
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Send me a YouTube link and I'll process the audio for you!")

def clean_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def download_and_process_video(url: str, chat_id: int, update: Update) -> tuple:
    # Create a download directory if not exists
    download_dir = f"downloads/{chat_id}"
    os.makedirs(download_dir, exist_ok=True)

    # Download video using yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{download_dir}/%(id)s.%(ext)s',
        'writethumbnail': True,
        'embedthumbnail': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        title= info_dict.get('title', None)
        video_id = info_dict.get('id', None)

        #clean_video_title = clean_filename(video_title)
        mp3_path = os.path.join(download_dir, f"{video_id}.mp3")
        thumbnail_path = os.path.join(download_dir, f"{video_id}.webp")

        #old_mp3_path = os.path.join(download_dir, f"{video_id}.mp3")
        #os.rename(old_mp3_path, mp3_path)

    return mp3_path, title, thumbnail_path

def split_audio(file_path: str, part_size_minutes: int = 50) -> list:
    audio = AudioSegment.from_mp3(file_path)

    # Convert chunk length to milliseconds
    chunk_length_ms = part_size_minutes * 60 * 1000

    # Calculate the number of chunks
    total_length_ms = len(audio)

    audio_parts = []
    for i in range(0, total_length_ms, chunk_length_ms):
        part = audio[i:i + chunk_length_ms]
        part_name = f"{file_path[:-4]}_{i // chunk_length_ms + 1:02d}.mp3"
        part.export(part_name, format="mp3")
        audio_parts.append(part_name)

    # sort parts in reverse order
    audio_parts.sort(key=lambda x: int(x.split('_')[-1][:-4]), reverse=True)
    
    return audio_parts

async def handle_message(update: Update, context: CallbackContext) -> None:
    url = update.message.text
    chat_id = update.message.chat_id

    if "youtube.com" in url or "youtu.be" in url:
        try:
            await update.message.reply_text("Downloading video...")
            mp3_path, title, thumbnail_path = download_and_process_video(url, chat_id, update)
            await update.message.reply_text("Extracting and splitting audio...")

            audio_parts = split_audio(mp3_path)
            for part in audio_parts:
                with open(part, 'rb') as audio_file:
                    with open(thumbnail_path, 'rb') as thumbnail:
                        await update.message.reply_audio(audio_file, caption=title, thumbnail=thumbnail)
            
            #cleanup
            for part in audio_parts:
                os.remove(part)
            os.remove(mp3_path)
            os.remove(thumbnail_path)
            
            await update.message.reply_text("All parts sent!")

        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")

    else:
        await update.message.reply_text("Please send a valid YouTube link.")

def main() -> None:
    # create application
    application = Application.builder().token(TOKEN).build()

    # add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # start the bot
    application.run_polling()

if __name__ == '__main__':
    main()