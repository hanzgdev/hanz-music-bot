import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get('TOKEN')

search_results = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *Hanz Music Downloader*\n\nJust send me a song title and I'll find it for you!\n\nExample: `never gonna give you up`",
        parse_mode='Markdown'
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    user_id = update.message.from_user.id

    msg = await update.message.reply_text(f"🔍 Searching for *{query}*...", parse_mode='Markdown')

    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'default_search': 'scsearch5',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(f"scsearch5:{query}", download=False)
            entries = results.get('entries', [])

        if not entries:
            await msg.edit_text("❌ No results found. Try a different search!")
            return

        search_results[user_id] = entries[:5]

        keyboard = []
        text = "🎵 *Search Results:*\n\n"
        for i, entry in enumerate(entries[:5]):
            title = entry.get('title', 'Unknown')
            duration = entry.get('duration', 0)
            mins = int(duration // 60) if duration else 0
            secs = int(duration % 60) if duration else 0
            text += f"`{i+1}.` {title} ({mins}:{secs:02d})\n"
            keyboard.append([InlineKeyboardButton(f"{i+1}. {title[:40]}", callback_data=f"dl_{user_id}_{i}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        await msg.edit_text(f"❌ Something went wrong. Try again!")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    user_id = int(data[1])
    index = int(data[2])

    if user_id not in search_results:
        await query.edit_message_text("❌ Session expired. Search again!")
        return

    entry = search_results[user_id][index]
    url = entry.get('url') or entry.get('webpage_url')
    title = entry.get('title', 'track')

    await query.edit_message_text(f"⬇️ Downloading *{title}*...", parse_mode='Markdown')

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'/tmp/{user_id}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        filepath = f'/tmp/{user_id}.mp3'

        await query.edit_message_text(f"📤 Sending *{title}*...", parse_mode='Markdown')

        with open(filepath, 'rb') as audio:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio,
                title=title,
                performer='Hanz Music Bot'
            )

        os.remove(filepath)
        await query.delete_message()

    except Exception as e:
        await query.edit_message_text("❌ Download failed. Try another track!")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(download, pattern=r'^dl_'))
    app.run_polling()

if __name__ == '__main__':
    main()
