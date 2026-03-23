import requests
import logging
from django.dispatch import receiver
from axes.signals import user_locked_out
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_discord_webhook(title, description, color=0xff0000,
                         mention_user_id=None):
    webhook_url = getattr(settings, 'DISCORD_WEBHOOK_URL', None)
    if not webhook_url:
        return

    # Если указан ID пользователя, отправляем отдельное сообщение с упоминанием
    if mention_user_id:
        mention_text = f"<@{mention_user_id}>"
        try:
            requests.post(webhook_url, data={'content': mention_text})
        except Exception as e:
            logger.error(f"Discord mention error: {e}")

    # Теперь отправляем embed
    data = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "timestamp": timezone.now().isoformat(),
        }]
    }
    try:
        requests.post(webhook_url, json=data)
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")


@receiver(user_locked_out)
def notify_lockout(sender, request, username, ip_address, **kwargs):
    now = timezone.now()
    if username:
        subject = f"Блокировка пользователя {username} на сайте"
        message = f"Пользователь {username} заблокирован из-за множества неуда\
чных попыток входа.\nIP: {ip_address}\nВремя: {now}"
        discord_title = "🚨 Блокировка пользователя"
        discord_description = f"**Пользователь:** {username}\n**IP:** \
{ip_address}\n**Время:** {now}"
        discord_color = 0xff0000
    else:
        subject = f"Блокировка IP-адреса {ip_address} на сайте"
        message = f"IP {ip_address} заблокирован из-за множества неудачных поп\
ыток входа.\nВремя: {now}"
        discord_title = "🚨 Блокировка IP"
        discord_description = f"**IP-адрес:** {ip_address}\n**Время:** {now}"
        discord_color = 0xff5500

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [
        settings.ADMIN_EMAIL], fail_silently=True)
    send_discord_webhook(discord_title, discord_description,
                         color=discord_color, mention_user_id=getattr(
                             settings, 'DISCORD_ADMIN_USER_ID', None))
