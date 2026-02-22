import asyncio
import os
from aiogram import Bot, Dispatcher

from commands import MODERATOR_CHAT_ID, dp as router1
from database import init_db
from signal_photos import ensure_signal_photos

async def main():
    init_db()

    bot = Bot(token=os.environ.get("BOT_TOKEN", "8472110529:AAFmFaryS_wWq9ZoqXTfEA9ozC5p_fMzrC8"))
    dp = Dispatcher()
    dp.include_routers(router1)

    await ensure_signal_photos(bot, MODERATOR_CHAT_ID)

    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Successfully launched!")
    asyncio.run(main())