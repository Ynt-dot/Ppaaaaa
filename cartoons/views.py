from django.shortcuts import render, get_object_or_404, redirect
from .models import Cartoon, CartoonLike, Comment, CommentLike, UserPreference, UserNote, Favorite, CartoonView
import json
from .utils import create_gif_from_frames
from django.contrib.auth import login
from django.contrib.auth.models import User
from .utils import send_verification_email
from .models import EmailVerificationToken
from .forms import CustomUserCreationForm
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
import os
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Count, Q, F, Case, When, Value, IntegerField
from django.template.loader import render_to_string
from django.db import transaction
from datetime import timedelta
from django.urls import reverse
from django.templatetags.static import static


def _get_user_avatar_url(user):
    """Return avatar preview URL for user, or default avatar static URL."""
    if user is not None:
        pref = getattr(user, 'preference', None)
        if pref and pref.avatar_id:
            try:
                if pref.avatar.preview:
                    return pref.avatar.preview.url
            except Exception:
                pass
    return static('cartoons/images/default_avatar.png')


def _frames_count(cartoon):
    fd = cartoon.frames_data
    return len(fd) if isinstance(fd, list) else 0


SORT_LABELS = {
    'new': 'Новое',
    'popular': 'Популярное',
    'trending': 'Тренды',
    'trending_24h': 'Тренды 24ч',
}


def index(request):
    default_sort = 'trending' if request.user.is_authenticated else 'popular'
    sort = request.GET.get('sort', default_sort)
    if sort not in SORT_LABELS:
        sort = default_sort

    if sort == 'popular':
        cartoon_list = Cartoon.objects.annotate(
            like_count=Count('likes', distinct=True),
            unique_views_count=Count('unique_views', distinct=True),
        ).order_by('-like_count', '-created_at')
    elif sort == 'trending':
        week_ago = timezone.now() - timedelta(days=7)
        cartoon_list = Cartoon.objects.annotate(
            recent_likes=Count('likes', filter=Q(likes__created_at__gte=week_ago), distinct=True),
            unique_views_count=Count('unique_views', distinct=True),
        ).order_by('-recent_likes', '-created_at')
    elif sort == 'trending_24h':
        day_ago = timezone.now() - timedelta(hours=24)
        cartoon_list = Cartoon.objects.annotate(
            recent_likes=Count('likes', filter=Q(likes__created_at__gte=day_ago), distinct=True),
            unique_views_count=Count('unique_views', distinct=True),
        ).order_by('-recent_likes', '-created_at')
    else:
        cartoon_list = Cartoon.objects.annotate(
            unique_views_count=Count('unique_views', distinct=True),
        ).order_by('-created_at')

    paginator = Paginator(cartoon_list, 12)
    page_number = request.GET.get('page')
    cartoons = paginator.get_page(page_number)

    news_file = os.path.join(settings.BASE_DIR, 'data', 'news.html')
    news_content = ''
    try:
        with open(news_file, 'r', encoding='utf-8') as f:
            news_content = f.read()
    except FileNotFoundError:
        news_content = '<p class="text-muted">Новостей пока нет.</p>'

    return render(request, 'cartoons/index.html', {
        'cartoons': cartoons,
        'news_content': news_content,
        'current_sort': sort,
        'sort_label': SORT_LABELS[sort],
    })


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _get_comment_sort(request):
    if request.user.is_authenticated:
        try:
            return request.user.preference.comment_sort
        except UserPreference.DoesNotExist:
            return 'popular'
    return request.session.get('comment_sort', 'popular')


