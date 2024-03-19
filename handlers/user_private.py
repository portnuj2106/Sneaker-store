from aiogram import F, types, Router
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_add_user, orm_add_to_cart, orm_get_user_carts
from handlers.menu_processing import get_menu_content
from keyboards.inline import MenuCallBack

user_private_router = Router()


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    start_command = message.text
    referrer_id = str(start_command[7:])
    if str(referrer_id) != "":
        if str(referrer_id) != str(message.from_user.id):
            await orm_add_user(
                session,
                user_id=message.from_user.id,
                referred_id=int(referrer_id),
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                phone=None,
            )
            try:
                await message.answer("Someone registered using your referral link", reply_to_message_id=int(referrer_id))
            except:
                pass
        else:
            await orm_add_user(
                session,
                user_id=message.from_user.id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                phone=None,
            )
            await message.answer("You cant register using your own referral link")
    else:
        await orm_add_user(
            session,
            user_id=message.from_user.id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            phone=None,
        )
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):

    if callback_data.menu_name == "add_to_cart":
        user = callback.from_user
        await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
        await callback.answer("Product added to the cart.")
        return

    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()
