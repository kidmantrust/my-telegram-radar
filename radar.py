import os
import asyncio
from telethon import TelegramClient, events
import google.generativeai as genai
import threading
from flask import Flask

# --- МИНИ-СЕРВЕР ДЛЯ БЕСПЛАТНОГО ТАРИФА RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Radar is active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
# -----------------------------------------------

api_id = 34960188
api_hash = 'd13bcdd634dab76cb5efddd1c8dba32b'
gemini_api_key = 'AQ...EmiA' # Твой полный ключ

genai.configure(api_key=gemini_api_key)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

client = TelegramClient('radar_session', api_id, api_hash)

@client.on(events.NewMessage(chats=[-100XXXXXXXXXX]))
async def handle_new_message(event):
    message_text = event.message.message
    print(f"Новое сообщение: {message_text}")

async def main():
    print("Радар запущен и слушает чаты...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
