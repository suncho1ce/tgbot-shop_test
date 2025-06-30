import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramForbiddenError
from decimal import Decimal
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
import os
from dotenv import load_dotenv
from keyboards import main_menu, get_inline_categories, get_inline_products, get_add_to_cart_keyboard, get_quantity_keyboard, get_confirm_keyboard, get_cart_keyboard, get_faq_keyboard, get_payment_keyboard, get_back_to_faq_keyboard
from db import (get_pool, fetch_categories, fetch_subcategories, fetch_products, fetch_product, fetch_cart, add_to_cart, remove_from_cart, create_order, search_faq, get_faq_answer, get_all_faq, add_or_update_user, get_pending_broadcast, get_all_active_users_ids, finalize_broadcast, add_recipients_to_broadcast, get_broadcast_recipients_from_db, update_cart_item_quantity, update_order_status)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from excel_export import append_order_to_excel

load_dotenv()

API_TOKEN = os.getenv("TG_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
 
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramBadRequest as e:
        logging.critical(f"CRITICAL: Subscription check failed due to bad request. Check if bot is admin in the channel {CHANNEL_ID}. Error: {e}")
        # Если бот не в канале или канал указан неверно, доступ не предоставляем.
        return False
    except Exception as e:
        logging.error(f"Unexpected error in subscription check for user {user_id}: {e}")
        return False

@dp.startup()
async def on_startup(dispatcher):
    pool = await get_pool()
    dispatcher.workflow_data["pool"] = pool
    logging.info("DB pool created")
    # Запускаем фоновую задачу для мониторинга рассылок
    asyncio.create_task(broadcast_scheduler(pool))

@dp.shutdown()
async def on_shutdown(dispatcher):
    pool = dispatcher.workflow_data.get("pool")
    if pool:
        await pool.close()
        logging.info("DB pool closed")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, pool):
    # 1. Проверяем подписку
    subscribed = await check_subscription(message.from_user.id)

    # 2. Сохраняем/обновляем информацию о пользователе, включая статус подписки
    await add_or_update_user(
        pool, message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        subscribed
    )
    if not subscribed:
        text = "Для доступа к магазину, пожалуйста, подпишитесь на наш канал."
        # Если ссылка на канал есть в .env, создаем кнопку
        if CHANNEL_LINK:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Перейти к каналу", url=CHANNEL_LINK)]
            ])
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=types.ReplyKeyboardRemove())
        return
    await message.answer(
        "👋 Добро пожаловать в интернет-магазин!\nВыберите действие:",
        reply_markup=main_menu
    )

@dp.message(F.text == "🛍️ Каталог")
async def catalog_handler(message: types.Message, pool):
    cats = await fetch_categories(pool)
    kb = get_inline_categories(cats)
    if not kb:
        await message.answer("Категории не найдены.")
        return
    await message.answer("📁 Выберите категорию:", reply_markup=kb)

@dp.callback_query(F.data.regexp(r"^(cat|subcat_\d+)_page_(\d+)$"))
async def category_page_callback(call: types.CallbackQuery, pool):
    prefix_part, page_str = call.data.rsplit("_page_", 1)
    page = int(page_str)

    if prefix_part == 'cat':
        # Пагинация по основным категориям
        items = await fetch_categories(pool)
        kb = get_inline_categories(items, parent_prefix="cat", page=page)
        await call.message.edit_text("📁 Выберите категорию:", reply_markup=kb)

    elif prefix_part.startswith("subcat_"):
        # Пагинация по подкатегориям
        parent_id = int(prefix_part.split("_")[1])
        items = await fetch_subcategories(pool, parent_id)
        kb = get_inline_categories(items, parent_prefix="subcat", page=page, parent_id_for_cb=parent_id)
        await call.message.edit_text("📂 Выберите подкатегорию:", reply_markup=kb)
    
    await call.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def category_callback(call: types.CallbackQuery, pool):
    cat_id = int(call.data.split("_")[1])
    subcats = await fetch_subcategories(pool, cat_id)
    kb = get_inline_categories(subcats, parent_prefix="subcat", parent_id_for_cb=cat_id)
    if kb:
        await call.message.edit_text("📂 Выберите подкатегорию:", reply_markup=kb)
        return
    products = await fetch_products(pool, cat_id)
    kb = get_inline_products(products)
    if not kb:
        await call.message.edit_text("В этой категории пока нет товаров.")
        return
    await call.message.edit_text("🏷️ Товары:", reply_markup=kb)

