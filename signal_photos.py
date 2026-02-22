# -*- coding: utf-8 -*-
"""
Загрузка изображений сигналов (bot_buy, bot_sell) в Telegram и кэширование file_id.

При первом запуске без signal_file_ids.json картинки из assets/ отправляются
в upload_chat_id (например, чат модератора), file_id сохраняются в signal_file_ids.json.
Дальше отправка идёт по file_id без повторной загрузки.

Риски file_id:
- Обычно file_id постоянен для одного бота и не удаляется Telegram.
- Может стать недействительным при смене токена бота (новый бот).
- В очень редких случаях Telegram может инвалидировать старые файлы.
Рекомендация: хранить signal_file_ids.json в бэкапах; при смене бота — перезалить картинки.
"""
import json
import os
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile

PROJECT_ROOT = Path(__file__).resolve().parent
IDS_PATH = PROJECT_ROOT / "signal_file_ids.json"
ASSETS_DIR = PROJECT_ROOT / "assets"
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
BUY_NAME = "bot_buy"
SELL_NAME = "bot_sell"


def load_signal_file_ids() -> dict[str, Optional[str]]:
    """Читает сохранённые file_id из signal_file_ids.json."""
    out = {"buy": None, "sell": None}
    if not IDS_PATH.is_file():
        return out
    try:
        with open(IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        out["buy"] = data.get("buy") or None
        out["sell"] = data.get("sell") or None
    except Exception:
        pass
    return out


def save_signal_file_ids(buy: Optional[str], sell: Optional[str]) -> None:
    """Сохраняет file_id в signal_file_ids.json."""
    data = {"buy": buy, "sell": sell}
    with open(IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _find_asset(name: str) -> Optional[Path]:
    for ext in EXTENSIONS:
        p = ASSETS_DIR / f"{name}{ext}"
        if p.is_file():
            return p
    return None


async def ensure_signal_photos(bot: Bot, upload_chat_id: int) -> dict[str, Optional[str]]:
    """
    Убеждается, что для buy/sell есть file_id. Если нет — заливает файлы из assets/
    в upload_chat_id и сохраняет file_id. Возвращает {"buy": file_id, "sell": file_id}.
    """
    ids = load_signal_file_ids()

    for key, name in [("buy", BUY_NAME), ("sell", SELL_NAME)]:
        if ids.get(key):
            continue
        path = _find_asset(name)
        if not path:
            continue
        try:
            photo = FSInputFile(path)
            msg = await bot.send_photo(upload_chat_id, photo=photo)
            file_id = msg.photo[-1].file_id
            ids[key] = file_id
            save_signal_file_ids(ids.get("buy"), ids.get("sell"))
        except Exception:
            pass

    return load_signal_file_ids()


def get_signal_photo_file_id(signal_direction: str) -> Optional[str]:
    """По направлению сигнала ('HIGHER' = buy, 'LOWER' = sell) возвращает file_id или None."""
    ids = load_signal_file_ids()
    if signal_direction == "HIGHER":
        return ids.get("buy")
    if signal_direction == "LOWER":
        return ids.get("sell")
    return None
