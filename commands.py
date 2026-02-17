import asyncio, random
from aiogram import Router, F, types, Bot
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.state import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import (user_exists, add_user, update_language, 
                      is_verification_pending, set_verification_pending,
                      get_user_info, update_verification_status, is_verified, get_user_language, update_user_language)

dp = Router()

MODERATOR_CHAT_ID = 8456243771

# FSM States
class LanguageSelection(StatesGroup):
    selecting = State()

class VerificationProcess(StatesGroup):
    waiting_files = State()

class ModeratorReview(StatesGroup):
    reviewing = State()

# Получить клавиатуру выбора языка
def get_language_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇬🇧 English", callback_data="lang_English")
    builder.button(text="🇷🇺 Русский", callback_data="lang_Russian")
    builder.button(text="🇪🇸 Español", callback_data="lang_Spanish")
    builder.button(text="🇸🇦 العربية", callback_data="lang_Hindi")
    builder.adjust(2)
    return builder.as_markup()

# Получить словарь переводов
def get_translations():
    return {
        "English": {
            "welcome": "Welcome! 🎉",
            "language_selected": "Language selected: English",
            "choose_language": "Choose your language:",
            "verify_request": "Please send your verification files:",
            "verification_pending": "Your verification request is already under review. Please wait.",
            "files_received": "Files received! Moderators will review them shortly.",
            "accepted": "✅ Your verification has been accepted!",
            "rejected": "❌ Your verification has been rejected. Please try again.",
            "already_verified": "You are already verified!",
            "command_not_found": "❌ This command does not exist. Please use /start to see available commands.",
            "not_verified": "❌ You are not verified yet. Please use /verify to start the verification process.",
            "nice_looking": "Looking great! 😊"
        },
        "Russian": {
            "welcome": "Добро пожаловать! 🎉",
            "language_selected": "Язык выбран: Русский",
            "choose_language": "Выберите ваш язык:",
            "verify_request": "Отправьте файлы для верификации:",
            "verification_pending": "Ваш запрос на верификацию уже на рассмотрении. Пожалуйста, подождите.",
            "files_received": "Файлы получены! Модераторы рассмотрят их в скором времени.",
            "accepted": "✅ Ваша верификация одобрена!",
            "rejected": "❌ Ваша верификация отклонена. Пожалуйста, попробуйте снова.",
            "already_verified": "Вы уже верифицированы!",
            "command_not_found": "❌ Такой команды не существует. Пожалуйста, используйте /start для просмотра доступных команд.",
            "not_verified": "❌ Вы еще не верифицированы. Пожалуйста, используйте /verify для начала процесса верификации.",
            "nice_looking": "Выглядишь классно! 😊"
        },
        "Spanish": {
            "welcome": "¡Bienvenido! 🎉",
            "language_selected": "Idioma seleccionado: Español",
            "choose_language": "Elige tu idioma:",
            "verify_request": "Por favor, envía tus archivos de verificación:",
            "verification_pending": "Tu solicitud de verificación ya está en revisión. Por favor, espera.",
            "files_received": "¡Archivos recibidos! Los moderadores los revisarán pronto.",
            "accepted": "✅ ¡Tu verificación ha sido aceptada!",
            "rejected": "❌ Tu verificación ha sido rechazada. Por favor, intenta de nuevo.",
            "already_verified": "¡Ya estás verificado!",
            "command_not_found": "❌ Este comando no existe. Por favor, usa /start para ver los comandos disponibles.",
            "not_verified": "❌ Aún no estás verificado. Por favor, usa /verify para iniciar el proceso de verificación.",
            "nice_looking": "¡Te ves muy bien! 😊"
        },
        "Hindi": {
            "welcome": "स्वागत है! 🎉",
            "language_selected": "भाषा चुनी गई: हिंदी",
            "choose_language": "अपनी भाषा चुनें:",
            "verify_request": "कृपया अपनी सत्यापन फ़ाइलें भेजें:",
            "verification_pending": "आपका सत्यापन अनुरोध पहले से समीक्षा में है। कृपया प्रतीक्षा करें।",
            "files_received": "फ़ाइलें प्राप्त हुईं! मॉडरेटर शीघ्र ही उनकी समीक्षा करेंगे।",
            "accepted": "✅ आपका सत्यापन स्वीकार कर लिया गया है!",
            "rejected": "❌ आपका सत्यापन अस्वीकार कर दिया गया है। कृपया दोबारा प्रयास करें।",
            "already_verified": "आप पहले से सत्यापित हैं!",
            "command_not_found": "❌ यह आदेश मौजूद नहीं है। कृपया उपलब्ध आदेशों को देखने के लिए /start का उपयोग करें।",
            "not_verified": "❌ आप अभी तक सत्यापित नहीं हैं। कृपया सत्यापन प्रक्रिया शुरू करने के लिए /verify का उपयोग करें।",
            "nice_looking": "बहुत अच्छा दिख रहे हो! 😊"
        }
    }

