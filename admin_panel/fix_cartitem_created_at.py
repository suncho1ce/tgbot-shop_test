from shop.models import CartItem
from django.utils import timezone

def fix_null_created_at():
    updated = CartItem.objects.filter(created_at__isnull=True).update(created_at=timezone.now())
    print(f"Updated {updated} cart items with null created_at.")

if __name__ == "__main__":
    fix_null_created_at()
