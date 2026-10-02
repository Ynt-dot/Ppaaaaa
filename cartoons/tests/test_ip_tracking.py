from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from cartoons.models import AccountAccessLog, BannedIdentifier


class AccessLoggingTests(TestCase):
    """Middleware пишет AccountAccessLog только для авторизованных
    запросов, и только с реальным IP - остальное не должно попадать
    в лог."""

    def setUp(self):
        self.user = User.objects.create_user('logged', password='x')

    def test_anonymous_request_creates_no_log(self):
        self.client.get(reverse('index'))
        self.assertFalse(AccountAccessLog.objects.exists())

    def test_authenticated_request_creates_log(self):
        self.client.force_login(self.user)
        self.client.get(reverse('index'))
        log = AccountAccessLog.objects.get(user=self.user)
        self.assertTrue(log.ip_address)
        self.assertEqual(log.visit_count, 1)

    def test_device_cookie_set_on_first_visit(self):
        resp = self.client.get(reverse('index'))
        self.assertIn('device_id', resp.cookies)

    def test_second_request_reuses_existing_cookie(self):
        resp1 = self.client.get(reverse('index'))
        device_id = resp1.cookies['device_id'].value
        resp2 = self.client.get(reverse('index'))
        # Кука не должна выставляться заново, раз уже была.
        self.assertNotIn('device_id', resp2.cookies)
        self.assertEqual(self.client.cookies['device_id'].value, device_id)

    def test_log_records_device_id_from_cookie(self):
        self.client.force_login(self.user)
        self.client.get(reverse('index'))
        log = AccountAccessLog.objects.get(user=self.user)
        self.assertTrue(log.device_id)
        self.assertEqual(
            log.device_id, self.client.cookies['device_id'].value)

    def test_repeated_requests_within_an_hour_do_not_duplicate_rows(self):
        self.client.force_login(self.user)
        self.client.get(reverse('index'))
        self.client.get(reverse('index'))
        self.client.get(reverse('index'))
        self.assertEqual(AccountAccessLog.objects.count(), 1)
        log = AccountAccessLog.objects.get(user=self.user)
        # Второй и третий запрос попали в "недавно засечено" окно,
        # поэтому visit_count не увеличился сверх первой записи.
        self.assertEqual(log.visit_count, 1)

    def test_different_users_same_ip_both_logged(self):
        other = User.objects.create_user('other_logged', password='x')
        self.client.force_login(self.user)
        self.client.get(reverse('index'))
        self.client.logout()
        self.client.force_login(other)
        self.client.get(reverse('index'))
        self.assertEqual(AccountAccessLog.objects.count(), 2)
        ips = set(
            AccountAccessLog.objects.values_list('ip_address', flat=True))
        self.assertEqual(len(ips), 1)


class BanEnforcementTests(TestCase):
    """Бан по IP/device_id блокирует вообще любой запрос к сайту -
    не только попытку входа - независимо от того, есть ли у
    посетителя аккаунт."""

    def test_banned_ip_gets_403(self):
        BannedIdentifier.objects.create(
            kind=BannedIdentifier.KIND_IP, value='127.0.0.1')
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.status_code, 403)

    def test_unbanned_ip_not_blocked(self):
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.status_code, 200)

    def test_banned_device_id_gets_403(self):
        self.client.cookies['device_id'] = 'banned-device-123'
        BannedIdentifier.objects.create(
            kind=BannedIdentifier.KIND_DEVICE, value='banned-device-123')
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.status_code, 403)

    def test_ban_blocks_authenticated_users_too(self):
        user = User.objects.create_user('banneduser', password='x')
        self.client.force_login(user)
        BannedIdentifier.objects.create(
            kind=BannedIdentifier.KIND_IP, value='127.0.0.1')
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.status_code, 403)

    def test_ban_blocks_registration_page(self):
        BannedIdentifier.objects.create(
            kind=BannedIdentifier.KIND_IP, value='127.0.0.1')
        resp = self.client.get(reverse('register'))
        self.assertEqual(resp.status_code, 403)


