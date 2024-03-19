import os

from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_user_carts, orm_add_to_cart, orm_reduce_product_in_cart, \
    orm_delete_from_cart, orm_get_products, orm_fetch_banner, orm_fetch_categories, orm_get_user, \
    get_referred_users_count
from keyboards.inline import get_products_btns, get_user_cart, \
    get_main_menu_buttons, get_catalog_buttons, get_profile_buttons
from utils.paginator import Paginator


async def generate_main_menu(session, level, menu_name):
    banner = await orm_fetch_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)
    buttons = get_main_menu_buttons(level=level)
    return image, buttons


async def generate_catalog(session, level, menu_name):
    banner = await orm_fetch_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)
    categories = await orm_fetch_categories(session)
    buttons = get_catalog_buttons(level=level, categories=categories)
    return image, buttons


def generate_pagination_buttons(paginator: Paginator):
    buttons = {}

    if paginator.has_previous():
        buttons["◀ Prev."] = "previous"
    if paginator.has_next():
        buttons["Next. ▶"] = "next"

    return buttons


async def products(session, level, category, page):
    products = await orm_get_products(session, category_id=category)

    paginator = Paginator(products, page=page)
    product = paginator.get_page()[0]

    image = InputMediaPhoto(
        media=product.image,
        caption=f"<strong>{product.name}\
                </strong>\n{product.description}\nPrice: {round(product.price, 2)}\n\
                <strong>Product {paginator.page} from {paginator.pages}</strong>",
    )

    pagination_btns = generate_pagination_buttons(paginator)

    kbds = get_products_btns(
        level=level,
        category=category,
        page=page,
        pagination_btns=pagination_btns,
        product_id=product.id,
    )

    return image, kbds


async def carts(session, level, menu_name, page, user_id, product_id):
    if menu_name == "delete":
        await orm_delete_from_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    elif menu_name == "decrement":
        is_cart = await orm_reduce_product_in_cart(session, user_id, product_id)
        if page > 1 and not is_cart:
            page -= 1
    elif menu_name == "increment":
        await orm_add_to_cart(session, user_id, product_id)

    carts = await orm_get_user_carts(session, user_id)

    if not carts:
        banner = await orm_fetch_banner(session, "cart")
        image = InputMediaPhoto(
            media=banner.image, caption=f"<strong>{banner.description}</strong>"
        )

        kbds = get_user_cart(
            level=level,
            page=None,
            pagination_btns=None,
            product_id=None,
        )

    else:
        paginator = Paginator(carts, page=page)

        cart = paginator.get_page()[0]

        cart_price = round(cart.quantity * cart.product.price, 2)
        total_price = round(
            sum(cart.quantity * cart.product.price for cart in carts), 2
        )
        image = InputMediaPhoto(
            media=cart.product.image,
            caption=f"<strong>{cart.product.name}</strong>\n{cart.product.price}$ x {cart.quantity} = {cart_price}$\
                    \nProduct {paginator.page} from {paginator.pages} in cart.\nTotal price of the cart {total_price}",
        )

        pagination_btns = generate_pagination_buttons(paginator)

        kbds = get_user_cart(
            level=level,
            page=page,
            pagination_btns=pagination_btns,
            product_id=cart.product.id,
        )

    return image, kbds


async def profile(session, menu_name, user_id, level):
    user = await orm_get_user(session, user_id)
    banner = await orm_fetch_banner(session, menu_name)
    buttons = get_profile_buttons(level=level)
    image = InputMediaPhoto(media=banner.image, caption=f"<strong>{banner.description}</strong>\n"
                                                        f"Referral link:{os.getenv("BOT_NICK")}?start={user.user_id}"
                                                        f"\nNumber of referrals: {await get_referred_users_count(session, user.user_id)}")
    return image, buttons


async def get_menu_content(
    session: AsyncSession,
    level: int,
    menu_name: str,
    category: int | None = None,
    page: int | None = None,
    product_id: int | None = None,
    user_id: int | None = None,
):
    if level == 0:
        return await generate_main_menu(session, level, menu_name)
    elif level == 1:
        return await generate_catalog(session, level, menu_name)
    elif level == 2:
        return await products(session, level, category, page)
    elif level == 3:
        return await carts(session, level, menu_name, page, user_id, product_id)
    elif level == 4:
        return await profile(session, menu_name, user_id, level)