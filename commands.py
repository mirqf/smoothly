import asyncio
import random
from aiogram import Router, F, types, Bot
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from collections import defaultdict
from aiogram.types import InputMediaPhoto, InputMediaVideo

_verification_albums: dict[str, list] = defaultdict(list)

from database import (
    user_exists,
    add_user,
    is_verification_pending,
    set_verification_pending,
    get_user_info,
    get_user_id_by_username,
    update_verification_status,
    is_verified,
    get_user_language,
    update_user_language,
)
from i18n import S
from signal_photos import get_signal_photo_file_id, load_signal_file_ids

dp = Router()

MODERATOR_CHAT_ID = 5081716116
MODERATOR_LANG = "ru"

# FSM
class LanguageSelection(StatesGroup):
    selecting = State()

class VerificationProcess(StatesGroup):
    waiting_files = State()

class ModeratorReview(StatesGroup):
    reviewing = State()

_verification_media_scheduled: set[str] = set()


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

    ids = load_signal_file_ids()
    await callback.message.answer_photo(
        photo = ids.get("welcome"),
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

@dp.callback_query(F.data == "verify_account")
async def verify_callback(callback: types.CallbackQuery, state: FSMContext):
    message = callback.message
    user_id = message.chat.id
    lang = get_user_language(user_id)

    if is_verified(user_id):
        await message.reply(S("already_verified", lang))
        return
    if is_verification_pending(user_id):
        await message.reply(S("verification_pending", lang))
        return

    await state.set_state(VerificationProcess.waiting_files)
    await message.reply(S("verify_request", lang), parse_mode="HTML")


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
    await message.reply(S("verify_request", lang), parse_mode="HTML")

@dp.message(VerificationProcess.waiting_files)
async def receive_verification_files(
    message: types.Message,
    state: FSMContext,
    bot: Bot
):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    user_info = get_user_info(user_id)

    if not user_info:
        await message.reply(S("user_not_found", lang))
        return
    
    if not message.photo and not message.video:
        await message.reply(S("need_file", lang))
        return

    user_id_db, username = user_info
    username_display = username if username else S("na", MODERATOR_LANG)

    # -------------------------------------------------
    # Если это альбом (media_group)
    # -------------------------------------------------
    if message.media_group_id:

        group_id = message.media_group_id

        if group_id not in _verification_albums:
            _verification_albums[group_id] = {
                "user_id": user_id,
                "user_id_db": user_id_db,
                "username_display": username_display,
                "media": [],
                "caption": message.caption or "",
            }

        album = _verification_albums[group_id]

        # Добавляем файл
        if message.photo:
            album["media"].append(
                InputMediaPhoto(media=message.photo[-1].file_id)
            )
        elif message.video:
            album["media"].append(
                InputMediaVideo(media=message.video.file_id)
            )

        # Если есть caption — сохраняем
        if message.caption:
            album["caption"] = message.caption

        # Планируем отправку только один раз
        if len(album["media"]) == 1:

            async def send_album():
                await asyncio.sleep(1)  # ждём пока Telegram пришлёт все элементы

                album_data = _verification_albums.pop(group_id, None)
                if not album_data:
                    return

                media_list = album_data["media"]

                media_list[0].caption = album_data['caption'] or ''

                # 1️⃣ Отправляем альбом
                await bot.send_media_group(
                    chat_id=MODERATOR_CHAT_ID,
                    media=media_list,
                )

                # 2️⃣ Отправляем кнопки отдельным сообщением

                mod_text = (
                    f"{S('moderator_new_verification', MODERATOR_LANG)}\n\n"
                    f"{S('moderator_user_id', MODERATOR_LANG)} <code>{user_id_db}</code>\n" 
                    f"{S('moderator_username', MODERATOR_LANG)} @{username_display}"
                )
                builder = InlineKeyboardBuilder()
                builder.button(text=S("btn_approve", MODERATOR_LANG), callback_data=f"approve_{album_data['user_id_db']}")
                builder.button(text=S("btn_reject", MODERATOR_LANG), callback_data=f"reject_{album_data['user_id_db']}")

                await bot.send_message(
                    chat_id=MODERATOR_CHAT_ID,
                    text=mod_text,
                    reply_markup=builder.as_markup(),
                    parse_mode = "HTML"
                )

                set_verification_pending(user_id, True)

                await bot.send_message(
                    chat_id=user_id,
                    text=S("files_received", lang),
                )

                await state.clear()

            asyncio.create_task(send_album())

    else:

        await message.copy_to(
            chat_id=MODERATOR_CHAT_ID,
            caption=message.caption or '',
            parse_mode="HTML",
        )

        mod_text = (
            f"{S('moderator_new_verification', MODERATOR_LANG)}\n\n"
            f"{S('moderator_user_id', MODERATOR_LANG)} <code>{user_id_db}</code>\n" 
            f"{S('moderator_username', MODERATOR_LANG)} @{username_display}"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text=S("btn_approve", MODERATOR_LANG), callback_data=f"approve_{user_id_db}")
        builder.button(text=S("btn_reject", MODERATOR_LANG), callback_data=f"reject_{user_id_db}",)

        await bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            text=mod_text,
            reply_markup=builder.as_markup(),
            parse_mode = "HTML"
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

    builder = InlineKeyboardBuilder()
    builder.button(text = S("btn_get_signals", lang), callback_data = "get_signals")
    await bot.send_message(
        chat_id=user_id, 
        text=S("accepted", lang),
        reply_markup = builder.as_markup()
    ),
    

    msg = S("moderator_approved", MODERATOR_LANG)
    await callback.answer(msg)
    new_text = (callback.message.text or "") + "\n\n" + msg
    await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")


@dp.callback_query(F.data.startswith("reject_"))
async def reject_verification(callback: types.CallbackQuery, bot: Bot):
    user_id = int(callback.data.replace("reject_", ""))
    lang = get_user_language(user_id)

    update_verification_status(user_id, False)
    set_verification_pending(user_id, False)

    await bot.send_message(chat_id=user_id, text=S("rejected", lang))

    msg = S("moderator_rejected", MODERATOR_LANG)
    await callback.answer(msg)
    new_text = (callback.message.text or "") + "\n\n" + msg
    await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")


@dp.message(Command("verification"))
async def verification_cmd(message: types.Message):
    if message.chat.id != MODERATOR_CHAT_ID:
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 3:
        await message.reply(
            S("verification_usage", MODERATOR_LANG),
            parse_mode="HTML",
        )
        return
    _, username_part, status_str = parts
    if status_str not in ("0", "1"):
        await message.reply(
            S("verification_usage", MODERATOR_LANG),
            parse_mode="HTML",
        )
        return
    user_id = get_user_id_by_username(username_part)
    if user_id is None:
        await message.reply(
            S("verification_user_not_found", MODERATOR_LANG).format(
                username=username_part.lstrip("@") or username_part
            ),
            parse_mode="HTML",
        )
        return
    status = status_str == "1"
    update_verification_status(user_id, status)
    set_verification_pending(user_id, False)
    await message.reply(
        S("verification_done", MODERATOR_LANG).format(
            username=username_part.lstrip("@") or username_part,
            status=S("verification_status_yes", MODERATOR_LANG) if status else S("verification_status_no", MODERATOR_LANG),
        ),
        parse_mode="HTML",
    )


signals = [("HIGHER", "S15"), ("HIGHER", "S5"), ("LOWER", "S15"), ("LOWER", "S5")]


async def throw_unauthorized(message: types.Message, lang_code: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=S("btn_create_account", lang_code),
        url="https://u3.shortink.io/register?utm_campaign=839002&utm_source=affiliate&utm_medium=sr&a=NUYNmfmAkKYMaY&ac=scanner-trade-bot&code=ROS149",
    )
    builder.button(text=S("btn_verify_account", lang_code), callback_data="verify_account")
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