import uuid

from axes.helpers import get_client_ip_address, get_client_user_agent
from django.db.models import F, Q
from django.http import HttpResponseForbidden
from django.utils import timezone

from .models import AccountAccessLog, BannedIdentifier

DEVICE_COOKIE_NAME = 'device_id'
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 5  # 5 лет
LOG_REFRESH_INTERVAL = timezone.timedelta(hours=1)


class AccountAccessLogMiddleware:
    """Две задачи в одном месте:

    1. Блокирует запросы с IP или device_id (кука), забаненных
       вручную в админке (BannedIdentifier) - до того, как запрос
       дойдёт до view, независимо от того, авторизован ли посетитель.
    2. Для авторизованных пользователей ведёт AccountAccessLog: с
       каких IP/устройств заходил конкретный аккаунт - админ потом
       может найти по IP все аккаунты, которые с него заходили
       (мультиаккаунты, обход бана).

    device_id - случайный UUID в cookie-файле, выставляется при
    первом визите; не привязан к аккаунту и переживает выход из
    системы, поэтому годится как ещё один (более слабый - куки
    вырезаются, VPN-адреса разбросаны) сигнал помимо IP.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip_address(request)
        device_id = request.COOKIES.get(DEVICE_COOKIE_NAME, '')
        needs_cookie = not device_id
        if needs_cookie:
            device_id = uuid.uuid4().hex

        if self._is_banned(ip, device_id):
            return HttpResponseForbidden(
                'Доступ к сайту с этого адреса/устройства ограничен.')

        response = self.get_response(request)

        if request.user.is_authenticated and ip:
            self._log_access(request.user, ip, device_id, request)

        if needs_cookie:
            response.set_cookie(
                DEVICE_COOKIE_NAME, device_id,
                max_age=DEVICE_COOKIE_MAX_AGE,
                httponly=True, samesite='Lax')
        return response

    @staticmethod
    def _is_banned(ip, device_id):
        if not ip and not device_id:
            return False
        condition = Q(pk__in=[])
        if ip:
            condition |= Q(kind=BannedIdentifier.KIND_IP, value=ip)
        if device_id:
            condition |= Q(
                kind=BannedIdentifier.KIND_DEVICE, value=device_id)
        return BannedIdentifier.objects.filter(condition).exists()

    @staticmethod
    def _log_access(user, ip, device_id, request):
        user_agent = get_client_user_agent(request)
        log, created = AccountAccessLog.objects.get_or_create(
            user=user, ip_address=ip,
            defaults={'device_id': device_id, 'user_agent': user_agent})
        if created:
            return
        # Не пишем в БД на каждый запрос - только если прошло
        # достаточно времени с прошлой засечки этой же пары.
        if timezone.now() - log.last_seen < LOG_REFRESH_INTERVAL:
            return
        AccountAccessLog.objects.filter(pk=log.pk).update(
            last_seen=timezone.now(),
            visit_count=F('visit_count') + 1,
            device_id=device_id or log.device_id,
            user_agent=user_agent or log.user_agent)
