from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE UNIQUE INDEX IF NOT EXISTS cartitem_user_product_active_idx
            ON shop_cartitem (user_id, product_id, is_active);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS cartitem_user_product_active_idx;
            """
        ),
    ]
