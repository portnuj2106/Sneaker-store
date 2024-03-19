from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_info_pages, orm_change_banner_image, orm_get_product, orm_fetch_categories, \
    orm_update_product, orm_add_product, orm_delete_product, orm_get_products
from filters.is_Admin import IsAdmin
from keyboards.inline import get_callback_btns
from keyboards.reply import get_keyboard

admin_private_router = Router()
admin_private_router.message.filter(IsAdmin())


ADMIN_KB = get_keyboard(
    "Add Product",
    "Assortment",
    "Add/Change Banner",
    placeholder="Select action",
    sizes=(2,),
)


@admin_private_router.message(Command("admin"))
async def admin_features(message: types.Message):
    await message.answer("What would you like to do?", reply_markup=ADMIN_KB)


@admin_private_router.message(F.text == 'Assortment')
async def admin_features(message: types.Message, session: AsyncSession):
    categories = await orm_fetch_categories(session)
    btns = {category.name : f'category_{category.id}' for category in categories}
    await message.answer("Select a category", reply_markup=get_callback_btns(btns=btns))


@admin_private_router.callback_query(F.data.startswith('category_'))
async def starring_at_product(callback: types.CallbackQuery, session: AsyncSession):
    category_id = callback.data.split('_')[-1]
    for product in await orm_get_products(session, int(category_id)):
        await callback.message.answer_photo(
            product.image,
            caption=f"<strong>{product.name}\
                    </strong>\n{product.description}\nPrice: {round(product.price, 2)}",
            reply_markup=get_callback_btns(
                btns={
                    "Delete": f"delete_{product.id}",
                    "Modify": f"change_{product.id}",
                },
                sizes=(2,)
            ),
        )
    await callback.answer()


@admin_private_router.callback_query(F.data.startswith("delete_"))
async def delete_product_callback(callback: types.CallbackQuery, session: AsyncSession):
    product_id = callback.data.split("_")[-1]
    await orm_delete_product(session, int(product_id))

    await callback.answer("Product deleted")
    await callback.message.answer("Product deleted!")


################# FSM for BANNERS ############################

class AddBanner(StatesGroup):
    image = State()


@admin_private_router.message(StateFilter(None), F.text == 'Add/Change Banner')
async def add_image2(message: types.Message, state: FSMContext, session: AsyncSession):
    pages_names = [page.name for page in await orm_get_info_pages(session)]
    await message.answer(f"Send the banner photo.\nSpecify the page for which it's intended:\
                         \n{', '.join(pages_names)}")
    await state.set_state(AddBanner.image)


# Handle the case when the user sends a photo for adding or changing a banner
@admin_private_router.message(AddBanner.image, F.photo)
async def add_banner(message: types.Message, state: FSMContext, session: AsyncSession):
    # Extract the file ID of the photo
    image_id = message.photo[-1].file_id

    # Extract the page name from the caption
    for_page = message.caption.strip()

    # Get the names of all pages from the database
    pages_names = [page.name for page in await orm_get_info_pages(session)]

    # Check if the provided page name is valid
    if for_page not in pages_names:
        await message.answer(f"Please enter a valid page name, for example:\
                         \n{', '.join(pages_names)}")
        return

    # Change the banner image for the specified page in the database
    await  orm_change_banner_image(session, for_page, image_id)

    # Confirm that the banner has been added or changed
    await message.answer("The banner has been added/changed.")

    # Clear the state to end the FSM flow
    await state.clear()


# Handle incorrect input
@admin_private_router.message(AddBanner.image)
async def add_banner2(message: types.Message, state: FSMContext):
    await message.answer("Send the banner photo or cancel.")


######################### FSM for adding/updating products ###################


class AddProduct(StatesGroup):
    # State steps
    name = State()
    description = State()
    category = State()
    price = State()
    image = State()

    product_for_change = None

    texts = {
        "AddProduct:name": "Enter the name again:",
        "AddProduct:description": "Enter the description again:",
        "AddProduct:category": "Select the category again ⬆️",
        "AddProduct:price": "Enter the price again:",
        "AddProduct:image": "This state is the last one, so...",
    }