@override_settings(AXES_ENABLED=False)
class AccountAccessLogAdminPermissionTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'x')
        self.staff = User.objects.create_user(
            'staffer', password='x', is_staff=True)

    def test_staff_cannot_see_access_log_admin(self):
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('admin:cartoons_accountaccesslog_changelist'))
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_see_access_log_admin(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(
            reverse('admin:cartoons_accountaccesslog_changelist'))
        self.assertEqual(resp.status_code, 200)

    def test_staff_cannot_see_banned_identifier_admin(self):
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('admin:cartoons_bannedidentifier_changelist'))
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_see_banned_identifier_admin(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(
            reverse('admin:cartoons_bannedidentifier_changelist'))
        self.assertEqual(resp.status_code, 200)

    def test_staff_does_not_see_access_log_inline_on_user_page(self):
        # Обычному стаффу нужны стандартные права Django на просмотр/
        # изменение User, чтобы вообще открыть эту страницу - сама
        # инлайн-секция с IP скрыта отдельной проверкой (не через
        # has_module_permission), поэтому staff здесь должен видеть
        # страницу, но без блока с IP.
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label='auth', content_type__model='user',
                codename__in=['view_user', 'change_user']))
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('admin:auth_user_change', args=[self.staff.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'IP-адреса и устройства')

    def test_superuser_sees_access_log_inline_on_user_page(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(
            reverse('admin:auth_user_change', args=[self.superuser.pk]))
        self.assertContains(resp, 'IP-адреса и устройства')


@override_settings(AXES_ENABLED=False)
class SharedIpsReportTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'x')
        self.alice = User.objects.create_user('alice_ip', password='x')
        self.bob = User.objects.create_user('bob_ip', password='x')
        AccountAccessLog.objects.create(
            user=self.alice, ip_address='10.0.0.1')
        AccountAccessLog.objects.create(user=self.bob, ip_address='10.0.0.1')
        self.client.force_login(self.superuser)

    def test_shared_ip_listed(self):
        resp = self.client.get(
            reverse('admin:cartoons_accountaccesslog_shared_ips'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '10.0.0.1')
        self.assertContains(resp, 'alice_ip')
        self.assertContains(resp, 'bob_ip')

    def test_staff_cannot_reach_shared_ips_report(self):
        self.client.logout()
        staff = User.objects.create_user(
            'staffnip', password='x', is_staff=True)
        self.client.force_login(staff)
        resp = self.client.get(
            reverse('admin:cartoons_accountaccesslog_shared_ips'))
        self.assertEqual(resp.status_code, 403)


@override_settings(AXES_ENABLED=False)
class BanActionsTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'x')
        self.user = User.objects.create_user('to_be_banned', password='x')
        self.log = AccountAccessLog.objects.create(
            user=self.user, ip_address='203.0.113.5',
            device_id='some-device-id')
        self.client.force_login(self.superuser)

    def test_ban_selected_ips_action_creates_ban(self):
        self.client.post(
            reverse('admin:cartoons_accountaccesslog_changelist'), {
                'action': 'ban_selected_ips',
                '_selected_action': [self.log.pk],
            }, follow=True)
        self.assertTrue(
            BannedIdentifier.objects.filter(
                kind=BannedIdentifier.KIND_IP,
                value='203.0.113.5').exists())

    def test_ban_selected_devices_action_creates_ban(self):
        self.client.post(
            reverse('admin:cartoons_accountaccesslog_changelist'), {
                'action': 'ban_selected_devices',
                '_selected_action': [self.log.pk],
            }, follow=True)
        self.assertTrue(
            BannedIdentifier.objects.filter(
                kind=BannedIdentifier.KIND_DEVICE,
                value='some-device-id').exists())

    def test_banned_by_recorded(self):
        BannedIdentifier.objects.create(
            kind=BannedIdentifier.KIND_IP, value='198.51.100.1',
            banned_by=self.superuser)
        ban = BannedIdentifier.objects.get(value='198.51.100.1')
        self.assertEqual(ban.banned_by, self.superuser)
