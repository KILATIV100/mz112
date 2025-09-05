import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, Any
import aiofiles
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8080)))
    await site.start()
    print("Web server started on port", os.getenv('PORT', 8080))

async def main():
    """Основна функція запуску бота"""
    init_database()
    logger.info("База даних ініціалізована")
    
    # Запуск веб-сервера для health check
    await start_web_server()
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

load_dotenv()

# Токен бота з змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не встановлено в змінних середовища")
    
    Build command: pip install -r requirements.txt
Run command: python bot.py

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile, Document, PhotoSize
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (замініть на свій)
BOT_TOKEN = "8395733479:AAF4mxEpGEIcym5NNq2krPLOHBLfpcRveDc"

# Директорія для збереження файлів
FILES_DIR = "files"
os.makedirs(FILES_DIR, exist_ok=True)

# Створення та ініціалізація бази даних
def init_database():
    """Ініціалізація бази даних SQLite"""
    conn = sqlite3.connect('correspondence.db')
    cursor = conn.cursor()
    
    # Таблиця для вхідної кореспонденції
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incoming (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number TEXT UNIQUE,
            from_whom TEXT,
            subject TEXT,
            content TEXT,
            received_date TEXT,
            notes TEXT,
            file_path TEXT
        )
    ''')
    
    # Таблиця для вихідної кореспонденції
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outgoing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number TEXT UNIQUE,
            to_whom TEXT,
            subject TEXT,
            content TEXT,
            sent_date TEXT,
            notes TEXT,
            file_path TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Стани для FSM
class IncomingStates(StatesGroup):
    from_whom = State()
    subject = State()
    content = State()
    received_date = State()
    notes = State()
    confirm = State()
    file_attachment = State()

class OutgoingStates(StatesGroup):
    to_whom = State()
    subject = State()
    content = State()
    sent_date = State()
    notes = State()
    confirm = State()
    file_attachment = State()

class SearchState(StatesGroup):
    waiting_keyword = State()

# Ініціалізація бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Функції для роботи з базою даних
def generate_doc_number(doc_type: str) -> str:
    """Генерація унікального номера документа"""
    conn = sqlite3.connect('correspondence.db')
    cursor = conn.cursor()
    
    table_name = doc_type.lower()
    cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    count = cursor.fetchone()[0]
    conn.close()
    
    prefix = "IN" if doc_type.lower() == "incoming" else "OUT"
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{count + 1:03d}"

def save_document(doc_type: str, data: Dict[str, Any]) -> str:
    """Збереження документа в базу даних"""
    conn = sqlite3.connect('correspondence.db')
    cursor = conn.cursor()
    
    doc_number = generate_doc_number(doc_type)
    table_name = doc_type.lower()
    
    if doc_type.lower() == "incoming":
        cursor.execute(f'''
            INSERT INTO {table_name} 
            (doc_number, from_whom, subject, content, received_date, notes, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (doc_number, data['from_whom'], data['subject'], data['content'], 
              data['received_date'], data['notes'], ''))
    else:  # outgoing
        cursor.execute(f'''
            INSERT INTO {table_name} 
            (doc_number, to_whom, subject, content, sent_date, notes, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (doc_number, data['to_whom'], data['subject'], data['content'], 
              data['sent_date'], data['notes'], ''))
    
    conn.commit()
    conn.close()
    return doc_number

def search_documents(keyword: str):
    """Пошук документів за ключовим словом"""
    conn = sqlite3.connect('correspondence.db')
    cursor = conn.cursor()
    
    # Пошук у вхідній кореспонденції
    cursor.execute('''
        SELECT 'incoming' as type, doc_number, from_whom as org, subject, content, received_date as date, notes, file_path
        FROM incoming 
        WHERE from_whom LIKE ? OR subject LIKE ? OR content LIKE ? OR notes LIKE ?
    ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
    
    incoming_results = cursor.fetchall()
    
    # Пошук у вихідній кореспонденції
    cursor.execute('''
        SELECT 'outgoing' as type, doc_number, to_whom as org, subject, content, sent_date as date, notes, file_path
        FROM outgoing 
        WHERE to_whom LIKE ? OR subject LIKE ? OR content LIKE ? OR notes LIKE ?
    ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
    
    outgoing_results = cursor.fetchall()
    
    conn.close()
    return incoming_results + outgoing_results

def update_file_path(doc_number: str, file_path: str):
    """Оновлення шляху до файлу в базі даних"""
    conn = sqlite3.connect('correspondence.db')
    cursor = conn.cursor()
    
    # Спробуємо оновити у вхідній кореспонденції
    cursor.execute('UPDATE incoming SET file_path = ? WHERE doc_number = ?', (file_path, doc_number))
    if cursor.rowcount == 0:
        # Якщо не знайдено у вхідній, оновлюємо у вихідній
        cursor.execute('UPDATE outgoing SET file_path = ? WHERE doc_number = ?', (file_path, doc_number))
    
    conn.commit()
    conn.close()

# Клавіатури
def main_menu_keyboard():
    """Головне меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Вхідна кореспонденція"), KeyboardButton(text="📤 Вихідна кореспонденція")],
            [KeyboardButton(text="🔍 Пошук"), KeyboardButton(text="ℹ️ Довідка")]
        ],
        resize_keyboard=True
    )
    return keyboard

def confirmation_keyboard():
    """Клавіатура підтвердження"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="confirm_no")]
    ])
    return keyboard

def file_attachment_keyboard():
    """Клавіатура для прикріплення файлу"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Прикріпити файл", callback_data="attach_file")],
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
    ])
    return keyboard

# Обробники команд
@dp.message(CommandStart())
async def start_handler(message: Message):
    """Обробник команди /start"""
    welcome_text = (
        "🤖 Вітаю! Я бот для обліку кореспонденції.\n\n"
        "Використовуйте кнопки нижче для навігації:"
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())

@dp.message(F.text == "ℹ️ Довідка")
async def help_handler(message: Message):
    """Обробник довідки"""
    help_text = (
        "📋 **Інструкція з використання бота**\n\n"
        "**📥 Вхідна кореспонденція** - реєстрація отриманих документів\n"
        "**📤 Вихідна кореспонденція** - реєстрація відправлених документів\n"
        "**🔍 Пошук** - пошук документів за ключовими словами\n"
        "**ℹ️ Довідка** - ця інструкція\n\n"
        "При реєстрації документів ви вводите дані поетапно. "
        "Після реєстрації можна прикріпити файл до документа.\n\n"
        "Пошук здійснюється за всіма полями: організацією, темою, змістом та примітками."
    )
    await message.answer(help_text, parse_mode="Markdown")

# Обробники вхідної кореспонденції
@dp.message(F.text == "📥 Вхідна кореспонденція")
async def incoming_start(message: Message, state: FSMContext):
    """Початок реєстрації вхідної кореспонденції"""
    await message.answer("📄 Будь ласка, вкажіть, від кого отримано документ:")
    await state.set_state(IncomingStates.from_whom)

@dp.message(IncomingStates.from_whom)
async def incoming_from_whom(message: Message, state: FSMContext):
    await state.update_data(from_whom=message.text)
    await message.answer("📝 Вкажіть об'єкт документа:")
    await state.set_state(IncomingStates.subject)

@dp.message(IncomingStates.subject)
async def incoming_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await message.answer("📋 Вкажіть зміст документа (короткий опис):")
    await state.set_state(IncomingStates.content)

@dp.message(IncomingStates.content)
async def incoming_content(message: Message, state: FSMContext):
    await state.update_data(content=message.text)
    await message.answer("📅 Вкажіть дату отримання (наприклад, 2024-01-15):")
    await state.set_state(IncomingStates.received_date)

@dp.message(IncomingStates.received_date)
async def incoming_date(message: Message, state: FSMContext):
    await state.update_data(received_date=message.text)
    await message.answer("📌 Додайте примітки (або напишіть 'немає', якщо немає приміток):")
    await state.set_state(IncomingStates.notes)

@dp.message(IncomingStates.notes)
async def incoming_notes(message: Message, state: FSMContext):
    notes = message.text if message.text.lower() != 'немає' else ''
    await state.update_data(notes=notes)
    
    data = await state.get_data()
    
    # Відображення зібраних даних
    summary = (
        "📋 **Підсумок введених даних:**\n\n"
        f"**Від кого:** {data['from_whom']}\n"
        f"**Об'єкт:** {data['subject']}\n"
        f"**Зміст:** {data['content']}\n"
        f"**Дата отримання:** {data['received_date']}\n"
        f"**Примітки:** {data['notes'] or 'Немає'}\n\n"
        "Чи хочете ви підтвердити введення?"
    )
    
    await message.answer(summary, reply_markup=confirmation_keyboard(), parse_mode="Markdown")
    await state.set_state(IncomingStates.confirm)

# Обробники вихідної кореспонденції
@dp.message(F.text == "📤 Вихідна кореспонденція")
async def outgoing_start(message: Message, state: FSMContext):
    """Початок реєстрації вихідної кореспонденції"""
    await message.answer("📄 Будь ласка, вкажіть, кому надіслано документ:")
    await state.set_state(OutgoingStates.to_whom)

@dp.message(OutgoingStates.to_whom)
async def outgoing_to_whom(message: Message, state: FSMContext):
    await state.update_data(to_whom=message.text)
    await message.answer("📝 Вкажіть об'єкт документа:")
    await state.set_state(OutgoingStates.subject)

@dp.message(OutgoingStates.subject)
async def outgoing_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await message.answer("📋 Вкажіть зміст документа (короткий опис):")
    await state.set_state(OutgoingStates.content)

@dp.message(OutgoingStates.content)
async def outgoing_content(message: Message, state: FSMContext):
    await state.update_data(content=message.text)
    await message.answer("📅 Вкажіть дату відправки (наприклад, 2024-01-15):")
    await state.set_state(OutgoingStates.sent_date)

@dp.message(OutgoingStates.sent_date)
async def outgoing_date(message: Message, state: FSMContext):
    await state.update_data(sent_date=message.text)
    await message.answer("📌 Додайте примітки (або напишіть 'немає', якщо немає приміток):")
    await state.set_state(OutgoingStates.notes)

@dp.message(OutgoingStates.notes)
async def outgoing_notes(message: Message, state: FSMContext):
    notes = message.text if message.text.lower() != 'немає' else ''
    await state.update_data(notes=notes)
    
    data = await state.get_data()
    
    # Відображення зібраних даних
    summary = (
        "📋 **Підсумок введених даних:**\n\n"
        f"**Кому:** {data['to_whom']}\n"
        f"**Об'єкт:** {data['subject']}\n"
        f"**Зміст:** {data['content']}\n"
        f"**Дата відправки:** {data['sent_date']}\n"
        f"**Примітки:** {data['notes'] or 'Немає'}\n\n"
        "Чи хочете ви підтвердити введення?"
    )
    
    await message.answer(summary, reply_markup=confirmation_keyboard(), parse_mode="Markdown")
    await state.set_state(OutgoingStates.confirm)

# Обробники підтвердження
@dp.callback_query(F.data == "confirm_yes")
async def confirm_document(callback: CallbackQuery, state: FSMContext):
    """Підтвердження збереження документа"""
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == IncomingStates.confirm.state:
        doc_number = save_document("incoming", data)
        doc_type = "вхідний"
    else:  # OutgoingStates.confirm
        doc_number = save_document("outgoing", data)
        doc_type = "вихідний"
    
    await state.update_data(doc_number=doc_number)
    
    await callback.message.edit_text(
        f"✅ {doc_type.capitalize()} документ зареєстровано!\n"
        f"📄 Номер документа: **{doc_number}**\n\n"
        "Бажаєте прикріпити файл?",
        reply_markup=file_attachment_keyboard(),
        parse_mode="Markdown"
    )
    
    if current_state == IncomingStates.confirm.state:
        await state.set_state(IncomingStates.file_attachment)
    else:
        await state.set_state(OutgoingStates.file_attachment)

@dp.callback_query(F.data == "confirm_no")
async def cancel_document(callback: CallbackQuery, state: FSMContext):
    """Скасування збереження документа"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Введення скасовано. Повертаюся в головне меню."
    )

@dp.callback_query(F.data == "attach_file")
async def request_file(callback: CallbackQuery, state: FSMContext):
    """Запит на надсилання файлу"""
    await callback.message.edit_text(
        "📎 Надішліть файл для прикріплення до документа.\n"
        "Підтримуються: PDF, DOCX, XLSX, зображення та інші типи файлів."
    )

@dp.callback_query(F.data == "main_menu")
async def go_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Повернення в головне меню"""
    await state.clear()
    await callback.message.edit_text("🏠 Повертаюся в головне меню.")

# Обробники файлів
@dp.message(F.document, IncomingStates.file_attachment)
@dp.message(F.document, OutgoingStates.file_attachment)
async def handle_document(message: Message, state: FSMContext):
    """Обробка документів"""
    await process_file(message, message.document, state)

@dp.message(F.photo, IncomingStates.file_attachment)
@dp.message(F.photo, OutgoingStates.file_attachment)
async def handle_photo(message: Message, state: FSMContext):
    """Обробка зображень"""
    # Беремо найбільше зображення
    photo = message.photo[-1]
    await process_file(message, photo, state)

async def process_file(message: Message, file_obj, state: FSMContext):
    """Обробка та збереження файлу"""
    data = await state.get_data()
    doc_number = data.get('doc_number')
    
    if not doc_number:
        await message.answer("❌ Помилка: номер документа не знайдено.")
        return
    
    try:
        # Отримання інформації про файл
        file_info = await bot.get_file(file_obj.file_id)
        
        # Визначення розширення файлу
        if hasattr(file_obj, 'file_name') and file_obj.file_name:
            file_name = file_obj.file_name
        else:
            # Для фото без імені
            file_name = f"photo_{file_obj.file_id}.jpg"
        
        # Створення унікального імені файлу
        file_extension = os.path.splitext(file_name)[1]
        unique_filename = f"{doc_number}{file_extension}"
        file_path = os.path.join(FILES_DIR, unique_filename)
        
        # Завантаження файлу
        await bot.download_file(file_info.file_path, file_path)
        
        # Оновлення інформації про файл в базі даних
        update_file_path(doc_number, file_path)
        
        await message.answer(
            f"✅ Файл успішно прикріплено до документа {doc_number}!\n"
            "🏠 Повертаюся в головне меню."
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Помилка при збереженні файлу: {e}")
        await message.answer("❌ Помилка при збереженні файлу. Спробуйте ще раз.")

# Обробник пошуку
@dp.message(F.text == "🔍 Пошук")
async def search_start(message: Message, state: FSMContext):
    """Початок пошуку"""
    await message.answer("🔍 Введіть ключове слово для пошуку:")
    await state.set_state(SearchState.waiting_keyword)

@dp.message(SearchState.waiting_keyword)
async def search_documents_handler(message: Message, state: FSMContext):
    """Обробка пошукового запиту"""
    keyword = message.text
    results = search_documents(keyword)
    
    if not results:
        await message.answer(f"❌ За запитом '{keyword}' документи не знайдено.")
        await state.clear()
        return
    
    response_text = f"🔍 **Результати пошуку за запитом:** '{keyword}'\n\n"
    
    for i, result in enumerate(results, 1):
        doc_type, doc_number, org, subject, content, date, notes, file_path = result
        
        type_emoji = "📥" if doc_type == "incoming" else "📤"
        org_label = "Від" if doc_type == "incoming" else "Кому"
        date_label = "Отримано" if doc_type == "incoming" else "Відправлено"
        
        file_info = " 📎" if file_path else ""
        
        response_text += (
            f"{type_emoji} **{i}. {doc_number}**{file_info}\n"
            f"**{org_label}:** {org}\n"
            f"**Тема:** {subject}\n"
            f"**{date_label}:** {date}\n"
            f"**Зміст:** {content[:100]}{'...' if len(content) > 100 else ''}\n\n"
        )
        
        if len(response_text) > 3500:  # Обмеження довжини повідомлення
            response_text += "... та інші результати"
            break
    
    await message.answer(response_text, parse_mode="Markdown")
    await state.clear()

# Health check для хостингу
async def health_check(request):
    """Health check endpoint для хостингу"""
    return web.Response(text="Bot is running!")

async def start_web_server():
    """Запуск веб-сервера для health check"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# Основна функція
async def main():
    """Основна функція запуску бота"""
    try:
        init_database()
        logger.info("База даних ініціалізована")
        
        # Запуск веб-сервера для health check (для хостингу)
        await start_web_server()
        
        logger.info("Запуск бота...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Помилка при запуску бота: {e}")
        raise
    finally:
        await bot.session.close()
        logger.info("Бот зупинено")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинено")
