from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.utils.html import format_html
from .models import Cartoon, UserPreference, SiteSettings
from .views import _extract_cartoon_pk_from_link


@admin.register(Cartoon)
class CartoonAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')


class UserPreferenceInline(admin.StackedInline):
    model = UserPreference
    can_delete = False
    fields = ('display_name', 'description', 'is_troll')


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


class SiteSettingsForm(forms.ModelForm):
    default_avatar_link = forms.CharField(
        required=False,
        label="Ссылка на мульт",
        help_text="Вставьте ссылку на мульт (например, .../cartoon/123/) "
                  "и сохраните - откроется страница обрезки аватара. "
                  "Аватаром по умолчанию может стать мульт любого "
                  "пользователя.")

    class Meta:
        model = SiteSettings
        fields = ()


class SiteSettingsAdmin(admin.ModelAdmin):
    """Синглтон-строка настроек (всегда pk=1). Видеть и трогать её
    может только суперпользователь - не просто скрыта от стаффа в
    интерфейсе, а отклоняется на сервере при каждой проверке прав,
    поскольку то, чем она управляет (аватар по умолчанию для всех
    пользователей без своего), общесайтовое.
    """
    form = SiteSettingsForm
    fields = ('default_avatar_preview', 'default_avatar_link')
    readonly_fields = ('default_avatar_preview',)

    def _is_superuser(self, request):
        return bool(
            request.user
            and request.user.is_active
            and request.user.is_superuser)

    def has_module_permission(self, request):
        return self._is_superuser(request)

    def has_view_permission(self, request, obj=None):
        return self._is_superuser(request)

    def has_change_permission(self, request, obj=None):
        return self._is_superuser(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def default_avatar_preview(self, obj):
        if obj and obj.default_avatar_gif:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;'
                'border-radius:50%;object-fit:cover;">',
                obj.default_avatar_gif.url)
        return "Не задан - используется стандартная картинка"
    default_avatar_preview.short_description = "Текущий аватар по умолчанию"

    def changelist_view(self, request, extra_context=None):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        return redirect('admin:cartoons_sitesettings_change', obj.pk)

    def response_change(self, request, obj):
        link = request.POST.get('default_avatar_link', '').strip()
        if link:
            cartoon_pk = _extract_cartoon_pk_from_link(link)
            if cartoon_pk is None or not Cartoon.objects.filter(
                    pk=cartoon_pk).exists():
                self.message_user(
                    request,
                    'Не удалось распознать ссылку на мульт - '
                    'проверьте, что она правильная.',
                    level=messages.ERROR)
                return redirect(request.path)
            return redirect('admin_default_avatar_crop', pk=cartoon_pk)
        return super().response_change(request, obj)


admin.site.register(SiteSettings, SiteSettingsAdmin)
