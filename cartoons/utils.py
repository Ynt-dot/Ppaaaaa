import base64
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from .models import EmailVerificationToken
from django.utils import timezone


def create_gif_from_frames(frames_data, fps=12):
    """
    frames_data: список строк dataURL (base64)
    возвращает ContentFile с GIF, где каждый кадр наложен на белый фон
    """
    images = []
    for data_url in frames_data:
        # data_url вида "data:image/png;base64,...."
        format, imgstr = data_url.split(';base64,')
        image_data = base64.b64decode(imgstr)
        # Открываем изображение с сохранением альфа-канала
        img = Image.open(BytesIO(image_data)).convert('RGBA')

        # Создаём белое фоновое изображение того же размера
        white_bg = Image.new('RGB', img.size, (255, 255, 255))

        # Накладываем изображение на белый фон, используя альфа-канал как маску
        white_bg.paste(img, (0, 0), img)  # третий аргумент — маска
        # прозрачности
        images.append(white_bg)

    # Создаём GIF в памяти
    gif_buffer = BytesIO()
    # duration в миллисекундах = 1000 / fps
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
