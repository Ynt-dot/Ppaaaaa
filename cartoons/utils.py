import base64
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.core.mail.utils import DNS_NAME
from django.urls import reverse
from django.conf import settings
from .models import EmailVerificationToken
from django.utils import timezone

# На некоторых Windows-машинах socket.getfqdn() возвращает имя хоста
# с точкой в конце (например "FLTP-5i5-8512."), что ломает IDNA-кодек
# при установке SMTP-соединения. Проверяем и подменяем на 'localhost'.
try:
    DNS_NAME.get_fqdn()
except UnicodeEncodeError:
    DNS_NAME._fqdn = 'localhost'


def create_gif_from_frames(frames_data, fps=12, max_frames=None):
    """
    frames_data: список строк dataURL (base64)
    fps: кадров в секунду
    max_frames: максимальное количество кадров для GIF (None = все)
    возвращает ContentFile с GIF
    """
    if max_frames is not None:
        frames_data = frames_data[:max_frames]

    GIF_SIZE = (600, 400)

    images = []
    for data_url in frames_data:
        format, imgstr = data_url.split(';base64,')
        image_data = base64.b64decode(imgstr)
        img = Image.open(BytesIO(image_data)).convert('RGBA')
        white_bg = Image.new('RGB', img.size, (255, 255, 255))
        white_bg.paste(img, (0, 0), img)
        if white_bg.size != GIF_SIZE:
            white_bg = white_bg.resize(GIF_SIZE, Image.LANCZOS)
        images.append(white_bg)

    if not images:
        return None

    gif_buffer = BytesIO()
    duration = int(1000 / fps)
    images[0].save(
        gif_buffer,
        format='GIF',
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0,
        optimize=False
    )
    gif_buffer.seek(0)
    return ContentFile(gif_buffer.read(), name='animation.gif')


def send_verification_email(user):
    # Создаём или обновляем токен для пользователя
    token, created = EmailVerificationToken.objects.update_or_create(
        user=user,
        defaults={'expires_at': timezone.now() + timezone.timedelta(hours=24)}
    )

    verification_url = reverse('verify_email', kwargs={'token': token.token})
    full_url = f"{settings.SITE_URL}{verification_url}"

    subject = 'Подтверждение email на сайте Ппааааа'
    message = f"""
    Здравствуйте, {user.username}!

    Для подтверждения вашего email перейдите по ссылке:
    {full_url}

    Ссылка действительна 24 часа.

    Если вы не регистрировались на нашем сайте, просто проигнорируйте это пись\
мо.
    """

    html_message = f"""
    <html>
    <body>
        <h2>Здравствуйте, {user.username}!</h2>
        <p>Для подтверждения вашего email нажмите на кнопку ниже:</p>
        <p>
            <a href="{full_url}" style="background-color: #4CAF50; color: whit\
e; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Подтвердить email
            </a>
        </p>
        <p>Или скопируйте ссылку: <a href="{full_url}">{full_url}</a></p>
        <p>Ссылка действительна 24 часа.</p>
        <p>Если вы не регистрировались, просто проигнорируйте это письмо.</p>
    </body>
    </html>
    """

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )
    return token
