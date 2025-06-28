# c:/Users/admin/PythonProjects/tgbot_shop_test/admin_panel/shop/migrations/0003_fix_created_at_defaults.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0002_cartitem_unique_index"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE shop_order ALTER COLUMN created_at SET DEFAULT NOW();
            ALTER TABLE shop_cartitem ALTER COLUMN created_at SET DEFAULT NOW();
            """,
            reverse_sql="""
            ALTER TABLE shop_order ALTER COLUMN created_at DROP DEFAULT;
            ALTER TABLE shop_cartitem ALTER COLUMN created_at DROP DEFAULT;
            """
        ),
    ]