def detail(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)
    Cartoon.objects.filter(pk=pk).update(views_count=F('views_count') + 1)
    cartoon.refresh_from_db(fields=['views_count'])
    session_key = _ensure_session(request)

    if request.user.is_authenticated:
        CartoonView.objects.get_or_create(cartoon=cartoon, user=request.user)
        if cartoon.author == request.user:
            Cartoon.objects.filter(pk=pk).update(author_last_seen_comments=timezone.now())

    likes_count = cartoon.likes.count()
    unique_views = cartoon.unique_views.count()
    if request.user.is_authenticated:
        user_liked = cartoon.likes.filter(user=request.user).exists()
    else:
        user_liked = cartoon.likes.filter(session_key=session_key).exists()

    comment_sort = _get_comment_sort(request)

    if request.user.is_authenticated:
        user_favorited = cartoon.favorited_by.filter(user=request.user).exists()
    else:
        user_favorited = False

    fc = _frames_count(cartoon)
    can_set_as_avatar = (
        request.user.is_authenticated
        and cartoon.author == request.user
        and 1 <= fc <= 10
    )

    is_used_as_avatar = cartoon.used_as_avatar.exists()

    if request.user.is_authenticated:
        try:
            _pref = request.user.preference
            rec_sort = _pref.rec_sort or 'trending'
            rec_author_filter = _pref.rec_author_filter
        except UserPreference.DoesNotExist:
            rec_sort = 'trending'
            rec_author_filter = False
    else:
        rec_sort = 'trending'
        rec_author_filter = False

    context = {
        'cartoon': cartoon,
        'likes_count': likes_count,
        'total_views': cartoon.views_count,
        'unique_views': unique_views,
        'user_liked': user_liked,
        'user_favorited': user_favorited,
        'comment_sort': comment_sort,
        'author_avatar_url': _get_user_avatar_url(cartoon.author),
        'can_set_as_avatar': can_set_as_avatar and not is_used_as_avatar,
        'is_used_as_avatar': is_used_as_avatar,
        'rec_sort': rec_sort,
        'rec_author_filter': rec_author_filter,
    }
    if cartoon.frames_data:
        context['frames_json'] = json.dumps(cartoon.frames_data)
    if cartoon.tags:
        context['sorted_tags'] = sorted(cartoon.tags)
    return render(request, 'cartoons/detail.html', context)


