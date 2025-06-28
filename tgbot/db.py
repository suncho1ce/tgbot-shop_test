import asyncpg
import os
import logging
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'database': os.getenv('POSTGRES_DB'),
    'host': os.getenv('POSTGRES_HOST', 'db'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
}

async def get_pool():
    return await asyncpg.create_pool(**DB_CONFIG)

# --- Пользователи ---
async def add_or_update_user(pool, user_id, username, first_name, last_name, is_subscribed):
    query = """
        INSERT INTO shop_telegramuser (user_id, username, first_name, last_name, is_subscribed, is_active, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, TRUE, NOW(), NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            is_subscribed = EXCLUDED.is_subscribed,
            is_active = TRUE,
            updated_at = NOW();
    """
    await pool.execute(query, user_id, username, first_name, last_name, is_subscribed)

# --- Категории и товары ---
async def fetch_categories(pool, parent_id=None):
    if parent_id is None:
        query = """
            SELECT id, name FROM shop_category
            WHERE is_active = TRUE AND parent_id IS NULL
            ORDER BY sort_order, name
        """
        return await pool.fetch(query)
    else:
        query = """
            SELECT id, name FROM shop_category
            WHERE is_active = TRUE AND parent_id = $1
            ORDER BY sort_order, name
        """
        return await pool.fetch(query, parent_id)

async def fetch_products(pool, category_id):
    query = """
        SELECT id, name, description, image, price FROM shop_product
        WHERE is_active = TRUE AND category_id = $1
        ORDER BY name
    """
    return await pool.fetch(query, category_id)

async def fetch_subcategories(pool, parent_id):
    query = """
        SELECT id, name FROM shop_category
        WHERE is_active = TRUE AND parent_id = $1
        ORDER BY sort_order, name
    """
    return await pool.fetch(query, parent_id)

async def fetch_product(pool, product_id):
    query = """
        SELECT id, name, description, image, price FROM shop_product
        WHERE is_active = TRUE AND id = $1
    """
    return await pool.fetchrow(query, product_id)

# --- Корзина ---
async def fetch_cart(pool, user_id):
    query = """
        SELECT ci.id, p.name, p.price, ci.quantity, ci.product_id
        FROM shop_cartitem ci
        JOIN shop_product p ON ci.product_id = p.id
        WHERE ci.user_id = $1 AND ci.is_active = TRUE
        ORDER BY ci.created_at
    """
    return await pool.fetch(query, user_id)

async def add_to_cart(pool, user_id, product_id, quantity):
    query = """
        INSERT INTO shop_cartitem (user_id, product_id, quantity, is_active, created_at)
        VALUES ($1, $2, $3, TRUE, NOW())
        ON CONFLICT (user_id, product_id) WHERE (is_active = TRUE)
        DO UPDATE SET quantity = shop_cartitem.quantity + EXCLUDED.quantity
        RETURNING id, created_at
    """
    return await pool.fetchrow(query, user_id, product_id, quantity)

async def update_cart_item_quantity(pool, cartitem_id, user_id, change: int):
    """
    Атомарно изменяет количество товара в корзине.
    Если количество становится 0 или меньше, товар удаляется (деактивируется).
    Возвращает новое количество или 0, если товар удален.
    """
    # Атомарно обновляем и получаем новое количество
    logging.info(f"Изменение количества товара {cartitem_id} пользователем {user_id} на {change}")
    query = """
        UPDATE shop_cartitem
        SET quantity = quantity + $1
        WHERE id = $2 AND user_id = $3 AND is_active = TRUE
        RETURNING quantity
    """
    new_quantity = await pool.fetchval(query, change, cartitem_id, user_id)

    # Если после уменьшения кол-во стало 0 или меньше, деактивируем позицию
    if new_quantity is not None and new_quantity <= 0:
        logging.info(f"Удаление товара {cartitem_id} (количество <= 0)")
        await remove_from_cart(pool, cartitem_id, user_id)
        return 0

    return new_quantity

async def remove_from_cart(pool, cartitem_id, user_id):
    query = """
        UPDATE shop_cartitem SET is_active = FALSE
        WHERE id = $1 AND user_id = $2
    """
    logging.info(f"Удаление товара {cartitem_id} пользователем {user_id}")
    await pool.execute(query, cartitem_id, user_id)

async def update_order_status(pool, order_id: int, user_id: int, new_status: str):
    """Обновляет статус заказа для конкретного пользователя."""
    query = "UPDATE shop_order SET status = $1 WHERE id = $2 AND user_id = $3 RETURNING id;"
    updated_id = await pool.fetchval(query, new_status, order_id, user_id)
    logging.info(f"Статус заказа #{order_id} для пользователя {user_id} изменен на '{new_status}'.")
    return updated_id


