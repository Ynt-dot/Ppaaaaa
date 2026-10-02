from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from .models import (
    Cartoon, UserPreference, SiteSettings, AccountAccessLog,
    BannedIdentifier,
)
from .views import _extract_cartoon_pk_from_link


class SuperuserOnlyAdminMixin:
    """Общий набор проверок прав для админок с чувствительными
    данными (IP-адреса, общесайтовые настройки) - доступ только
    суперпользователю, отклоняется на сервере при каждой проверке, а
    не просто скрывается из меню для рядового стаффа."""

    def _is_superuser(self, request):
        return bool(
            request.user
            and request.user.is_active
            and request.user.is_superuser)

    def has_module_permission(self, request):
        return self._is_superuser(request)

    def has_view_permission(self, request, obj=None):
        return self._is_superuser(request)


@admin.register(Cartoon)
class CartoonAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')


class UserPreferenceInline(admin.StackedInline):
    model = UserPreference
    can_delete = False
    fields = ('display_name', 'description', 'is_troll')


class AccountAccessLogInline(admin.TabularInline):
    """Только для суперпользователя - см.
    CustomUserAdmin.get_inline_instances."""
    model = AccountAccessLog
    extra = 0
    can_delete = False
    fields = (
        'ip_address', 'device_id', 'user_agent', 'first_seen',
        'last_seen', 'visit_count')
    readonly_fields = fields
    verbose_name_plural = "IP-адреса и устройства этого аккаунта"

    def has_add_permission(self, request, obj=None):
        return False


class CustomUserAdmin(UserAdmin):
    inlines = (UserPreferenceInline, AccountAccessLogInline)
    list_display = UserAdmin.list_display + ('is_troll_flag',)

    def is_troll_flag(self, obj):
        pref = getattr(obj, 'preference', None)
        return pref.is_troll if pref else False
    is_troll_flag.short_description = 'Тролль'
    is_troll_flag.boolean = True

    def get_inline_instances(self, request, obj=None):
        instances = super().get_inline_instances(request, obj)
        if request.user.is_superuser:
            return instances
        return [
            i for i in instances
            if not isinstance(i, AccountAccessLogInline)]


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


class SiteSettingsAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    """Синглтон-строка настроек (всегда pk=1). Видеть и трогать её
    может только суперпользователь - не просто скрыта от стаффа в
    интерфейсе, а отклоняется на сервере при каждой проверке прав,
    поскольку то, чем она управляет (аватар по умолчанию для всех
    пользователей без своего), общесайтовое.
    """
    form = SiteSettingsForm
    fields = ('default_avatar_preview', 'default_avatar_link')
    readonly_fields = ('default_avatar_preview',)

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


class AccountAccessLogAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    """Только чтение - записи создаёт middleware
    (AccountAccessLogMiddleware), руками их заводить/трогать не за
    чем. Через поиск/сортировку по IP или device_id админ находит все
    аккаунты, заходившие с одного адреса/устройства - т.е. подборку
    для решения "банить или нет"."""
    list_display = (
        'user', 'ip_address', 'device_id', 'user_agent_short',
        'first_seen', 'last_seen', 'visit_count')
    search_fields = ('user__username', 'ip_address', 'device_id')
    ordering = ('-last_seen',)
    actions = ['ban_selected_ips', 'ban_selected_devices']
    change_list_template = 'admin/cartoons/accountaccesslog_changelist.html'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return self._is_superuser(request)

    def user_agent_short(self, obj):
        return (obj.user_agent[:60] + '…') if len(
            obj.user_agent) > 60 else obj.user_agent
    user_agent_short.short_description = "User-Agent"

    def get_urls(self):
        return [
            path(
                'shared-ips/',
                self.admin_site.admin_view(self.shared_ips_view),
                name='cartoons_accountaccesslog_shared_ips'),
        ] + super().get_urls()

    def shared_ips_view(self, request):
        """IP-адреса, с которых заходило больше одного аккаунта -
        готовая подборка потенциальных мультиаккаунтов.

        admin_view() (обёртка в get_urls) проверяет только
        has_permission сайта (is_active и is_staff) - has_view_permission
        самой этой ModelAdmin для кастомных view не применяется
        автоматически, поэтому проверяем суперпользователя здесь же.
        """
        if not self._is_superuser(request):
            return HttpResponseForbidden(
                'Только суперпользователь может это смотреть.')
        rows = (
            AccountAccessLog.objects
            .values('ip_address')
            .annotate(account_count=Count('user', distinct=True))
            .filter(account_count__gt=1)
            .order_by('-account_count'))
        banned_ips = set(
            BannedIdentifier.objects.filter(
                kind=BannedIdentifier.KIND_IP)
            .values_list('value', flat=True))
        for row in rows:
            row['accounts'] = list(
                User.objects.filter(
                    access_logs__ip_address=row['ip_address'])
                .distinct())
            row['is_banned'] = row['ip_address'] in banned_ips
        context = {
            **self.admin_site.each_context(request),
            'title': "IP-адреса с несколькими аккаунтами",
            'rows': rows,
            'opts': self.model._meta,
        }
        return render(
            request, 'admin/cartoons/shared_ips.html', context)

    @admin.action(description="Забанить выбранные IP-адреса")
    def ban_selected_ips(self, request, queryset):
        if not self._is_superuser(request):
            return
        ips = queryset.values_list('ip_address', flat=True).distinct()
        created = 0
        for ip in ips:
            _, was_created = BannedIdentifier.objects.get_or_create(
                kind=BannedIdentifier.KIND_IP, value=ip,
                defaults={'banned_by': request.user})
            created += int(was_created)
        self.message_user(
            request, f"Забанено новых IP-адресов: {created}")

    @admin.action(description="Забанить выбранные device_id")
    def ban_selected_devices(self, request, queryset):
        if not self._is_superuser(request):
            return
        device_ids = queryset.exclude(device_id='').values_list(
            'device_id', flat=True).distinct()
        created = 0
        for device_id in device_ids:
            _, was_created = BannedIdentifier.objects.get_or_create(
                kind=BannedIdentifier.KIND_DEVICE, value=device_id,
                defaults={'banned_by': request.user})
            created += int(was_created)
        self.message_user(
            request, f"Забанено новых устройств: {created}")


admin.site.register(AccountAccessLog, AccountAccessLogAdmin)


class BannedIdentifierAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('kind', 'value', 'reason', 'banned_by', 'banned_at')
    list_filter = ('kind',)
    search_fields = ('value', 'reason')
    readonly_fields = ('banned_by', 'banned_at')

    def has_add_permission(self, request):
        return self._is_superuser(request)

    def has_change_permission(self, request, obj=None):
        return self._is_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_superuser(request)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.banned_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(BannedIdentifier, BannedIdentifierAdmin)
