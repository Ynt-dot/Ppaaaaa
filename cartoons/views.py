from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Cartoon
import json
from .utils import create_gif_from_frames
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login


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
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})