@dp.callback_query(F.data.startswith("subcat_"))
async def subcategory_callback(call: types.CallbackQuery, pool):
    cat_id = int(call.data.split("_")[1])
    products = await fetch_products(pool, cat_id)
    kb = get_inline_products(products)
    if not kb:
        await call.message.edit_text("В этой подкатегории пока нет товаров.")
        return
    await call.message.edit_text("🏷️ Товары:", reply_markup=kb)

@dp.callback_query(F.data.startswith("product_"))
async def product_callback(call: types.CallbackQuery, pool):
    prod_id = int(call.data.split("_")[1])
    prod = await fetch_product(pool, prod_id)
    if not prod:
        await call.answer("Товар не найден.", show_alert=True)
        return
    text = f"<b>{prod['name']}</b>\nЦена: {prod['price']}₽\n\n{prod['description']}"
    kb = get_add_to_cart_keyboard(prod_id)

    image_path = os.path.join('/app/media', prod['image']) if prod.get('image') else None

    if image_path and os.path.exists(image_path):
        photo_to_send = FSInputFile(image_path)
        await call.message.answer_photo(photo_to_send, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        if image_path:
            logging.warning(f"Image file not found at path: {image_path}")
        await call.message.answer(f"🖼️ [фото не доступно]\n{text}", reply_markup=kb if kb else None, parse_mode=ParseMode.HTML)
    await call.answer()

@dp.callback_query(F.data.startswith("addcart_"))
async def addcart_callback(call: types.CallbackQuery):
    prod_id = int(call.data.split("_")[1])
    # Заменяем клавиатуру в текущем сообщении, не создавая новое
    await call.message.edit_reply_markup(reply_markup=get_quantity_keyboard(prod_id))
    await call.answer()

@dp.callback_query(F.data.startswith("qty_"))
async def quantity_callback(call: types.CallbackQuery):
    _, prod_id, qty = call.data.split("_")
    text = f"Добавить {qty} шт. в корзину?"
    kb = get_confirm_keyboard(int(prod_id), int(qty))

    # Проверяем, есть ли у сообщения фото. Если да, редактируем подпись (caption).
    if call.message.photo:
        await call.message.edit_caption(caption=text, reply_markup=kb)
    # Если это текстовое сообщение, редактируем текст.
    else:
        await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_callback(call: types.CallbackQuery, pool):
    _, prod_id, qty = call.data.split("_")
    prod_id = int(prod_id)
    qty = int(qty)
    await add_to_cart(pool, call.from_user.id, prod_id, qty)
    await call.answer("Товар добавлен в корзину")
    # Обновляем сообщение, чтобы показать корзину
    await update_cart_message(call, pool)

async def format_cart_text(items: list) -> str:
    """Форматирует текст для сообщения с корзиной."""
    if not items:
        return "🛒 Ваша корзина пуста."

    text_lines = ["<b>🛒 Ваша корзина:</b>"]
    total_cost = Decimal(0)

    for item in items:
        item_price = Decimal(item['price'])
        item_quantity = item['quantity']
        position_cost = item_price * item_quantity
        total_cost += position_cost
        text_lines.append(
            f"• {item['name']} ({item_quantity} шт. × {item_price:.2f}₽) = <b>{position_cost:.2f}₽</b>"
        )

    text_lines.append(f"\n<b>Итого: {total_cost:.2f}₽</b>")
    return "\n".join(text_lines)

class OrderForm(StatesGroup):
    delivery = State()

@dp.message(F.text == "🛒 Корзина")
async def cart_handler(message: types.Message, pool):
    items = await fetch_cart(pool, message.from_user.id)
    text = await format_cart_text(items)
    await message.answer(text, reply_markup=get_cart_keyboard(items))

async def update_cart_message(call: types.CallbackQuery, pool):
    """Обновляет сообщение с корзиной, игнорируя ошибку 'message is not modified'."""
    items = await fetch_cart(pool, call.from_user.id)
    text = await format_cart_text(items)
    kb = get_cart_keyboard(items)
    try:
        # Если у исходного сообщения есть фото, мы не можем его отредактировать в текстовое.
        # Поэтому мы удаляем старое сообщение (карточку товара) и отправляем новое (корзину).
        if call.message.photo:
            await call.message.delete()
            await call.message.answer(text, reply_markup=kb)
        else:
            await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logging.error(f"Error updating cart message: {e}")
            await call.answer("Произошла ошибка.", show_alert=True)

@dp.callback_query(F.data == "cart_noop")
async def cart_noop_callback(call: types.CallbackQuery):
    """Пустой обработчик для кнопок, которые не должны ничего делать (например, отображение кол-ва)."""
    await call.answer()

@dp.callback_query(F.data.startswith(("cart_incr_", "cart_decr_")))
async def cart_quantity_callback(call: types.CallbackQuery, pool):
    _, action, cartitem_id_str = call.data.split("_")
    cartitem_id = int(cartitem_id_str)
    change = 1 if action == "incr" else -1
    await update_cart_item_quantity(pool, cartitem_id, call.from_user.id, change)
    await update_cart_message(call, pool)
    await call.answer()  # Убедитесь, что ответ отправлен

@dp.callback_query(F.data.startswith("delcart_"))
async def delcart_callback(call: types.CallbackQuery, pool):
    cartitem_id = int(call.data.split("_")[1])
    await remove_from_cart(pool, cartitem_id, call.from_user.id)
    await call.answer("Товар удалён из корзины.")
    await update_cart_message(call, pool)


@dp.callback_query(F.data == "order")
async def order_callback(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите адрес или данные для доставки:")
    await state.set_state(OrderForm.delivery)
    await call.answer()

@dp.message(OrderForm.delivery)
async def process_delivery(message: types.Message, state: FSMContext, pool):
    delivery_info = message.text
    try:
        order, order_items = await create_order(pool, message.from_user.id, delivery_info)
        if not order or not order_items:
            await message.answer("Не удалось создать заказ. Возможно, ваша корзина пуста.")
            await state.clear()
            return

        # Синхронная операция экспорта в Excel
        await asyncio.to_thread(
            append_order_to_excel,
            order['id'],
            message.from_user.id,
            delivery_info,
            order['created_at'],
            order['status'],
            order_items
        )

        # --- Заглушка для оплаты ---
        total_cost = sum(Decimal(item['product_price']) * item['quantity'] for item in order_items)
        payment_url = f"https://example.com/pay?order_id={order['id']}"  # ЗАГЛУШКА

        await message.answer(
            f"✅ Заказ #{order['id']} успешно создан.\n\n"
            "Для завершения, пожалуйста, оплатите его.",
            reply_markup=get_payment_keyboard(order['id'], total_cost, payment_url)
        )
        # --- Конец заглушки ---
    except Exception as e:
        logging.error(f"Failed to create order for user {message.from_user.id}: {e}")
        await message.answer("Произошла ошибка при оформлении заказа. Пожалуйста, попробуйте позже.")
    finally:
        await state.clear()

@dp.callback_query(F.data.startswith("paid_"))
async def paid_callback(call: types.CallbackQuery, pool):
    """Обработчик-заглушка для подтверждения оплаты."""
    order_id = int(call.data.split("_")[1])

    # Обновляем статус заказа в БД
    updated_order_id = await update_order_status(pool, order_id, call.from_user.id, 'paid')

    if updated_order_id:
        # Редактируем исходное сообщение, убирая кнопки
        await call.message.edit_text(
            f"✅ Заказ #{order_id} успешно оплачен!\n\n"
            "Спасибо за покупку! Мы скоро свяжемся с вами для уточнения деталей."
        )
        # Отправляем новое сообщение с главным меню
        await call.message.answer("Вы можете продолжить покупки.", reply_markup=main_menu)
    else:
        await call.answer("Не удалось обновить статус заказа. Пожалуйста, свяжитесь с поддержкой.", show_alert=True)
    await call.answer()

class FAQForm(StatesGroup):
    question = State()

@dp.message(F.text == "❓ FAQ")
async def faq_handler(message: types.Message, state: FSMContext, pool):
    faqs = await search_faq(pool, None)
    await message.answer(
        "❓ Введите ваш вопрос или выберите из популярных:",
        reply_markup=get_faq_keyboard(faqs)
    )
    await state.set_state(FAQForm.question)

@dp.message(FAQForm.question)
async def faq_search(message: types.Message, state: FSMContext, pool):
    faqs = await search_faq(pool, message.text)
    kb = get_faq_keyboard(faqs)
    if not kb:
        await message.answer("Нет подходящих статей. Попробуйте 'Показать все статьи'.")
        await state.clear()
        return
    await message.answer("Возможно, вы имели в виду:", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data.regexp(r"^faq_\d+$"))
async def faq_answer_callback(call: types.CallbackQuery, pool):
    faq_id = int(call.data.split("_")[1])
    answer = await get_faq_answer(pool, faq_id)
    kb = get_back_to_faq_keyboard()
    if answer:
        await call.message.edit_text(answer, reply_markup=kb)
    else:
        await call.message.edit_text("Ответ не найден.", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "faq_all")
async def faq_all_callback(call: types.CallbackQuery, pool):
    faqs = await get_all_faq(pool)
    kb = get_faq_keyboard(faqs, show_all_button=False)
    if not faqs:
        await call.message.edit_text("Статей пока нет.")
        await call.answer()
        return
    await call.message.edit_text("Все статьи:", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "faq_back_to_list")
async def faq_back_to_list_callback(call: types.CallbackQuery, pool):
    """Handles the 'Back to questions' button press."""
    faqs = await get_all_faq(pool)
    kb = get_faq_keyboard(faqs, show_all_button=False)
    if not faqs:
        await call.message.edit_text("Статей пока нет.")
    else:
        await call.message.edit_text("Все статьи:", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu_callback(call: types.CallbackQuery):
    """Handles the 'To main menu' button press."""
    await call.message.delete()
    await call.message.answer(
        "👋 Добро пожаловать в интернет-магазин!\nВыберите действие:",
        reply_markup=main_menu
    )
    await call.answer()

async def broadcast_scheduler(pool):
    """Периодически проверяет и отправляет рассылки."""
    while True:
        try:
            broadcast = await get_pending_broadcast(pool)
            if broadcast:
                broadcast_id = broadcast['id']
                logging.info(f"Начинаю рассылку #{broadcast_id}...")
 
                # Определяем, кому отправлять рассылку
                explicit_recipients = await get_broadcast_recipients_from_db(pool, broadcast_id)
                
                if explicit_recipients:
                    user_ids = explicit_recipients
                    should_add_recipients_to_db = False # Получатели уже выбраны в админке
                else:
                    user_ids = await get_all_active_users_ids(pool)
                    should_add_recipients_to_db = True # Отправляем всем, нужно записать получателей
 
                if not user_ids:
                    logging.warning(f"Рассылка #{broadcast_id}: нет пользователей для отправки. Завершаю.")
                    await finalize_broadcast(pool, broadcast_id)
                    continue
 
                sent_user_ids = []
                for user_id in user_ids:
                    try:
                        await bot.send_message(chat_id=user_id, text=broadcast['message'])
                        sent_user_ids.append(user_id)
                        await asyncio.sleep(0.1)  # Задержка для избежания лимитов Telegram
                    except (TelegramForbiddenError, TelegramBadRequest):
                        logging.warning(f"Не удалось отправить сообщение пользователю {user_id}. Он заблокировал бота.")
                
                if should_add_recipients_to_db and sent_user_ids:
                    await add_recipients_to_broadcast(pool, broadcast_id, sent_user_ids) # Записываем получателей только если отправляли всем
                
                await finalize_broadcast(pool, broadcast_id)
                logging.info(f"Рассылка #{broadcast_id} завершена. Отправлено: {len(sent_user_ids)}.")
        except Exception as e:
            logging.error(f"Ошибка в планировщике рассылок: {e}")
        
        await asyncio.sleep(60) # Проверка раз в минуту

async def main():
    # on_startup будет вызван внутри start_polling и создаст пул соединений.
    # Aiogram DI (Dependency Injection) автоматически передаст этот пул
    # в хендлеры, у которых есть аргумент 'pool'.
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