async def create_order(pool, user_id, delivery_info):
    async with pool.acquire() as connection:
        async with connection.transaction():
            # 1. Получаем активные товары из корзины
            cart_items_query = """
                SELECT ci.product_id, ci.quantity, p.name as product_name, p.price as product_price
                FROM shop_cartitem ci
                JOIN shop_product p ON ci.product_id = p.id
                WHERE ci.user_id = $1 AND ci.is_active = TRUE
            """
            cart_items = await connection.fetch(cart_items_query, user_id)

            if not cart_items:
                return None, []  # Корзина пуста

            # 2. Создаем заказ
            order_query = """
                INSERT INTO shop_order (user_id, delivery_info, status, created_at)
                VALUES ($1, $2, 'created', NOW())
                RETURNING id, created_at, status
            """
            order_record = await connection.fetchrow(order_query, user_id, delivery_info)
            order_id = order_record['id']

            # 3. Создаем OrderItem для каждого товара и собираем данные для возврата
            order_items_data = []
            for item in cart_items:
                await connection.execute(
                    """
                    INSERT INTO shop_orderitem (order_id, product_id, product_name, product_price, quantity, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    """,
                    order_id, item['product_id'], item['product_name'], item['product_price'], item['quantity']
                )
                order_items_data.append(dict(item))

            # 4. Деактивируем товары в корзине
            await connection.execute(
                "UPDATE shop_cartitem SET is_active = FALSE WHERE user_id = $1 AND is_active = TRUE",
                user_id
            )

            return dict(order_record), order_items_data

# --- FAQ ---
async def fetch_faq(pool, search=None):
    if search:
        query = """
            SELECT id, question, answer FROM shop_faq
            WHERE is_active = TRUE AND question ILIKE $1
            ORDER BY id
        """
        return await pool.fetch(query, f"%{search}%")
    else:
        query = """
            SELECT id, question, answer FROM shop_faq
            WHERE is_active = TRUE
            ORDER BY id
        """
        return await pool.fetch(query)

async def search_faq(pool, query=None):
    if query:
        # Поиск по подстроке, началу, концу, части слова, регистронезависимо
        sql = '''
            SELECT id, question FROM shop_faq
            WHERE is_active = TRUE AND (
                question ILIKE $1 OR question ILIKE $2 OR question ILIKE $3 OR question ILIKE $4
            )
            ORDER BY id DESC LIMIT 7
        '''
        q = f"%{query}%"
        q_start = f"{query}%"
        q_end = f"%{query}"
        q_word = f"% {query}%"
        faqs = await pool.fetch(sql, q, q_start, q_end, q_word)
        if faqs:
            return faqs
    # Если ничего не найдено или нет запроса — вернуть топ-3 самых новых FAQ
    faqs = await pool.fetch(
        "SELECT id, question FROM shop_faq WHERE is_active = TRUE ORDER BY id DESC LIMIT 3"
    )
    return faqs

async def get_faq_answer(pool, faq_id):
    sql = """
        SELECT answer FROM shop_faq WHERE id = $1 AND is_active = TRUE
    """
    row = await pool.fetchrow(sql, faq_id)
    return row['answer'] if row else None

async def get_all_faq(pool):
    sql = "SELECT id, question FROM shop_faq WHERE is_active = TRUE ORDER BY id DESC"
    return await pool.fetch(sql)

# --- Рассылки ---
async def get_pending_broadcast(pool):
    """
    Атомарно находит одну рассылку в статусе 'pending'
    и меняет ее статус на 'sending', чтобы другие воркеры ее не взяли.
    """
    query = """
        UPDATE shop_broadcast
        SET status = 'sending'
        WHERE id = (
            SELECT id
            FROM shop_broadcast
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT 1
        )
        RETURNING id, message;
    """
    return await pool.fetchrow(query)

async def get_all_active_users_ids(pool):
    """Получает ID всех активных пользователей."""
    return await pool.fetchval("SELECT array_agg(user_id) FROM shop_telegramuser WHERE is_active = TRUE;")

async def finalize_broadcast(pool, broadcast_id):
    """Обновляет статус рассылки на 'sent' после завершения."""
    query = "UPDATE shop_broadcast SET status = 'sent', sent_at = NOW() WHERE id = $1;"
    await pool.execute(query, broadcast_id)

async def add_recipients_to_broadcast(pool, broadcast_id, user_ids):
    """Добавляет получателей к рассылке."""
    if not user_ids:
        return
    # asyncpg может принимать список кортежей для executemany
    data_to_insert = [(broadcast_id, user_id) for user_id in user_ids]
    await pool.executemany(
        "INSERT INTO shop_broadcast_recipients (broadcast_id, telegramuser_id) VALUES ($1, $2) ON CONFLICT (broadcast_id, telegramuser_id) DO NOTHING;",
        data_to_insert
    )

async def get_broadcast_recipients_from_db(pool, broadcast_id):
    """Получает ID пользователей, указанных в рассылке."""
    query = "SELECT telegramuser_id FROM shop_broadcast_recipients WHERE broadcast_id = $1;"
    # fetch returns records. We need a list of IDs.
    return [r['telegramuser_id'] for r in await pool.fetch(query, broadcast_id)]