# Transition to the state waiting for name input
@admin_private_router.callback_query(StateFilter(None), F.data.startswith("change_"))
async def change_product_callback(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    # Extract the product ID from the callback data
    product_id = callback.data.split("_")[-1]

    # Retrieve the product information from the database
    product_for_change = await orm_get_product(session, int(product_id))

    # Assign the retrieved product to the class attribute for later reference
    AddProduct.product_for_change = product_for_change

    # Acknowledge the callback
    await callback.answer()

    # Ask the user to input the product name
    await callback.message.answer(
        "Enter the product name", reply_markup=types.ReplyKeyboardRemove()
    )

    # Transition to the state waiting for name input
    await state.set_state(AddProduct.name)


# Transition to the state waiting for name input
@admin_private_router.message(StateFilter(None), F.text == "Add Product")
async def add_product(message: types.Message, state: FSMContext):
    await message.answer(
        "Enter the product name", reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddProduct.name)


# The cancellation and state reset handler should always be placed here,
# after transitioning to the first state (elementary filter order)
@admin_private_router.message(StateFilter("*"), Command("cancel"))
@admin_private_router.message(StateFilter("*"), F.text.casefold() == "cancel")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    if AddProduct.product_for_change:
        AddProduct.product_for_change = None
    await state.clear()
    await message.answer("Actions cancelled", reply_markup=ADMIN_KB)


# Go back one step (to the previous state)
@admin_private_router.message(StateFilter("*"), Command("back"))
@admin_private_router.message(StateFilter("*"), F.text.casefold() == "back")
async def back_step_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state == AddProduct.name:
        await message.answer(
            'There is no previous step, either enter the product name or type "cancel"'
        )
        return

    previous = None
    for step in AddProduct.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(
                f"Okay, you've returned to the previous step\n {AddProduct.texts[previous.state]}"
            )
            return
        previous = step


# Capture data for the 'name' state and then transition to the 'description' state
@admin_private_router.message(AddProduct.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(name=AddProduct.product_for_change.name)
    else:
        if not (4 <= len(message.text) <= 150):
            await message.answer(
                "The product name should be between 5 and 150 characters long. Please enter again."
            )
            return

        await state.update_data(name=message.text)
    await message.answer("Enter the product description")
    await state.set_state(AddProduct.description)


# Handler for catching incorrect input for the 'name' state
@admin_private_router.message(AddProduct.name)
async def add_name2(message: types.Message, state: FSMContext):
    await message.answer("You entered invalid data. Please enter the product name as text.")


# Capture data for the 'description' state and then transition to the 'price' state
@admin_private_router.message(AddProduct.description, F.text)
async def add_description(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(description=AddProduct.product_for_change.description)
    else:
        if len(message.text) < 5:
            await message.answer(
                "Description is too short. Please enter again."
            )
            return
        await state.update_data(description=message.text)

    categories = await orm_fetch_categories(session)
    btns = {category.name: str(category.id) for category in categories}
    await message.answer("Select the category", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddProduct.category)


# Handler for catching incorrect input for the 'description' state
@admin_private_router.message(AddProduct.description)
async def add_description2(message: types.Message, state: FSMContext):
    await message.answer("You entered invalid data. Please enter the product description as text.")


# Capture the category selection callback
@admin_private_router.callback_query(AddProduct.category)
async def category_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    if int(callback.data) in [category.id for category in await orm_fetch_categories(session)]:
        await callback.answer()
        await state.update_data(category=callback.data)
        await callback.message.answer('Now enter the price of the product.')
        await state.set_state(AddProduct.price)
    else:
        await callback.message.answer('Select a category from the buttons.')
        await callback.answer()


# Catch any incorrect actions, except pressing the category selection button
@admin_private_router.message(AddProduct.category)
async def category_choice2(message: types.Message, state: FSMContext):
    await message.answer("Select a category from the buttons.")


# Capture data for the 'price' state and then transition to the 'image' state
@admin_private_router.message(AddProduct.price, F.text)
async def add_price(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(price=AddProduct.product_for_change.price)
    else:
        try:
            float(message.text)
        except ValueError:
            await message.answer("Enter a valid price value")
            return

        await state.update_data(price=message.text)
    await message.answer("Upload the product image")
    await state.set_state(AddProduct.image)


# Handler for catching incorrect input for the 'price' state
@admin_private_router.message(AddProduct.price)
async def add_price2(message: types.Message, state: FSMContext):
    await message.answer("You entered invalid data. Please enter the product price.")


# Capture data for the 'image' state and then exit the states
@admin_private_router.message(AddProduct.image, or_f(F.photo, F.text == "."))
async def add_image(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text == "." and AddProduct.product_for_change:
        await state.update_data(image=AddProduct.product_for_change.image)

    elif message.photo:
        await state.update_data(image=message.photo[-1].file_id)
    else:
        await message.answer("Send the product photo")
        return
    data = await state.get_data()
    try:
        if AddProduct.product_for_change:
            await orm_update_product(session, AddProduct.product_for_change.id, data)
        else:
            await orm_add_product(session, data)
        await message.answer("The product has been added/updated", reply_markup=ADMIN_KB)
        await state.clear()

    except Exception as e:
        await message.answer(
            f"Error: \n{str(e)}\nPlease contact the developer.",
            reply_markup=ADMIN_KB,
        )
        await state.clear()

    AddProduct.product_for_change = None


# Catch all other incorrect behavior for this state
@admin_private_router.message(AddProduct.image)
async def add_image2(message: types.Message, state: FSMContext):
    await message.answer("Send the product photo")
