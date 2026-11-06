import os
import asyncio
import logging
import json
import requests
from flask import Flask
from threading import Thread
import google.generativeai as genai

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ==========================================
# ФУНДАМЕНТАЛЬНЫЕ НАСТРОЙКИ (Всё на месте)
# ==========================================
TELEGRAM_BOT_TOKEN = "9223838955:AAEd_wxYQfmQzpB6ZmLx7oJ3YqMCyiTkJmw"
TARGET_CHANNEL = 8768875698  # Твой личный ID в Telegram для карточек
GEMINI_API_KEY = "AQ.Ab8RN6LXL64AGRJpmlB6zqKUGK3u5l2FXKGIP5pg5W0aBquLqw"
# ==========================================

# Инициализация Gemini
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

seen_messages = set()

# Flask сервер для поддержания активности на Render
app = Flask(__name__)

@app.route("/")
def index():
    return "Radar Bot Active", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Функция отправки карточки в ЛС через Bot API
def send_to_channel(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHANNEL,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")

# Целевые триггеры для фильтрации мусора
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

def process_message(chat_title, chat_username, message_text, message_id):
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

    try:
        response = ai_model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
        )
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
        msg_link = f"https://t.me/{chat_username}/{message_id}"
    else:
        msg_link = f"https://t.me"

    card = (
        f"🎯 **ОБНАРУЖЕНА ЦЕЛЬ**\n\n"
        f"📌 **Категория:** {result.get('category')}\n"
        f"📍 **Чат:** {chat_title}\n\n"
        f"📝 **Суть ситуации:**\n{result.get('problem_summary')}\n\n"
        f"💡 **Диагноз / Ответ для связи:**\n"
        f"`{result.get('diagnosis_pitch')}`\n\n"
        f"🔗 [Перейти к сообщению]({msg_link})"
    )

    send_to_channel(card)

# Главный цикл опроса Telegram Bot API
def run_telegram_bot():
    offset = 0
    logging.info("🚀 Бот-радар запущен и мониторит сеть...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()
            
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    
                    message = update.get("message") or update.get("channel_post") or update.get("edited_message")
                    if message:
                        chat = message.get("chat", {})
                        chat_type = chat.get("type", "")
                        
                        if chat_type in ["group", "supergroup", "channel"]:
                            chat_title = chat.get("title", "Чат")
                            chat_username = chat.get("username")
                            text = message.get("text") or message.get("caption", "")
                            msg_id = message.get("message_id")
                            
                            process_message(chat_title, chat_username, text, msg_id)
        except Exception as e:
            logging.error(f"Ошибка в цикле бота: {e}")
            import time
            time.sleep(5)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    run_telegram_bot()