def translate(language: str, key: str) -> str:
    translations = get_translations()
    lang_name = "Russian" if language == "Russian" else language
    return translations.get(lang_name, translations["English"]).get(key, "")

# Команда /start и /language
@dp.message(Command("start", "lang"))
async def start(message: types.Message, state: FSMContext):
    await state.set_state(LanguageSelection.selecting)
    await message.answer(
        text = "<b>Select your preferred language</b>\nYou can change the language at any time from the main menu",
        parse_mode = "HTML", reply_markup = get_language_keyboard()
    )

# Обработчик выбора языка при /start и /language
@dp.callback_query(LanguageSelection.selecting, F.data.startswith("lang_"))
async def select_language(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.username
    language = callback.data.replace("lang_", "")
    
    # Обновляем язык пользователя, сохраняя статусы верификации
    update_user_language(user_id, username, language)
    await callback.message.delete()

    builder = InlineKeyboardBuilder()
    builder.button(text = "📈 Get Signals", callback_data = "get_signals")
    builder.button(text = "🔤 Language", callback_data = "selecting_lang")
    builder.button(text = "🎗️ Support", url = "https://t.me/ScannerManager")
    builder.adjust(1, 2)

    await callback.message.answer(
        text = "Начнем работу с ботом!",
        reply_markup = builder.as_markup()
    )

@dp.callback_query(F.data == "selecting_lang")
async def lang_selecting(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(LanguageSelection.selecting)
    await callback.message.answer(
        text = "<b>Select your preferred language</b>\nYou can change the language at any time from the main menu",
        parse_mode = "HTML", reply_markup = get_language_keyboard()
    )

@dp.callback_query(F.data == "get_signals")
async def get_signals(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if is_verified(user_id):
        await callback.message.answer(
            text = "Для получения сигналов отправьте боту скриншот, где четко видно <b>валютную пару</b> и <b>график</b>",
            parse_mode = "HTML"
        )
    else:
        await callback.message.answer("Для получения доступа к сигналам необходимо авторизоваться!\nИспользуйте /verify и следуйте инструкциям")

# Команда /verify
@dp.message(Command("signals"))
async def signals_cmd(message: types.Message, state: FSMContext):
    if is_verified(message.from_user.id):
        await message.answer(
            text = "Для получения сигналов отправьте боту скриншот, где четко видно <b>валютную пару</b> и <b>график</b>",
            parse_mode = "HTML"
        )
    else:
        await message.answer("Для получения доступа к сигналам необходимо авторизоваться!\nИспользуйте /verify и следуйте инструкциям")

# Команда /verify
@dp.message(Command("verify"))
async def verify(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, уже ли верифицирован
    if is_verified(user_id):
        language = "English"
        await message.reply(translate(language, "already_verified"))
        return
    
    # Проверяем, есть ли уже запрос на верификацию
    if is_verification_pending(user_id):
        language = "English"  # Умолчание, можно получить из БД
        await message.reply(translate(language, "verification_pending"))
        return
    
    language = "English"  # Умолчание
    await state.set_state(VerificationProcess.waiting_files)
    await message.reply(translate(language, "verify_request"))

# Обработчик получения файлов для верификации
@dp.message(VerificationProcess.waiting_files)
async def receive_verification_files(message: types.Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_info = get_user_info(user_id)

    if not message.document and not message.photo:
        await message.reply("Для подтверждения верификации прикрепите хотя бы один файл!")
        return
    
    if not user_info:
        await message.reply("User not found in database")
        return
    
    user_id_db, username = user_info
    
    # Готовим текст для модератора
    moderator_text = f"""📋 <b>Новая верификация</b>

👤 ID пользователя: <code>{user_id_db}</code>
📝 Username: <code>@{username if username else 'N/A'}</code>
    """
    
    # Готовим кнопки для модератора
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data=f"approve_{user_id_db}")
    builder.button(text="❌ Отклонить", callback_data=f"reject_{user_id_db}")
    builder.adjust(2)
    
    # Отправляем файл с текстом и кнопками в одном сообщении
    if message.document:
        await bot.send_document(
            chat_id=MODERATOR_CHAT_ID,
            document=message.document.file_id,
            caption=moderator_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    elif message.photo:
        await bot.send_photo(
            chat_id=MODERATOR_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=moderator_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    else:
        # Если нет файла/фото, просто отправляем сообщение с кнопками
        await bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            text=moderator_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    
    # Устанавливаем флаг, что верификация на рассмотрении
    set_verification_pending(user_id, True)
    # Уведомляем пользователя
    language = "English"
    await message.reply(translate(language, "files_received"))
    await state.clear()

# Обработчик одобрения верификации
@dp.callback_query(F.data.startswith("approve_"))
async def approve_verification(callback: types.CallbackQuery, bot: Bot):
    user_id = int(callback.data.replace("approve_", ""))
    
    # Обновляем статус верификации
    update_verification_status(user_id, True)
    set_verification_pending(user_id, False)
    
    # Уведомляем пользователя
    language = "English"
    await bot.send_message(
        chat_id=user_id,
        text=translate(language, "accepted")
    )
    
    await callback.answer("Верификация одобрена ✅")
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\nВерификация одобрена ✅",
        reply_markup=None
    )

# Обработчик отклонения верификации
@dp.callback_query(F.data.startswith("reject_"))
async def reject_verification(callback: types.CallbackQuery, bot: Bot):
    user_id = int(callback.data.replace("reject_", ""))
    
    # Обновляем статус верификации
    update_verification_status(user_id, False)
    set_verification_pending(user_id, False)
    
    # Уведомляем пользователя
    language = "English"
    await bot.send_message(
        chat_id=user_id,
        text=translate(language, "rejected")
    )
    
    await callback.answer("Верификация отклонена ❌")
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\nВерификация отклонена ❌",
        reply_markup=None
    )

# Обработчик неизвестной команды
@dp.message(F.text.startswith("/"))
async def unknown_command(message: types.Message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    await message.reply(translate(language, "command_not_found"))

time_periods = ["S5", "S15", "M1", "M3", "M5"]
outcomes = ["BUY", "SELL"]

# Обработчик отправки фотографий
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    language = get_user_language(user_id)

    if not is_verified(user_id):
        await message.reply(translate(language, "not_verified"))
        return

    waiting_msg = await message.reply("<b>🔄 Генерирую прогноз...</b>\nЭто займет не более 5 секунд", parse_mode = "HTML")

    await asyncio.sleep(random.randint(3, 5))

    period = random.choice(time_periods)
    direction = random.choice(outcomes)

    await waiting_msg.edit_text(
        f"""📊 <b>Прогноз готов!</b>

⏱ Таймфрейм: <b>{period}</b>
📈 Направление: <b>{direction}</b>
        """,
        parse_mode="HTML"
    )
