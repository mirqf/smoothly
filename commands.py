import asyncio
import random
from aiogram import Router, F, types, Bot
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    user_exists,
    add_user,
    is_verification_pending,
    set_verification_pending,
    get_user_info,
    update_verification_status,
    is_verified,
    get_user_language,
    update_user_language,
)
from locale import S
from signal_photos import get_signal_photo_file_id

dp = Router()

MODERATOR_CHAT_ID = 8456243771
MODERATOR_LANG = "ru"

# FSM
class LanguageSelection(StatesGroup):
    selecting = State()

class VerificationProcess(StatesGroup):
    waiting_files = State()

class ModeratorReview(StatesGroup):
    reviewing = State()


def get_language_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=S("btn_english", "en"), callback_data="lang_en")
    builder.button(text=S("btn_russian", "ru"), callback_data="lang_ru")
    builder.button(text=S("btn_spanish", "es"), callback_data="lang_es")
    builder.button(text=S("btn_arabic", "ar"), callback_data="lang_ar")
    builder.adjust(2)
    return builder.as_markup()


@dp.message(Command("start", "lang"))
async def start(message: types.Message, state: FSMContext):
    await state.set_state(LanguageSelection.selecting)
    await message.answer(
        text=S("select_language_message", "en"),
        parse_mode="HTML",
        reply_markup=get_language_keyboard(),
    )


@dp.callback_query(LanguageSelection.selecting, F.data.startswith("lang_"))
async def select_language(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.username
    lang_code = callback.data.replace("lang_", "").strip().lower()
    if lang_code not in ("en", "ru", "es", "ar"):
        lang_code = "en"

    update_user_language(user_id, username, lang_code)
    await callback.message.delete()

    builder = InlineKeyboardBuilder()
    builder.button(text=S("btn_get_signals", lang_code), callback_data="get_signals")
    builder.button(text=S("btn_language", lang_code), callback_data="selecting_lang")
    builder.button(text=S("btn_support", lang_code), url="https://t.me/ScannerManager")
    builder.adjust(1, 2)

    await callback.message.answer(
        text=S("start_after_lang", lang_code),
        reply_markup=builder.as_markup(),
    )


@dp.callback_query(F.data == "selecting_lang")
async def lang_selecting(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(LanguageSelection.selecting)
    lang = get_user_language(callback.from_user.id)
    await callback.message.answer(
        text=S("select_language_message", lang),
        parse_mode="HTML",
        reply_markup=get_language_keyboard(),
    )


@dp.callback_query(F.data == "get_signals")
async def get_signals(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if is_verified(user_id):
        await callback.message.answer(
            text=S("get_signals_instruction", lang),
            parse_mode="HTML",
        )
    else:
        await throw_unauthorized(callback.message, lang)


@dp.message(Command("verify"))
async def verify(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = get_user_language(user_id)

    if is_verified(user_id):
        await message.reply(S("already_verified", lang))
        return
    if is_verification_pending(user_id):
        await message.reply(S("verification_pending", lang))
        return

    await state.set_state(VerificationProcess.waiting_files)
    await message.reply(S("verify_request", lang))


@dp.message(VerificationProcess.waiting_files)
async def receive_verification_files(message: types.Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    user_info = get_user_info(user_id)

    if not message.document and not message.photo:
        await message.reply(S("need_file", lang))
        return

    if not user_info:
        await message.reply(S("user_not_found", lang))
        return

    user_id_db, username = user_info
    username_display = username if username else S("na", MODERATOR_LANG)
    moderator_text = (
        f"{S('moderator_new_verification', MODERATOR_LANG)}\n\n"
        f"{S('moderator_user_id', MODERATOR_LANG)} <code>{user_id_db}</code>\n"
        f"{S('moderator_username', MODERATOR_LANG)} <code>@{username_display}</code>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=S("btn_approve", MODERATOR_LANG), callback_data=f"approve_{user_id_db}")
    builder.button(text=S("btn_reject", MODERATOR_LANG), callback_data=f"reject_{user_id_db}")
    builder.adjust(2)

    if message.document:
        await bot.send_document(
            chat_id=MODERATOR_CHAT_ID,
            document=message.document.file_id,
            caption=moderator_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    elif message.photo:
        await bot.send_photo(
            chat_id=MODERATOR_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=moderator_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    else:
        await bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            text=moderator_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )

    set_verification_pending(user_id, True)
    await message.reply(S("files_received", lang))
    await state.clear()


@dp.callback_query(F.data.startswith("approve_"))
async def approve_verification(callback: types.CallbackQuery, bot: Bot):
    user_id = int(callback.data.replace("approve_", ""))
    lang = get_user_language(user_id)

    update_verification_status(user_id, True)
    set_verification_pending(user_id, False)

    await bot.send_message(chat_id=user_id, text=S("accepted", lang))

    msg = S("moderator_approved", MODERATOR_LANG)
    await callback.answer(msg)
    new_caption = (callback.message.caption or "") + "\n\n" + msg
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)


@dp.callback_query(F.data.startswith("reject_"))
async def reject_verification(callback: types.CallbackQuery, bot: Bot):
    user_id = int(callback.data.replace("reject_", ""))
    lang = get_user_language(user_id)

    update_verification_status(user_id, False)
    set_verification_pending(user_id, False)

    await bot.send_message(chat_id=user_id, text=S("rejected", lang))

    msg = S("moderator_rejected", MODERATOR_LANG)
    await callback.answer(msg)
    new_caption = (callback.message.caption or "") + "\n\n" + msg
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)


signals = [("HIGHER", "S15"), ("HIGHER", "S5"), ("LOWER", "S15"), ("LOWER", "S5")]


async def throw_unauthorized(message: types.Message, lang_code: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=S("btn_create_account", lang_code),
        url="https://u3.shortink.io/register?utm_campaign=839002&utm_source=affiliate&utm_medium=sr&a=NUYNmfmAkKYMaY&ac=scanner-trade-bot&code=ROS149",
    )
    builder.button(text=S("btn_support", lang_code), url="https://t.me/ScannerManager")
    builder.adjust(1)

    await message.answer(
        text=S("unauthorized_message", lang_code),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@dp.message(Command("signals"))
async def signals_cmd(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    if is_verified(user_id):
        await message.answer(
            text=S("get_signals_instruction", lang),
            parse_mode="HTML",
        )
    else:
        await throw_unauthorized(message, lang)


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)

    if not is_verified(user_id):
        await throw_unauthorized(message, lang)
        return

    waiting_msg = await message.reply(
        S("generating_forecast", lang),
        parse_mode="HTML",
    )

    await asyncio.sleep(random.randint(3, 5))
    signal = random.choice(signals)
    direction, timeframe = signal[0], signal[1]
    caption = (
        f"<b>{S('signal_info_title', lang)}</b>\n"
        f"{S('pair_label', lang)} EUR/USD (OTC) | {timeframe}\n"
        f"{S('scanner_signal_label', lang)} {direction}"
    )

    await waiting_msg.delete()
    photo_file_id = get_signal_photo_file_id(direction)
    if photo_file_id:
        await message.answer_photo(photo=photo_file_id, caption=caption, parse_mode="HTML")
    else:
        await message.answer(text=caption, parse_mode="HTML")


@dp.message(F.text)
async def unknown_command(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    await message.reply(S("command_not_found", lang))
