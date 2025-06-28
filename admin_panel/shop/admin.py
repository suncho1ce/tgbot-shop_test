from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Sum, F, Count, OuterRef, Subquery, Max
from django.urls import reverse
from django.utils.http import urlencode
from .models import Category, Product, FAQ, CartItem, Order, OrderItem, TelegramUser, Broadcast

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active", "image_thumbnail")
    list_filter = ("category", "is_active")
    search_fields = ("name",)

    def image_thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "–"
    image_thumbnail.short_description = 'Изображение'

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "is_active")
    list_filter = ("is_active",)
    search_fields = ("question",)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'product_price', 'quantity')
    can_delete = False

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user_id", "product", "quantity", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user_id",)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "status", "order_summary", "total_cost_display", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "user_id",)
    ordering = ('-id',)
    inlines = [OrderItemInline]
    readonly_fields = ('total_cost_display',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related('items').annotate(
            total_cost=Sum(F('items__product_price') * F('items__quantity'))
        )
        return queryset

    def order_summary(self, obj):
        summary = ", ".join(
            f"{item.product_name} ({item.quantity} шт.)" for item in obj.items.all()
        )
        return summary if summary else "–"
    order_summary.short_description = 'Состав заказа'

    def total_cost_display(self, obj):
        return f"{obj.total_cost} ₽" if obj.total_cost is not None else "0.00 ₽"
    total_cost_display.short_description = 'Сумма заказа'
    total_cost_display.admin_order_field = 'total_cost'

@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = (
        'user_id', 'username', 'first_name', 'is_subscribed', 'order_count_link',
        'total_spent_display', 'last_order_date_display', 'broadcast_count_link', 'updated_at'
    )
    list_filter = ('is_subscribed', 'is_active',)
    search_fields = ('user_id', 'username', 'first_name', 'last_name')
    ordering = ('-updated_at',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # Subquery для подсчета заказов
        order_count_subquery = Order.objects.filter(
            user_id=OuterRef('pk')
        ).values('user_id').annotate(c=Count('pk')).values('c')

        # Subquery для подсчета общей суммы
        total_spent_subquery = OrderItem.objects.filter(
            order__user_id=OuterRef('pk')
        ).values('order__user_id').annotate(
            total=Sum(F('product_price') * F('quantity'))
        ).values('total')

        # Subquery для получения даты последнего заказа
        last_order_date_subquery = Order.objects.filter(
            user_id=OuterRef('pk')
        ).values('user_id').annotate(last_date=Max('created_at')).values('last_date')

        return queryset.annotate(
            order_count=Subquery(order_count_subquery),
            total_spent=Subquery(total_spent_subquery),
            last_order_date=Subquery(last_order_date_subquery),
            broadcast_count=Count('broadcasts', distinct=True),
        )

    @admin.display(description='Заказы', ordering='order_count')
    def order_count_link(self, obj):
        count = obj.order_count or 0
        url = reverse("admin:shop_order_changelist") + "?" + urlencode({"user_id__exact": f"{obj.user_id}"})
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description='Общая сумма', ordering='total_spent')
    def total_spent_display(self, obj):
        return f"{obj.total_spent or '0.00'} ₽"

    @admin.display(description='Последний заказ', ordering='last_order_date')
    def last_order_date_display(self, obj):
        return obj.last_order_date.strftime("%d.%m.%Y %H:%M") if obj.last_order_date else "–"

    @admin.display(description='Рассылок получено', ordering='broadcast_count')
    def broadcast_count_link(self, obj):
        count = obj.broadcast_count or 0
        url = (
            reverse("admin:shop_broadcast_changelist")
            + "?"
            + urlencode({"recipients__user_id": f"{obj.user_id}"})
        )
        return format_html('<a href="{}">{}</a>', url, count)

@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'recipient_count_display', 'created_at', 'sent_at')
    list_filter = ('status',)
    actions = ['schedule_for_sending']
    readonly_fields = ('sent_at', 'status')
    filter_horizontal = ('recipients',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(recipient_count=Count('recipients'))

    @admin.display(description='Получателей', ordering='recipient_count')
    def recipient_count_display(self, obj):
        return obj.recipient_count

    @admin.action(description="Поставить в очередь на отправку")
    def schedule_for_sending(self, request, queryset):
        # Ставим в очередь только черновики
        count = queryset.filter(status='draft').update(status='pending')
        self.message_user(
            request, f"{count} рассылок поставлено в очередь на отправку.", messages.SUCCESS
        )
