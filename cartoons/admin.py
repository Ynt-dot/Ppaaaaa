from django.contrib import admin
from .models import Cartoon


@admin.register(Cartoon)
class CartoonAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')
