import os

from aiogram import types, Bot
from aiogram.filters import Filter

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


class IsAdmin(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: types.Message, bot: Bot) -> bool:
        return int(message.from_user.id) == int(os.getenv('ADMIN'))