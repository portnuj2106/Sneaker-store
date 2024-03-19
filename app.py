import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from dotenv import find_dotenv, load_dotenv

from database.engine import create_db, session_maker
from handlers.admin_private import admin_private_router
from handlers.user_private import user_private_router
from middlewares.db import DataBaseSession

logging.basicConfig(level=logging.INFO)

load_dotenv(find_dotenv())


bot = Bot(token=os.getenv('TOKEN'), parse_mode=ParseMode.HTML)
bot.my_admins_list = []

dp = Dispatcher()

dp.include_router(user_private_router)
dp.include_router(admin_private_router)


async def on_startup(bot):
    await create_db()


async def on_shutdown(bot):
    print("Don't leave me")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.update.middleware(DataBaseSession(session_pool=session_maker))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


asyncio.run(main())