import os
import asyncio
from telethon import TelegramClient, events
import google.generativeai as genai
from flask import Flask
from threading import Thread

# Инициализация Flask (главный веб-сервер для Render)
app = Flask(__name__)

@app.route('/')
def home():
    return "Radar is active and running!"

def run_telegram_bot():
    api_id = 34960188
    api_hash = 'd13bcdd634dab76cb5efddd1c8dba32b'
    gemini_api_key = 'AQ...EmiA' # Твой ключ

    genai.configure(api_key=gemini_api_key)
    ai_model = genai.GenerativeModel("gemini-1.5-flash")

    client = TelegramClient('radar_session', api_id, api_hash)

    @client.on(events.NewMessage)
    async def handle_new_message(event):
        print(f"Новое сообщение: {event.message.message}")

    async def main():
        print("Telegram-радар запущен...")
        await client.run_until_disconnected()

    with client:
        client.loop.run_until_complete(main())

if __name__ == '__main__':
    # Запускаем Telegram-клиент в отдельном потоке в фоне
    bot_thread = Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Веб-сервер работает в основном потоке и держит порт для Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
