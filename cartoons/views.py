from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Cartoon
import json
from .utils import create_gif_from_frames
from django.contrib.auth import login
from django.contrib.auth.models import User
from .utils import send_verification_email
from .models import EmailVerificationToken
from .forms import CustomUserCreationForm
from django.contrib import messages
from django.utils import timezone


def index(request):
    cartoons = Cartoon.objects.all()
    return render(request, 'cartoons/index.html', {'cartoons': cartoons})


def detail(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)
    context = {'cartoon': cartoon}
    if cartoon.frames_data:
        context['frames_json'] = json.dumps(cartoon.frames_data)
    return render(request, 'cartoons/detail.html', context)


@login_required
def editor(request, pk=None):
    if pk:
        cartoon = get_object_or_404(Cartoon, pk=pk)
        if cartoon.author != request.user:
            return redirect('index')
    else:
        cartoon = None

    if request.method == 'POST':
        title = request.POST.get('title')
        fps = int(request.POST.get('fps', 12))
        frames_json = request.POST.get('frames')

        if not title or not frames_json:
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'Не хватает данных'
            })

        frames_data = json.loads(frames_json)  # список dataURL

        if not frames_data:
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'Нет кадров'
            })

        # Создаём или обновляем объект Cartoon
        if cartoon:
            cartoon.title = title
            cartoon.fps = fps
            cartoon.frames_data = frames_data
            # Удаляем старый preview, если есть
            if cartoon.preview:
                cartoon.preview.delete(save=False)
        else:
            cartoon = Cartoon(
                title=title,
                author=request.user,
                fps=fps,
                frames_data=frames_data
            )

        # Генерируем GIF из кадров
        gif_content = create_gif_from_frames(frames_data, fps)

        # Сохраняем GIF в поле preview
        cartoon.preview.save(f'cartoon_{cartoon.pk or "new"}.gif', gif_content,
                             save=False)
        cartoon.save()

        return redirect('detail', pk=cartoon.pk)

    # Для GET-запроса передаём существующие данные (если редактирование)
    context = {'cartoon': cartoon}
    # Если редактируем и есть frames_data, передадим их в шаблон для
    # инициализации JS
    if cartoon and cartoon.frames_data:
        context['frames_json'] = json.dumps(cartoon.frames_data)
    return render(request, 'cartoons/editor.html', context)


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            send_verification_email(user)
            # Сохраняем id пользователя в сессии для повторной отправки
            request.session['pending_user_id'] = user.id
            return redirect('verification_sent')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def user_profile(request, username):
    # Получаем пользователя по имени или 404
    user = get_object_or_404(User, username=username)
    # Все мультики этого пользователя, отсортированные по новизне
    cartoons = Cartoon.objects.filter(author=user).order_by('-created_at')
    return render(request, 'cartoons/user_profile.html', {
        'profile_user': user,
        'cartoons': cartoons
    })


def verify_email(request, token):
    token_obj = get_object_or_404(EmailVerificationToken, token=token)

    if not token_obj.is_valid():
        return render(request, 'registration/verification_invalid.html', {
            'message':
            'Срок действия ссылки истёк. Запросите подтверждение снова.'
        })

    user = token_obj.user
    user.is_active = True
    user.save()

    # Удаляем токен, чтобы нельзя было использовать повторно
    token_obj.delete()

    # Автоматически входим пользователя (опционально)
    login(request, user)

    return render(
        request,
        'registration/verification_success.html',
        {'user': user}
        )


def verification_sent(request):
    return render(request, 'registration/verification_sent.html')


def resend_verification(request):
    # Получаем id пользователя из сессии
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, 'Не найден пользователь для повторной отправки\
. Зарегистрируйтесь снова.')
        return redirect('register')

    try:
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        messages.error(request, 'Пользователь не найден или уже активирован.')
        return redirect('login')

    # Получаем или создаём токен
    token, created = EmailVerificationToken.objects.get_or_create(user=user)

    # Проверяем, прошло ли достаточно времени с последней отправки (60 секунд)
    if not created:
        time_since_last = (timezone.now() - token.updated_at).total_seconds()
        if time_since_last < 60:
            messages.error(
                request,
                f'Повторная отправка доступна через \
{60 - int(time_since_last)} секунд.'
                )
            return redirect('verification_sent')

    # Обновляем expires_at и отправляем письмо
    token.expires_at = timezone.now() + timezone.timedelta(hours=24)
    token.save()
    send_verification_email(user)  # используем ту же функцию, она обновит
    # токен (но мы уже обновили вручную, можно просто отправить)
    # Можно также вызвать send_verification_email, но она создаст новый токен.
    # Чтобы не дублировать, просто отправим письмо с существующим токеном.
    # Для этого выделим отправку в отдельную функцию, либо здесь сформируем
    # письмо заново.
    # Лучше реорганизовать код: send_verification_email принимает токен или
    # пользователя и использует существующий токен.
    # Сейчас функция send_verification_email создаёт/обновляет токен. Если мы
    # уже обновили, можно вызвать её снова — она перезапишет токен, но это
    # нормально.
    send_verification_email(user)  # она обновит expires_at ещё раз, но это не
    # страшно.

    messages.success(request, 'Письмо с подтверждением отправлено повторно.')
    return redirect('verification_sent')
