import sqlite3
import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.methods.get_chat_member import GetChatMember

# === TOKEN VA CHAT ID ===
TOKEN = "7830067818:AAHdWV23wjWrFT9VxaJKNh7MwO3wm2UWCOk"  # Bot tokenini kiriting
GROUP_CHAT_ID = "-1002425037771"  # Admin guruh ID
CHANNEL_ID = "@transformatsiyamarkazinsu"  # Kanal username

# === BOT VA DISPATCHER ===
bot = Bot(token=TOKEN)
dp = Dispatcher()

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === DATABASE FUNKSIYALARI ===
def get_db_connection(db_name):
    return sqlite3.connect(db_name, check_same_thread=False)

# === USER DATABASE ===
conn_users = get_db_connection("users.db")
cursor_users = conn_users.cursor()
cursor_users.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        full_name TEXT,
        phone_number TEXT
    )
""")
conn_users.commit()

# === REQUEST DATABASE ===
conn_requests = get_db_connection("requests.db")
cursor_requests = conn_requests.cursor()
cursor_requests.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        file_id TEXT,
        status TEXT
    )
""")
conn_requests.commit()

# === XATOLARNI ADMINLARGA YUBORISH ===
async def send_error_to_admin(error_message):
    try:
        await bot.send_message(GROUP_CHAT_ID, f"⚠️ **Xatolik yuz berdi:**\n```{error_message}```", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Xatolik xabari yuborilmadi: {e}")

@dp.errors()
async def error_handler(event, exception):
    error_message = f"❌ Xatolik: {exception}"
    logging.error(error_message)
    await send_error_to_admin(error_message)

# === TELEFON RAQAM OLISH UCHUN KLAVIATURA ===
phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Telefon raqam yuborish", request_contact=True)]],
    resize_keyboard=True
)

# === ASOSIY MENU KLAVIATURASI ===
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📄 Scopus maqolalari yo‘riqnomasi")],
        [KeyboardButton(text="📑 Scopus jurnal topish")],
        [KeyboardButton(text="❓ Savol yo‘llash")]
    ],
    resize_keyboard=True
)

# === KANAL OBUNA TEKSHIRISH ===
async def is_subscribed(user_id):
    try:
        chat_member = await bot(GetChatMember(chat_id=CHANNEL_ID, user_id=user_id))
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Obuna tekshirishda xatolik: {e}")
        return False

# === START KOMANDASI ===
@dp.message(CommandStart())
async def start_command(message: types.Message):
    try:
        if not await is_subscribed(message.from_user.id):
            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Kanalga a'zo bo‘lish", url=f"https://t.me/{CHANNEL_ID[1:]}")]
            ])
            await message.answer("Iltimos, avval kanalga a'zo bo‘ling va qayta /start buyrug‘ini kiriting:", reply_markup=inline_keyboard)
            return

        cursor_users.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
        user = cursor_users.fetchone()
        if not user:
            await message.answer("Iltimos, telefon raqamingizni yuboring.", reply_markup=phone_keyboard)
        else:
            await message.answer("Assalomu alaykum! Xizmat turlaridan birini tanlang.", reply_markup=main_keyboard)
    except Exception as e:
        await send_error_to_admin(f"/start buyrug‘ida xatolik: {e}")

# === TELEFON RAQAMNI QABUL QILISH ===
@dp.message(lambda message: message.contact)
async def register_user(message: types.Message):
    try:
        phone_number = message.contact.phone_number
        full_name = message.from_user.full_name
        user_id = message.from_user.id

        cursor_users.execute("INSERT OR IGNORE INTO users (user_id, full_name, phone_number) VALUES (?, ?, ?)",
                            (user_id, full_name, phone_number))
        conn_users.commit()

        await message.answer("Rahmat! Endi xizmatlardan foydalanishingiz mumkin.", reply_markup=main_keyboard)
        await bot.send_message(GROUP_CHAT_ID, f"🆕 **Yangi foydalanuvchi:**\n👤 Ism: {full_name}\n📞 Telefon: {phone_number}\n🆔 User ID: {user_id}")
    except Exception as e:
        await send_error_to_admin(f"Telefon raqamni saqlashda xatolik: {e}")

# === FOYDALANUVCHI MUROJAATLARI ===
@dp.message()
async def handle_request(message: types.Message):
    try:
        file_id = message.document.file_id if message.document else None
        user_id = message.from_user.id
        cursor_users.execute("SELECT full_name, phone_number FROM users WHERE user_id = ?", (user_id,))
        user = cursor_users.fetchone()
        full_name, phone_number = user if user else ("Noma’lum", "Noma’lum")

        cursor_requests.execute("INSERT INTO requests (user_id, text, file_id, status) VALUES (?, ?, ?, ?)",
                                (user_id, message.text, file_id, "pending"))
        conn_requests.commit()
        request_id = cursor_requests.lastrowid

        await message.answer(f"Murojaatingiz qabul qilindi. ID: {request_id:06}")
        await bot.send_message(GROUP_CHAT_ID, f"📩 **Yangi murojaat:**\n👤 Ism: {full_name}\n📞 Telefon: {phone_number}\n🆔 User ID: {user_id}\n🔢 ID: {request_id:06}\n💬 Matn: {message.text}")

        if file_id:
            await bot.send_document(GROUP_CHAT_ID, file_id)
    except Exception as e:
        await send_error_to_admin(f"Murojaat saqlashda xatolik: {e}")

# === BOTNI ISHGA TUSHIRISH ===
async def main():
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logging.warning("Polling bekor qilindi!")
    except Exception as e:
        await send_error_to_admin(f"Bot ishlashida xatolik: {e}")
        await asyncio.sleep(5)  # 5 soniyadan keyin qayta urinish
        await main()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.warning("Bot to‘xtatildi!")
    finally:
        loop.close()
