from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Cartoon, UserPreference


@admin.register(Cartoon)
class CartoonAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')


class UserPreferenceInline(admin.StackedInline):
    model = UserPreference
    can_delete = False
    fields = ('profile_slug', 'description', 'is_troll')


class CustomUserAdmin(UserAdmin):
    inlines = (UserPreferenceInline,)
    list_display = UserAdmin.list_display + ('is_troll_flag',)

    def is_troll_flag(self, obj):
        pref = getattr(obj, 'preference', None)
        return pref.is_troll if pref else False
    is_troll_flag.short_description = 'Тролль'
    is_troll_flag.boolean = True


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
