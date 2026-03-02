import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get('TOKEN')

search_results = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *Hanz Music Downloader*\n\n"
        "Just send me a song title and I'll find it for you!\n\n"
        "Example: `never gonna give you up`",
        parse_mode='Markdown'
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Please send a song name or title!")
        return

    user_id = update.effective_user.id
    msg = await update.message.reply_text(f"🔍 Searching for *{query}*...", parse_mode='Markdown')

    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Changed to YouTube search — much more reliable for full songs
            results = ydl.extract_info(f"ytsearch5:{query}", download=False)
            entries = results.get('entries', [])

        if not entries:
            await msg.edit_text("❌ No results found. Try a different song!")
            return

        # Keep only first 5 results
        search_results[user_id] = entries[:5]

        keyboard = []
        text = "🎵 *Top 5 Results:*\n\n"
        for i, entry in enumerate(entries[:5]):
            title = entry.get('title', 'Unknown title')
            duration = entry.get('duration') or 0
            mins = int(duration // 60)
            secs = int(duration % 60)
            duration_str = f"{mins}:{secs:02d}" if duration else "??:??"
            text += f"`{i+1}.` {title} ({duration_str})\n"
            # Shorten button text if title is very long
            btn_text = f"{i+1}. {title[:38]}" + ("..." if len(title) > 38 else "")
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"dl_{user_id}_{i}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        print(f"SEARCH ERROR: {type(e).__name__}: {e}")
        await msg.edit_text("❌ Something went wrong while searching. Try again!")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, user_id_str, index_str = query.data.split('_')
        user_id = int(user_id_str)
        index = int(index_str)
    except:
        await query.edit_message_text("❌ Invalid selection. Try searching again.")
        return

    if user_id not in search_results or index >= len(search_results[user_id]):
        await query.edit_message_text("❌ Session expired or invalid choice. Please search again!")
        return

    entry = search_results[user_id][index]
    url = entry.get('url') or entry.get('webpage_url') or entry.get('id')
    title = entry.get('title', 'track').replace('/', '_').replace('\\', '_')  # safe filename

    await query.edit_message_text(f"⬇️ Downloading *{title}*...", parse_mode='Markdown')

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'/tmp/{user_id}_%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Try to get the exact output filename
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith('.mp3'):
                filepath = filepath.rsplit('.', 1)[0] + '.mp3'

        if not os.path.exists(filepath):
            raise FileNotFoundError("Audio file was not created")

        await query.edit_message_text(f"📤 Uploading *{title}*...", parse_mode='Markdown')

        with open(filepath, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio_file,
                title=title,
                performer="Hanz Music Bot",
                duration=entry.get('duration'),
                thumbnail=None,  # optional: can add later if you want
            )

        # Cleanup
        try:
            os.remove(filepath)
        except:
            pass

        await query.delete_message()

    except Exception as e:
        print(f"DOWNLOAD ERROR for '{title}': {type(e).__name__}: {str(e)}")
        await query.edit_message_text(
            f"❌ Download failed: {str(e)[:120]}\nTry another track!",
            parse_mode=None
        )

def main():
    if not TOKEN:
        print("ERROR: TOKEN environment variable is not set!")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(download, pattern=r'^dl_'))

    print("Bot is starting...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()