@require_GET
def get_recommendations(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)
    author_filter = request.GET.get('filter', 'all')
    sort = request.GET.get('sort', 'trending')
    if sort not in ('trending', 'trending_24h', 'new', 'popular'):
        sort = 'trending'

    if request.user.is_authenticated:
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        pref.rec_sort = sort
        pref.rec_author_filter = (author_filter == 'author')
        pref.save(update_fields=['rec_sort', 'rec_author_filter'])

    qs = Cartoon.objects.all()
    if author_filter == 'author' and cartoon.author:
        qs = qs.filter(author=cartoon.author)
    qs = qs.exclude(pk=pk)

    now = timezone.now()
    if sort == 'trending':
        week_ago = now - timedelta(days=7)
        qs = qs.annotate(sort_val=Count('likes', filter=Q(likes__created_at__gte=week_ago), distinct=True))
        order = ['-sort_val', '-created_at']
    elif sort == 'trending_24h':
        day_ago = now - timedelta(hours=24)
        qs = qs.annotate(sort_val=Count('likes', filter=Q(likes__created_at__gte=day_ago), distinct=True))
        order = ['-sort_val', '-created_at']
    elif sort == 'new':
        order = ['-created_at']
    else:  # popular
        qs = qs.annotate(sort_val=Count('likes', distinct=True))
        order = ['-sort_val', '-created_at']

    qs = qs.annotate(unique_views_count=Count('unique_views', distinct=True))

    if request.user.is_authenticated:
        viewed_ids = list(
            CartoonView.objects.filter(user=request.user).values_list('cartoon_id', flat=True)
        )
        qs = qs.annotate(
            is_viewed=Case(
                When(pk__in=viewed_ids, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        order = ['is_viewed'] + order

    qs = qs.select_related('author', 'author__preference', 'author__preference__avatar').order_by(*order)[:10]

    show_author = (author_filter != 'author')
    html = ''.join(
        render_to_string('cartoons/cartoon_card.html', {'cartoon': c, 'show_author': show_author}, request=request)
        for c in qs
    )

    return JsonResponse({'html': html, 'empty': len(html) == 0})


@require_POST
def toggle_cartoon_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    cartoon = get_object_or_404(Cartoon, pk=pk)
    like, created = CartoonLike.objects.get_or_create(
        cartoon=cartoon, user=request.user,
        defaults={'session_key': ''}
    )
    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({'liked': liked, 'count': cartoon.likes.count()})


def _serialize_comment(comment, request, session_key, current_level=0, max_inline_level=2, root_level=0, cartoon_author_id=None):
    """Serialize comment with nested replies up to max_inline_level."""
    if request.user.is_authenticated:
        user_liked = comment.likes.filter(user=request.user).exists()
    else:
        user_liked = comment.likes.filter(session_key=session_key).exists()

    author_url = reverse('user_profile', args=[comment.author.username]) if comment.author else None

    try:
        likes_count = comment.likes_count
    except AttributeError:
        likes_count = comment.likes.count()

    replies_data = []
    has_more_replies = False
    has_deeper_replies = False
    per_used = 0

    if current_level < max_inline_level:
        rel = current_level - root_level
        per_used = 2 if rel == 0 else 1
        per_load = 3
        qs = comment.replies.annotate(
            likes_count=Count('likes', distinct=True)
        ).select_related('author', 'author__preference', 'author__preference__avatar')
        if request.user.is_authenticated:
            qs = qs.annotate(
                is_mine=Case(When(author=request.user, then=Value(0)), default=Value(1), output_field=IntegerField())
            ).order_by('is_mine', '-is_pinned', '-likes_count', 'created_at')
        else:
            qs = qs.order_by('-is_pinned', '-likes_count', 'created_at')
        total_r = qs.count()
        has_more_replies = total_r > per_used
        for r in qs[:per_used]:
            replies_data.append(_serialize_comment(r, request, session_key, current_level + 1, max_inline_level, root_level, cartoon_author_id))
    elif current_level == max_inline_level:
        has_deeper_replies = comment.replies.exists()

    is_own = request.user.is_authenticated and comment.author_id == request.user.id
    can_pin = request.user.is_authenticated and cartoon_author_id is not None and request.user.id == cartoon_author_id

    return {
        'id': comment.id,
        'author': comment.display_author(),
        'author_url': author_url,
        'avatar_url': _get_user_avatar_url(comment.author),
        'text': comment.text,
        'is_edited': comment.is_edited,
        'is_pinned': comment.is_pinned,
        'is_own': is_own,
        'can_pin': can_pin,
        'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
        'likes_count': likes_count,
        'user_liked': user_liked,
        'level': comment.level,
        'per_used': per_used,
        'per_load': per_load if current_level < max_inline_level else 3,
        'replies': replies_data,
        'has_more_replies': has_more_replies,
        'has_deeper_replies': has_deeper_replies,
    }


@require_GET
def get_comments(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)
    session_key = _ensure_session(request)
    page = max(1, int(request.GET.get('page', 1)))
    sort = request.GET.get('sort', 'popular')
    per_page = 3

    qs = Comment.objects.filter(cartoon=cartoon, parent=None).annotate(
        likes_count=Count('likes', distinct=True)
    ).select_related('author', 'author__preference', 'author__preference__avatar')
    if request.user.is_authenticated:
        qs = qs.annotate(
            is_mine=Case(When(author=request.user, then=Value(0)), default=Value(1), output_field=IntegerField())
        )
        if sort == 'newest':
            qs = qs.order_by('is_mine', '-is_pinned', '-created_at')
        else:
            qs = qs.order_by('is_mine', '-is_pinned', '-likes_count', '-created_at')
    else:
        if sort == 'newest':
            qs = qs.order_by('-is_pinned', '-created_at')
        else:
            qs = qs.order_by('-is_pinned', '-likes_count', '-created_at')

    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    comments = list(qs[start:end])

    cartoon_author_id = cartoon.author_id
    data = [_serialize_comment(c, request, session_key, cartoon_author_id=cartoon_author_id) for c in comments]

    return JsonResponse({
        'comments': data,
        'has_next': end < total,
        'total': total,
    })


@require_GET
def get_replies(request, comment_pk):
    parent = get_object_or_404(Comment.objects.select_related('cartoon'), pk=comment_pk)
    session_key = _ensure_session(request)

    try:
        per_page = int(request.GET.get('per_page', 0))
        if per_page < 1 or per_page > 50:
            raise ValueError
    except (ValueError, TypeError):
        per_page = 3

    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except (ValueError, TypeError):
        offset = 0

    qs = parent.replies.annotate(
        likes_count=Count('likes', distinct=True)
    ).select_related('author', 'author__preference', 'author__preference__avatar')
    if request.user.is_authenticated:
        qs = qs.annotate(
            is_mine=Case(When(author=request.user, then=Value(0)), default=Value(1), output_field=IntegerField())
        ).order_by('is_mine', '-is_pinned', '-likes_count', 'created_at')
    else:
        qs = qs.order_by('-is_pinned', '-likes_count', 'created_at')

    total = qs.count()
    start = offset
    end = offset + per_page
    replies = list(qs[start:end])

    child_level = parent.level + 1
    max_inline = 2 if child_level <= 1 else child_level
    cartoon_author_id = parent.cartoon.author_id
    data = [_serialize_comment(r, request, session_key, current_level=child_level, max_inline_level=max_inline, cartoon_author_id=cartoon_author_id) for r in replies]

    return JsonResponse({'comments': data, 'has_next': end < total})


@require_GET
def get_thread(request, comment_pk):
    """Returns thread for modal: the root comment + paginated direct replies deeply nested."""
    root = get_object_or_404(Comment.objects.select_related('cartoon'), pk=comment_pk)
    session_key = _ensure_session(request)
    page = max(1, int(request.GET.get('page', 1)))
    per_page = 10

    qs = root.replies.annotate(
        likes_count=Count('likes', distinct=True)
    ).select_related('author', 'author__preference', 'author__preference__avatar')
    if request.user.is_authenticated:
        qs = qs.annotate(
            is_mine=Case(When(author=request.user, then=Value(0)), default=Value(1), output_field=IntegerField())
        ).order_by('is_mine', '-is_pinned', '-likes_count', 'created_at')
    else:
        qs = qs.order_by('-is_pinned', '-likes_count', 'created_at')

    per_page = 3
    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    replies = list(qs[start:end])

    cartoon_author_id = root.cartoon.author_id
    max_inline = root.level + 3
    child_level = root.level + 1
    replies_data = [_serialize_comment(r, request, session_key, current_level=child_level, max_inline_level=max_inline, root_level=child_level, cartoon_author_id=cartoon_author_id) for r in replies]

    root_data = _serialize_comment(root, request, session_key, current_level=root.level, max_inline_level=root.level - 1, root_level=root.level, cartoon_author_id=cartoon_author_id)
    root_data['replies'] = replies_data
    root_data['has_more_replies'] = end < total
    root_data['per_used'] = per_page
    root_data['per_load'] = per_page

    return JsonResponse({'root': root_data, 'has_next': end < total, 'page': page})


@require_POST
def add_comment(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)

    text = body.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Комментарий не может быть пустым'},
                            status=400)
    if len(text) > 2000:
        return JsonResponse(
            {'error': 'Комментарий слишком длинный (макс. 2000 символов)'},
            status=400
        )

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Войдите, чтобы оставить комментарий'}, status=403)

    parent = None
    level = 0
    parent_id = body.get('parent_id')
    if parent_id:
        try:
            parent = Comment.objects.get(pk=int(parent_id), cartoon=cartoon)
            level = parent.level + 1
        except Comment.DoesNotExist:
            return JsonResponse({'error': 'Комментарий не найден'}, status=404)

    comment = Comment.objects.create(
        cartoon=cartoon,
        author=request.user,
        parent=parent,
        level=level,
        text=text,
    )
    comment.likes_count = 0

    session_key = _ensure_session(request)
    data = _serialize_comment(comment, request, session_key, current_level=level, max_inline_level=level - 1, cartoon_author_id=cartoon.author_id)
    return JsonResponse(data, status=201)

@require_POST
def pin_comment(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    comment = get_object_or_404(Comment.objects.select_related('cartoon'), pk=comment_pk)
    if comment.cartoon.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)
    comment.is_pinned = not comment.is_pinned
    comment.save(update_fields=['is_pinned'])
    return JsonResponse({'pinned': comment.is_pinned})


@require_POST
def edit_comment(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    comment = get_object_or_404(Comment, pk=comment_pk)
    if comment.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    text = body.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Комментарий не может быть пустым'}, status=400)
    if len(text) > 2000:
        return JsonResponse({'error': 'Слишком длинный (макс. 2000 символов)'}, status=400)
    comment.text = text
    comment.is_edited = True
    comment.save(update_fields=['text', 'is_edited'])
    return JsonResponse({'ok': True, 'text': text})


@require_POST
def toggle_comment_like(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    comment = get_object_or_404(Comment, pk=comment_pk)
    like, created = CommentLike.objects.get_or_create(
        comment=comment, user=request.user,
        defaults={'session_key': ''}
    )
    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({'liked': liked, 'count': comment.likes.count()})


@require_POST
def set_comment_sort(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)

    sort = body.get('sort', 'popular')
    if sort not in ('popular', 'newest'):
        return JsonResponse({'error': 'Неверное значение'}, status=400)

    if request.user.is_authenticated:
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        pref.comment_sort = sort
        pref.save()
    else:
        request.session['comment_sort'] = sort

    return JsonResponse({'sort': sort})


def editor(request, pk=None):
    if pk:
        cartoon = get_object_or_404(Cartoon, pk=pk)
        if cartoon.author and cartoon.author != request.user:
            return redirect('index')
        if cartoon.used_as_avatar.exists():
            return redirect('detail', pk=pk)
    else:
        cartoon = None

    if request.method == 'POST':
        title = request.POST.get('title', '')[:100]
        fps_str = request.POST.get('fps', '10')
        frames_json = request.POST.get('frames')
        tags_json = request.POST.get('tags', '[]')
        description = request.POST.get('description', '')

        try:
            fps = int(fps_str)
            if fps < 1 or fps > 30:
                raise ValueError
        except (ValueError, TypeError):
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'FPS должен быть целым числом от 1 до 30'
            })

        # Преобразуем теги из JSON
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            tags = []

        if not title or not frames_json:
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'Не хватает данных'
            })

        frames_data = json.loads(frames_json)

        if not frames_data:
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'Нет кадров'
            })

        if len(frames_data) > 5000:
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'Слишком много кадров. Максимум 5000 кадров.'
            })

        if cartoon:
            cartoon.title = title
            cartoon.fps = fps
            cartoon.frames_data = frames_data
            cartoon.tags = tags
            cartoon.description = description
            if cartoon.preview:
                cartoon.preview.delete(save=False)
        else:
            cartoon = Cartoon(
                title=title,
                author=request.user if request.user.is_authenticated else None,
                fps=fps,
                frames_data=frames_data,
                tags=tags,
                description=description
            )

        gif_content = create_gif_from_frames(frames_data, fps, max_frames=50)
        cartoon.preview.save(f'cartoon_{cartoon.pk or "new"}.gif', gif_content,
                             save=False)
        cartoon.save()

        return redirect('detail', pk=cartoon.pk)

    context = {'cartoon': cartoon}
    if cartoon and cartoon.frames_data:
        context['frames_json'] = json.dumps(cartoon.frames_data)

    # Добавляем флаг для анонимов, чтобы показать модальное окно
    if not request.user.is_authenticated and not pk:
        context['show_anon_modal'] = True

    return render(request, 'cartoons/editor.html', context)


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.save()
                    send_verification_email(user)
                request.session['pending_user_id'] = user.id
                return redirect('verification_sent')
            except Exception:
                form.add_error(None, 'Не удалось отправить письмо подтверждения. Попробуйте позже.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def user_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    tab = request.GET.get('tab', 'album')
    if tab not in ('album', 'comments', 'liked', 'favorites'):
        tab = 'album'

    total_cartoons = Cartoon.objects.filter(author=profile_user).count()

    user_note = ''
    if request.user.is_authenticated and request.user != profile_user:
        try:
            note_obj = UserNote.objects.get(author=request.user, about=profile_user)
            user_note = note_obj.text
        except UserNote.DoesNotExist:
            pass

    is_own_profile = request.user == profile_user

    # Аватар профиля
    pref = getattr(profile_user, 'preference', None)
    if pref and pref.avatar_id:
        try:
            profile_avatar_url = pref.avatar.preview.url
        except Exception:
            profile_avatar_url = static('cartoons/images/default_avatar.png')
    else:
        profile_avatar_url = static('cartoons/images/default_avatar.png')

    context = {
        'profile_user': profile_user,
        'active_tab': tab,
        'user_note': user_note,
        'is_own_profile': is_own_profile,
        'total_cartoons': total_cartoons,
        'profile_avatar_url': profile_avatar_url,
    }

    if tab == 'album':
        sort = request.GET.get('sort', 'new')
        if sort not in SORT_LABELS:
            sort = 'new'

        if sort == 'popular':
            cartoon_list = Cartoon.objects.filter(author=profile_user).annotate(
                like_count=Count('likes', distinct=True),
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-like_count', '-created_at')
        elif sort == 'trending':
            week_ago = timezone.now() - timedelta(days=7)
            cartoon_list = Cartoon.objects.filter(author=profile_user).annotate(
                recent_likes=Count('likes', filter=Q(likes__created_at__gte=week_ago), distinct=True),
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-recent_likes', '-created_at')
        elif sort == 'trending_24h':
            day_ago = timezone.now() - timedelta(hours=24)
            cartoon_list = Cartoon.objects.filter(author=profile_user).annotate(
                recent_likes=Count('likes', filter=Q(likes__created_at__gte=day_ago), distinct=True),
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-recent_likes', '-created_at')
        else:
            cartoon_list = Cartoon.objects.filter(author=profile_user).annotate(
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-created_at')

        if is_own_profile:
            cartoon_list = cartoon_list.annotate(
                new_comments_count=Count(
                    'comments',
                    filter=(
                        Q(comments__created_at__gt=F('author_last_seen_comments')) |
                        Q(author_last_seen_comments__isnull=True)
                    ),
                    distinct=True,
                )
            )

        paginator = Paginator(cartoon_list, 12)
        cartoons = paginator.get_page(request.GET.get('page'))
        context.update({
            'cartoons': cartoons,
            'current_sort': sort,
            'sort_label': SORT_LABELS[sort],
        })

    elif tab == 'liked':
        liked_list = Cartoon.objects.filter(
            likes__user=profile_user
        ).annotate(
            unique_views_count=Count('unique_views', distinct=True),
        ).order_by('-likes__created_at')
        paginator = Paginator(liked_list, 12)
        context['cartoons'] = paginator.get_page(request.GET.get('page'))

    elif tab == 'favorites':
        fav_list = Cartoon.objects.filter(
            favorited_by__user=profile_user
        ).annotate(
            unique_views_count=Count('unique_views', distinct=True),
        ).order_by('-favorited_by__created_at')
        paginator = Paginator(fav_list, 12)
        context['cartoons'] = paginator.get_page(request.GET.get('page'))

    return render(request, 'cartoons/user_profile.html', context)


@require_POST
def save_user_note(request, username):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    about_user = get_object_or_404(User, username=username)
    if request.user == about_user:
        return JsonResponse({'error': 'forbidden'}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)

    text = body.get('text', '')[:256]
    if text:
        UserNote.objects.update_or_create(
            author=request.user, about=about_user,
            defaults={'text': text}
        )
    else:
        UserNote.objects.filter(author=request.user, about=about_user).delete()

    return JsonResponse({'ok': True})


@require_POST
def toggle_favorite(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    cartoon = get_object_or_404(Cartoon, pk=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, cartoon=cartoon)
    if not created:
        fav.delete()
        favorited = False
    else:
        favorited = True

    return JsonResponse({'favorited': favorited})


@require_GET
def get_user_profile_comments(request, username):
    profile_user = get_object_or_404(User, username=username)
    session_key = _ensure_session(request)

    comment_type = request.GET.get('type', 'user')
    sort = request.GET.get('sort', 'newest')
    page = max(1, int(request.GET.get('page', 1)))
    per_page = 10

    if comment_type == 'cartoon':
        qs = Comment.objects.filter(cartoon__author=profile_user)
    else:
        qs = Comment.objects.filter(author=profile_user)

    qs = qs.select_related(
        'author', 'author__preference', 'author__preference__avatar', 'cartoon'
    ).annotate(likes_count=Count('likes'))

    if sort == 'popular':
        qs = qs.order_by('-likes_count', '-created_at')
    else:
        qs = qs.order_by('-created_at')

    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    page_qs = qs[start:end]

    data = []
    for c in page_qs:
        if request.user.is_authenticated:
            user_liked = c.likes.filter(user=request.user).exists()
        else:
            user_liked = c.likes.filter(session_key=session_key).exists()

        author_url = None
        if c.author:
            author_url = reverse('user_profile', args=[c.author.username])

        data.append({
            'id': c.id,
            'author': c.display_author(),
            'author_url': author_url,
            'avatar_url': _get_user_avatar_url(c.author),
            'text': c.text,
            'created_at': c.created_at.strftime('%d.%m.%Y %H:%M'),
            'likes_count': c.likes_count,
            'user_liked': user_liked,
            'cartoon_title': c.cartoon.title,
            'cartoon_url': reverse('detail', args=[c.cartoon_id]),
        })

    return JsonResponse({
        'comments': data,
        'has_next': end < total,
        'total': total,
    })


@require_POST
def set_as_avatar(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    cartoon = get_object_or_404(Cartoon, pk=pk)

    if cartoon.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)

    fc = _frames_count(cartoon)
    if not (1 <= fc <= 10):
        return JsonResponse(
            {'error': 'Мульт должен иметь от 1 до 10 кадров'}, status=400
        )

    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    pref.avatar = cartoon
    pref.save()

    return JsonResponse({
        'ok': True,
        'avatar_url': cartoon.preview.url if cartoon.preview else static('cartoons/images/default_avatar.png'),
    })


@require_POST
def delete_avatar(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    pref.avatar = None
    pref.save()

    return JsonResponse({'ok': True, 'avatar_url': static('cartoons/images/default_avatar.png')})


@require_GET
def get_avatar_cartoons(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    per_page = 12
    offset = max(0, int(request.GET.get('offset', 0)))

    qs = Cartoon.objects.filter(author=request.user).only('id', 'title', 'preview', 'frames_data')

    eligible = [
        {'id': c.id, 'title': c.title, 'preview_url': c.preview.url if c.preview else None}
        for c in qs
        if 1 <= _frames_count(c) <= 10
    ]

    page = eligible[offset:offset + per_page]
    has_next = offset + per_page < len(eligible)

    return JsonResponse({'cartoons': page, 'has_next': has_next})


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
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

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
