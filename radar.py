import os
import re
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.custom import Button
import google.generativeai as genai

# --- 1. НАСТРОЙКИ И КЛЮЧИ ---
API_ID = 34960188
API_HASH = "d13bcdd634dab76cb5efddd1c8dba32b"
BOT_TOKEN = "9032033160:AAElOsq3IXQMmtGRz_CMSEERCX-N9ck06O4"
GEMINI_KEY = "AQ.Ab8RN6Kf3mc7qnAqbb-mHs6xKMnEdgOZbYzpNmwggj_vmCEmiA"

# Инициализация Gemini
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

# Создаем клиентов Telegram
user_client = TelegramClient("user_session", API_ID, API_HASH)
bot_client = TelegramClient("bot_session", API_ID, API_HASH)

# Память против повторов (хранит ID обработанных сообщений)
PROCESSED_MSGS = set()

# --- 2. ГРУБЫЙ ФИЛЬТР (Ключевые связки) ---
KEYWORDS = [
    # RU
    r"кинул", r"депозит", r"не платит", r"адвокат", r"суд", r"контракт", r"договор",
    r"спор", r"долг", r"переводчик", r"лицензия", r"подрядчик", r"билдинг", r"смета",
    r"выбить деньги", r"проблема с", r"help", r"помогите",
    # EN
    r"scam", r"deposit", r"contractor", r"sue", r"lawyer", r"dispute", r"unpaid",
    # HE
    r"חוזה", r"עורך דין", r"קבלן", r"כסף"
]

# Исключения (отсекаем явную барахолку и аренду)
EXCLUDE_WORDS = [r"продам", r"сдам", r"куплю", r"диван", r"машина", r"работа", r"вакансия"]

def Quick_filter(text: str) -> bool:
    text_lower = text.lower()
    if any(re.search(word, text_lower) for word in EXCLUDE_WORDS):
        return False
    return any(re.search(word, text_lower) for word in KEYWORDS)

# --- 3. УМНЫЙ ФИЛЬТР И ЧЕРНОВИК (GEMINI) ---
async def process_with_ai(post_text: str):
    prompt = f"""
Ты — аналитик и бизнес-консультант в США.
Проанализируй пост из Telegram-чата иммигрантов:
"{post_text}"

Ответь строго в формате JSON:
{{
  "is_target": true/false (true ТОЛЬКО если у человека реальная коммерческая, договорная, финансовая или административная беда/спор в США, где нужен опытный Problem Solver. Бытовые вопросы, барахолка и поиск работы — false),
  "summary": "Краткая суть проблемы на русском (1 предложение)",
  "urgency": "Высокая / Средняя / Низкая",
  "draft": "Текст первого ответа автору поста на его языке. Тон: спокойный эксперт, никакой рекламы и юр. советов. Сразу диагноз боли и предложение разобрать ситуацию."
}}
"""
    try:
        response = ai_model.generate_content(prompt)
        import json
        clean_json = re.sub(r'```json\s*|\s*```', '', response.text).strip()
        return json.loads(clean_json)
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        return None

# --- 4. СЛУШАТЕЛЬ ЧАТОВ (USERBOT) ---
@user_client.on(events.NewMessage)
async def handler(event):
    if not event.is_group and not event.is_channel:
        return
    
    msg_id = f"{event.chat_id}_{event.id}"
    if msg_id in PROCESSED_MSGS:
        return
    
    text = event.message.message
    if not text or len(text) < 20:
        return

    # Слои 1 и 2: Чтение и грубый фильтр
    if not quick_filter(text):
        return
    
    PROCESSED_MSGS.add(msg_id)

    # Слой 3 и 4: Умный фильтр и генерация черновика
    ai_result = await process_with_ai(text)
    if not ai_result or not ai_result.get("is_target"):
        return

    # Слой 5: Формирование алерта в бот
    chat = await event.get_chat()
    chat_title = getattr(chat, 'title', 'Чат')
    msg_link = f"https://t.me/c/{str(event.chat_id).replace('-100', '')}/{event.id}"

    alert_text = (
        f"🚨 **НАЙДЕН ЛИД | {ai_result['urgency']} срочность**\n"
        f"📍 **Чат:** {chat_title}\n\n"
        f"📌 **Суть:** {ai_result['summary']}\n\n"
        f"📝 **Предлагаемый черновик:**\n`{ai_result['draft']}`"
    )

    buttons = [
        [Button.url("🔗 Открыть пост", msg_link)],
        [Button.inline("✅ Ответил", data="status_done"), Button.inline("❌ Мимо", data="status_skip")]
    ]

    # Отправляем алерт тебе через бота (укажи свой Telegram ID)
    # Замени 123456789 на свой личный Telegram ID (или бот пришлет в ответ на /start)
    await bot_client.send_message(event.sender_id, alert_text, buttons=buttons)

# --- 5. ЗАПУСК СИСТЕМЫ ---
async def main():
    await bot_client.start(bot_token=BOT_TOKEN)
    await user_client.start()
    print("Радар успешно запущен и слушаeт чаты...")
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
