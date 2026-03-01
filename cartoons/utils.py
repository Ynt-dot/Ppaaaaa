import base64
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile


def create_gif_from_frames(frames_data, fps=12):
    """
    frames_data: список строк dataURL (base64)
    возвращает ContentFile с GIF
    """
    images = []
    for data_url in frames_data:
        # data_url вида "data:image/png;base64,...."
        format, imgstr = data_url.split(';base64,')
        image_data = base64.b64decode(imgstr)
        img = Image.open(BytesIO(image_data))
        # Конвертируем в RGB (GIF не поддерживает альфа-канал)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        images.append(img)

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
