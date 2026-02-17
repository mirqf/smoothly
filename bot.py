import asyncio, logging, sqlite3
from aiogram import Bot, Dispatcher
from commands import dp as router1
from database import init_db
from dotenv import load_dotenv
import os

load_dotenv()

async def main():
    init_db()
    
    bot = Bot(token = os.getenv("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_routers(router1)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Successfully launched!")
    asyncio.run(main())