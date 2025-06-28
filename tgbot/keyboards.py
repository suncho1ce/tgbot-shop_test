from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍️ Каталог")],
        [KeyboardButton(text="🛒 Корзина")],
        [KeyboardButton(text="❓ FAQ")],
    ],
    resize_keyboard=True
)

def get_inline_categories(categories, parent_prefix="cat", page=1, per_page=5, parent_id_for_cb=None):
    if not categories:
        return None

    # Для пагинации по подкатегориям нам нужно передавать ID родителя в callback_data
    cb_prefix = parent_prefix
    if parent_prefix == 'subcat' and parent_id_for_cb:
        cb_prefix = f"subcat_{parent_id_for_cb}"

    buttons = [
        [InlineKeyboardButton(text=cat['name'], callback_data=f"{parent_prefix}_{cat['id']}")]
        for cat in categories[(page-1)*per_page:page*per_page]
    ]
    # Пагинация
    if len(categories) > page*per_page:
        buttons.append([InlineKeyboardButton(text="Далее ▶️", callback_data=f"{cb_prefix}_page_{page+1}")])
    if page > 1:
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"{cb_prefix}_page_{page-1}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

def get_inline_products(products):
    if not products:
        return None
    buttons = [
        [InlineKeyboardButton(text=prod['name'], callback_data=f"product_{prod['id']}")]
        for prod in products
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

def get_add_to_cart_keyboard(product_id):
    if not product_id:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить в корзину", callback_data=f"addcart_{product_id}")]
    ])

def get_quantity_keyboard(product_id, max_qty=10):
    buttons = []
    row = []
    for i in range(1, max_qty+1):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"qty_{product_id}_{i}"))
        if i % 5 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

def get_confirm_keyboard(product_id, qty):
    buttons = [
        [InlineKeyboardButton(text=f"✅ Добавить {qty} шт.", callback_data=f"confirm_{product_id}_{qty}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_keyboard(cart_items):
    if not cart_items:
        return None
    buttons = []
    for item in cart_items:
        # Ряд 1: Название товара (кнопка ведет на карточку товара)
        buttons.append([
            InlineKeyboardButton(
                text=item['name'],
                callback_data=f"product_{item['product_id']}"
            )
        ])
        # Ряд 2: Управление количеством и удаление
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"cart_decr_{item['id']}"),
            InlineKeyboardButton(text=f"{item['quantity']} шт.", callback_data="cart_noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_incr_{item['id']}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"delcart_{item['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="💳 Оформить заказ", callback_data="order")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_keyboard(order_id: int, total_cost: float, payment_url: str):
    """Создает клавиатуру для оплаты с реальной ссылкой и кнопкой-заглушкой."""
    buttons = [
        [InlineKeyboardButton(text=f"Оплатить {total_cost:.2f} ₽", url=payment_url)],
        # Кнопка-заглушка для имитации ответа от платежной системы
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data=f"paid_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_to_faq_keyboard():
    """Создает клавиатуру для возврата к списку FAQ или в главное меню."""
    buttons = [
        [
            InlineKeyboardButton(text="⬅️ Назад к вопросам", callback_data="faq_back_to_list"),
            InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_faq_keyboard(faqs, show_all_button=True):
    buttons = [
        [InlineKeyboardButton(text=faq['question'], callback_data=f"faq_{faq['id']}")]
        for faq in faqs
    ]
    if show_all_button:
        buttons.append([InlineKeyboardButton(text="📖 Показать все статьи", callback_data="faq_all")])
    if not buttons or (not faqs and not show_all_button):
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)
