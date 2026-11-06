import os
import asyncio
import logging
import json
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL", "0"))

DEFAULT_US_CHATS = [
    # B2B, Экспертиза и Бизнес-партнерство
    "MiamiBusinessChat", "ny_business_chat", "california_business", 
    "usabusinesschat", "startups_usa", "relocate_usa_biz",
    # Тракисты, Логистика и Диспетчеры
    "usatc", "truckers_usa", "disp_usa", "auto_trans_usa",
    # Недвижимость и Аренда (Депозиты / Лендлорды)
    "ny_rent_apartments", "miami_rent_usa", "california_rent_us",
    # Крупные живые хабы США
    "russian_in_usa", "Miami_Chat_US", "NY_Chat_US", "LA_Chat_US"
]

RAW_ALLOWED = os.getenv("ALLOWED_CHATS", "")
if RAW_ALLOWED.strip():
    ALLOWED_CHATS = [c.strip() for c in RAW_ALLOWED.split(",") if c.strip()]
else:
    ALLOWED_CHATS = DEFAULT_US_CHATS

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

seen_messages = set()

app = Flask(__name__)

@app.route("/")
def index():
    return "Radar Bot Active", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TARGET_TRIGGERS = [
    'zelle', 'wire', 'chase', 'bank of america', 'boa', 'wells fargo', 'td bank',
    'заблокировали счет', 'счет закрыли', 'заморозили', 'fraud department', 'holding',
    'security deposit', 'депозит', 'лендлорд', 'eviction', 'выселение', 'lease', 'удержали',
    'предоплату', 'подрядчик', 'contractor', 'накосячил', 'не возвращает', 'bounced check',
    'убыток', 'страховка', 'claim', 'чарджбэк', 'chargeback', 'кинул', 'factoring',
    'партнер', 'партнерство', 'инвестор', 'инвестиции', 'ищу эксперта', 'нужен специалист',
    'открыть бизнес', 'запуск в сша', 'соинвестор', 'b2b', 'стратегия', 'масштабирование'
]

def passes_strict_filter(text: str) -> bool:
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in TARGET_TRIGGERS)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    try:
        if event.is_private:
            return

        chat = await event.get_chat()
        chat_id = chat.id
        chat_username = getattr(chat, 'username', None)

        is_allowed = False
        for allowed in ALLOWED_CHATS:
            clean_allowed = str(allowed).lower().replace('@', '')
            if str(allowed) == str(chat_id) or (chat_username and clean_allowed == chat_username.lower()):
                is_allowed = True
                break
        
        if not is_allowed:
            return

        message_text = event.raw_text
        if not message_text or len(message_text.strip()) < 20:
            return

        if not passes_strict_filter(message_text):
            return

        msg_hash = hash(message_text[:300])
        if msg_hash in seen_messages:
            return
        seen_messages.add(msg_hash)
        if len(seen_messages) > 3000:
            seen_messages.pop()

        prompt = f"""
Ты — эксперт-аналитик проблемных ситуаций и B2B-запросов в США.
Проанализируй текст сообщения из чата. Твоя задача — определить, описывает ли человек конкретную БЕДУ/ПРОБЛЕМУ (зависшие деньги, блок счета, спор по депозиту, недобросовестный подрядчик, потеря груза/страховка) ИЛИ ищет партнера/местную экспертизу для бизнеса.

СТРОГО ИГНОРИРУЙ:
- Вакансии, поиск сотрудников на зарплату, предложения бытовой работы.
- Прямую рекламу услуг, продавцов, риелторов, автодилеров.
- Бытовую купли-продажу (мебель, авто, вещи).
- Общий флуд и вопросы "где купить / как доехать".

Если найдена реальная проблема или бизнес-запрос, верни JSON (без markdown):
{{
  "is_relevant": true,
  "category": "Тип (Депозит / Блок счета / Подрядчик / Тракеры / B2B-Партнерство / Экспертиза)",
  "problem_summary": "Суть запроса или проблемы (1-2 предложения).",
  "diagnosis_pitch": "Короткий спокойный диагноз или профессиональная оценка ситуации без хвастовства, без юридических советов и без рекламных фраз ('я помогу/обращайтесь'). Дай оценку сути и логичный первый шаг для разбора."
}}

Если не подходит или спам:
{{ "is_relevant": false }}

Текст сообщения:
""" + message_text

        response = ai_model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
        )

        try:
            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result = json.loads(result_text.strip())
        except Exception:
            return

        if not result.get("is_relevant", False):
            return

        if chat_username:
            msg_link = f"https://t.me/{chat_username}/{event.id}"
        else:
            clean_id = str(chat_id).replace("-100", "")
            msg_link = f"https://t.me/c/{clean_id}/{event.id}"

        card = (
            f"🎯 **ОБНАРУЖЕНА ЦЕЛЬ**\n\n"
            f"📌 **Категория:** {result.get('category')}\n"
            f"📍 **Чат:** {chat.title}\n\n"
            f"📝 **Суть ситуации:**\n{result.get('problem_summary')}\n\n"
            f"💡 **Диагноз / Ответ для связи:**\n"
            f"`{result.get('diagnosis_pitch')}`\n\n"
            f"🔗 [Перейти к сообщению]({msg_link})"
        )

        await client.send_message(TARGET_CHANNEL, card, link_preview=False)

    except errors.FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logging.error(f"Ошибка обработки: {e}")

async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    while True:
        try:
            await client.start()
            await client.run_until_disconnected()
        except Exception as e:
            logging.error(f"Переподключение через 10 сек: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
