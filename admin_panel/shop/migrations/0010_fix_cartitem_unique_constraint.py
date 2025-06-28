from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0009_broadcast_recipients"),
    ]

    operations = [
        # Сначала удаляем старый, некорректный индекс
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS cartitem_user_product_active_idx;",
            reverse_sql="""
                CREATE UNIQUE INDEX IF NOT EXISTS cartitem_user_product_active_idx
                ON shop_cartitem (user_id, product_id, is_active);
            """
        ),
        # Затем создаем новый, частичный уникальный индекс, который применяется только к активным товарам
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX cartitem_user_product_active_idx
                ON shop_cartitem (user_id, product_id)
                WHERE (is_active = TRUE);
            """,
            reverse_sql="DROP INDEX IF EXISTS cartitem_user_product_active_idx;"
        ),
    ]
