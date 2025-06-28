from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='subcategories', on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Изображение')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.name

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'

    def __str__(self):
        return self.question

class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, primary_key=True, verbose_name='ID пользователя Telegram')
    username = models.CharField(max_length=100, null=True, blank=True, verbose_name='Имя пользователя Telegram')
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    last_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Фамилия')
    is_subscribed = models.BooleanField(default=False, verbose_name='Подписан на канал')
    is_active = models.BooleanField(default=True, verbose_name='Активен') # Можно использовать для блокировки
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Последнее обновление')

    class Meta:
        verbose_name = 'Пользователь Telegram'
        verbose_name_plural = 'Пользователи Telegram'

    def __str__(self):
        return f"@{self.username}" if self.username else f"ID: {self.user_id}"

class CartItem(models.Model):
    user_id = models.BigIntegerField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Товар в корзине'
        verbose_name_plural = 'Корзина'

class Order(models.Model):
    user_id = models.BigIntegerField()
    delivery_info = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, default='created')

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f"Order #{self.id} ({self.user_id})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Элемент заказа'
        verbose_name_plural = 'Элементы заказа'

    def __str__(self):
        return f"{self.product_name} ({self.quantity} шт.) для Заказа #{self.order.id}"

class Broadcast(models.Model):
    message = models.TextField(verbose_name='Текст сообщения')
    recipients = models.ManyToManyField(
        'TelegramUser',
        blank=True,
        verbose_name='Получатели',
        related_name='broadcasts'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отправки')
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Черновик'),
            ('pending', 'Ожидает отправки'),
            ('sending', 'В процессе'),
            ('sent', 'Отправлено'),
        ],
        default='draft',
        verbose_name='Статус'
    )

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'
        ordering = ['-created_at']

    def __str__(self):
        return f"Рассылка от {self.created_at.strftime('%d.%m.%Y %H:%M')}"
