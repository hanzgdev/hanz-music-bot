import asyncio
import logging
import os
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import yt_dlp

# -------------------------------
# CONFIG
# -------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Set this in Railway Variables
YOUTUBE_COOKIES_VAR = "YOUTUBE_COOKIES"  # env var name you used

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router
router = Router()

# States (optional - can remove if you don't need multi-step)
class DownloadForm(StatesGroup):
    waiting_for_query = State()

# -------------------------------
# YT-DLP OPTIONS
# -------------------------------
def get_ydl_opts(cookie_path: str | None = None) -> dict:
    opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',  # or 128, 320 etc.
        }],
        'outtmpl': '%(title)s.%(ext)s',  # temp file name
        'quiet': True,
        'no_warnings': True,
        'continuedl': True,
        'retries': 10,
        'fragment_retries': 10,
        # Optional anti-detection
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
    }
    
    if cookie_path:
        opts['cookiefile'] = cookie_path
    
    return opts

# -------------------------------
# HELPERS
# -------------------------------
async def download_audio(query: str) -> tuple[Path | None, str | None]:
    ydl_opts = get_ydl_opts()
    
    # Load cookies from env if available
    cookies_content = os.environ.get(YOUTUBE_COOKIES_VAR)
    cookie_path = None
    
    if cookies_content:
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
                temp_file.write(cookies_content)
                cookie_path = temp_file.name
            ydl_opts['cookiefile'] = cookie_path
            logger.info(f"Using cookies from env var → {cookie_path}")
        except Exception as e:
            logger.error(f"Failed to write cookies: {e}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search first (ytsearch: returns best match)
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' not in info or not info['entries']:
                return None, "No results found for this query."
            
            video_info = info['entries'][0]
            video_url = video_info['url']
            title = video_info.get('title', 'Unknown Title')
            
            # Now download the best audio
            logger.info(f"Downloading: {title}")
            ydl.download([video_url])
            
            # Find the downloaded file (yt-dlp renames to title.mp3 usually)
            possible_files = list(Path(".").glob(f"{title}*.mp3")) + list(Path(".").glob("*.mp3"))
            if not possible_files:
                return None, "Downloaded but could not find the mp3 file."
            
            file_path = possible_files[0]
            return file_path, None
    
    except Exception as e:
        logger.error(f"yt-dlp error: {str(e)}", exc_info=True)
        return None, f"Download failed: {str(e)}"
    
    finally:
        # Clean up temp cookie file
        if cookie_path and os.path.exists(cookie_path):
            try:
                os.unlink(cookie_path)
            except:
                pass

# -------------------------------
# HANDLERS
# -------------------------------
@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🎵 **Hanz Music Downloader**\n\n"
        "Just send me a song title and I'll find & download it for you!\n\n"
        "Example: Blinding Lights\n"
        "Or: never gonna give you up"
    )

@router.message(\~Command())  # any non-command text message
async def search_and_download(message: Message):
    query = message.text.strip()
    if not query:
        await message.answer("Please send a song title!")
        return
    
    loading_msg = await message.answer("🔍 Searching and downloading... Please wait (can take 10–60 seconds)...")
    
    file_path, error = await download_audio(query)
    
    if error:
        await loading_msg.edit_text(
            f"❌ Download failed: ERROR:\n{error}\n\nTry another track!"
        )
        return
    
    try:
        # Send audio
        audio_file = FSInputFile(file_path)
        await message.answer_audio(
            audio=audio_file,
            title=file_path.stem,
            caption=f"🎧 {file_path.stem}\nDownloaded via HanZ Music Bot"
        )
        
        await loading_msg.delete()  # remove "please wait" message
    except Exception as e:
        await loading_msg.edit_text(f"Failed to send audio: {str(e)}")
    finally:
        # Clean up downloaded file
        if file_path and file_path.exists():
            try:
                os.unlink(file_path)
            except:
                pass

# -------------------------------
# MAIN
# -------------------------------
async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    logger.info("Bot is starting...")
    await dp.start_polling(bot, allowed_updates=types.default_allowed_updates)

if __name__ == "__main__":
    asyncio.run(main())
