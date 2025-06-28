from django.core.management.base import BaseCommand
from shop.models import Category

class Command(BaseCommand):
    help = 'Загружает тестовые данные для пагинации в каталоге'

    def handle(self, *args, **options):
        self.stdout.write('Начинаю загрузку тестовых данных...')

        # Создаем основную категорию для тестов, если ее нет
        parent_cat, created = Category.objects.get_or_create(
            name="Тестовые категории для пагинации",
            defaults={'sort_order': 100, 'is_active': True}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Создана родительская категория: "{parent_cat.name}"'))
        else:
            self.stdout.write(f'Родительская категория "{parent_cat.name}" уже существует.')

        # Создаем 15 подкатегорий, если их нет
        created_count = 0
        for i in range(1, 16):
            _, created = Category.objects.get_or_create(
                name=f"Подкатегория {i}",
                parent=parent_cat,
                defaults={'sort_order': i, 'is_active': True}
            )
            if created:
                created_count += 1
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Создано {created_count} новых тестовых подкатегорий.'))
        else:
            self.stdout.write('Все тестовые подкатегории уже существуют.')

        self.stdout.write(self.style.SUCCESS('Загрузка тестовых данных завершена.'))

