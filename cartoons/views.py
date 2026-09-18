from django.shortcuts import render, get_object_or_404, redirect
from .models import (
    Cartoon, CartoonLike, Comment, CommentLike, UserPreference, UserNote,
    Favorite, CartoonView, UserBlock, SiteSettings,
)
import json
import re
from .utils import create_gif_from_frames, create_avatar_gif
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .utils import send_verification_email
from .models import EmailVerificationToken
from .forms import CustomUserCreationForm
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
import os
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_GET
from django.db.models import (
    Count, Q, F, Case, When, Value, IntegerField, OuterRef, Subquery,
)
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string
from django.db import transaction
from datetime import timedelta
from django.urls import reverse
from django.templatetags.static import static


def _get_user_avatar_url(user):
    """Возвращает URL GIF-аватара пользователя, с откатом на
    общесайтовый аватар по умолчанию (SiteSettings, задаётся
    суперпользователем в админке), а в конце - на статичную
    заглушку."""
    if user is not None:
        pref = getattr(user, 'preference', None)
        if pref and pref.avatar_gif:
            try:
                return pref.avatar_gif.url
            except Exception:
                pass
    site_settings = SiteSettings.objects.filter(pk=1).first()
    if site_settings and site_settings.default_avatar_gif:
        try:
            return site_settings.default_avatar_gif.url
        except Exception:
            pass
    return static('cartoons/images/default_avatar.png')


def _profile_url(user):
    return reverse('user_profile', args=[user.username])


def _display_name(user):
    """Имя, которое видят другие: UserPreference.display_name, если
    задано, иначе C-key (User.username)."""
    if user is None:
        return ''
    pref = getattr(user, 'preference', None)
    if pref and pref.display_name:
        return pref.display_name
    return user.username


def _avatar_link_url(user):
    """Куда должен вести клик по аватарке пользователя: на мульт,
    выбранный в качестве аватара (UserPreference.avatar), если он
    есть - иначе на страницу профиля, так как отправлять клик
    некуда (это также покрывает общесайтовый аватар по умолчанию,
    который не является "его" мультом)."""
    if user is None:
        return None
    pref = getattr(user, 'preference', None)
    if pref and pref.avatar_id:
        return reverse('detail', args=[pref.avatar_id])
    return _profile_url(user)


def _frames_count(cartoon):
    fd = cartoon.frames_data
    return len(fd) if isinstance(fd, list) else 0


def _build_avatar_gif(cartoon, body):
    """Обрезает cartoon.preview по нормализованным
    left/top/right/bottom из body (каждое кламп(з)ится в [0, 1];
    некорректные/отсутствующие значения откатываются на весь кадр) и
    возвращает ContentFile GIF размера аватара."""
    def _clamp(v, default):
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = default
        return max(0.0, min(1.0, v))

    left_n = _clamp(body.get('left', 0), 0.0)
    top_n = _clamp(body.get('top', 0), 0.0)
    right_n = _clamp(body.get('right', 1), 1.0)
    bottom_n = _clamp(body.get('bottom', 1), 1.0)
    return create_avatar_gif(
        cartoon.preview.path, left_n, top_n, right_n, bottom_n)


def _count_descendant_comments(comment_id, created_after=None):
    """Считает все вложенные ответы под комментарием, на любой
    глубине - соответствует тому, что удалит CASCADE-удаление
    родителя.

    Если задан created_after, считает только те, что созданы после
    этого момента (тоже на любой глубине) - используется для бейджа
    "непрочитанные ответы".
    """
    total = 0
    current_ids = [comment_id]
    while current_ids:
        qs = Comment.objects.filter(parent_id__in=current_ids)
        if created_after is not None:
            total += qs.filter(created_at__gt=created_after).count()
        current_ids = list(qs.values_list('id', flat=True))
        if created_after is None:
            total += len(current_ids)
    return total


def _clean_tags(tags):
    """Проверяет и очищает присланные пользователем теги: на выходе
    должен получиться список коротких простых строк, иначе
    валидация молча откатывается на [] вместо сохранения
    произвольного JSON, который потом попадёт в рендер."""
    if not isinstance(tags, list):
        return []
    cleaned = []
    for tag in tags[:20]:
        if not isinstance(tag, str):
            continue
        tag = tag.strip()[:30]
        if tag:
            cleaned.append(tag)
    return cleaned


SORT_LABELS = {
    'new': 'Новое',
    'popular': 'Популярное',
    'trending': 'Тренды',
    'trending_24h': 'Тренды 24ч',
}


def index(request):
    if request.user.is_authenticated:
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        if 'sort' in request.GET:
            sort = request.GET['sort']
            if sort not in SORT_LABELS:
                sort = pref.index_sort
            elif sort != pref.index_sort:
                pref.index_sort = sort
                pref.save(update_fields=['index_sort'])
        else:
            sort = pref.index_sort
    else:
        sort = request.GET.get('sort', 'popular')
        if sort not in SORT_LABELS:
            sort = 'popular'

    # Через подзапросы, а не annotate(Count(...)) на нескольких связях
    # сразу - см. подробный комментарий в get_recommendations() про
    # декартово произведение строк при нескольких Count() с join к
    # разным related-таблицам в одном запросе.
    views_subquery = (
        CartoonView.objects.filter(cartoon=OuterRef('pk'))
        .order_by().values('cartoon')
        .annotate(c=Count('id')).values('c')
    )
    unique_views_annotation = Coalesce(
        Subquery(views_subquery, output_field=IntegerField()), 0)

    if sort in ('popular', 'trending', 'trending_24h'):
        likes_time_filter = Q()
        if sort == 'trending':
            likes_time_filter = Q(
                created_at__gte=timezone.now() - timedelta(days=7))
        elif sort == 'trending_24h':
            likes_time_filter = Q(
                created_at__gte=timezone.now() - timedelta(hours=24))
        likes_subquery = (
            CartoonLike.objects.filter(
                likes_time_filter, cartoon=OuterRef('pk'))
            .order_by().values('cartoon')
            .annotate(c=Count('id')).values('c')
        )
        cartoon_list = Cartoon.objects.annotate(
            recent_likes=Coalesce(
                Subquery(likes_subquery, output_field=IntegerField()), 0),
            unique_views_count=unique_views_annotation,
        ).order_by('-recent_likes', '-created_at')
    else:
        cartoon_list = Cartoon.objects.annotate(
            unique_views_count=unique_views_annotation,
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

    # Яркое объявление наверху заглавной - как и news.html, живёт вне
    # git (data/announcement.html, в .gitignore) и правится вручную на
    # сервере. Файла обычно нет - блок тогда просто не показывается.
    announcement_file = os.path.join(
        settings.BASE_DIR, 'data', 'announcement.html')
    announcement_content = ''
    try:
        with open(announcement_file, 'r', encoding='utf-8') as f:
            announcement_content = f.read().strip()
    except FileNotFoundError:
        pass

    return render(request, 'cartoons/index.html', {
        'cartoons': cartoons,
        'news_content': news_content,
        'announcement_content': announcement_content,
        'current_sort': sort,
        'sort_label': SORT_LABELS[sort],
    })


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

    if request.user.is_authenticated:
        CartoonView.objects.get_or_create(cartoon=cartoon, user=request.user)
        # "author_last_seen_comments" НЕ обновляем здесь: comments/replies
        # подгружаются отдельными AJAX-запросами уже после рендера этой
        # страницы, и им нужен старый (ещё не сброшенный) cutoff, чтобы
        # посчитать "новых ответов" зелёным бейджем. Сброс происходит
        # через mark_comments_seen(), который фронтенд дёргает при уходе
        # со страницы (см. detail.html).

    likes_count = cartoon.likes.count()
    unique_views = cartoon.unique_views.count()
    if request.user.is_authenticated:
        user_liked = cartoon.likes.filter(user=request.user).exists()
    else:
        user_liked = False

    comment_sort = _get_comment_sort(request)

    if request.user.is_authenticated:
        user_favorited = cartoon.favorited_by.filter(
            user=request.user).exists()
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
        'author_profile_url': (
            _profile_url(cartoon.author) if cartoon.author else None),
        'author_avatar_link_url': _avatar_link_url(cartoon.author),
        'can_set_as_avatar': can_set_as_avatar,
        'is_used_as_avatar': is_used_as_avatar,
        'rec_sort': rec_sort,
        'rec_author_filter': rec_author_filter,
        'can_delete_cartoon': (request.user.is_authenticated
                               and request.user.is_staff),
        'can_moderate_comments': (
            request.user.is_authenticated
            and cartoon.author == request.user),
        'my_profile_url': (
            _profile_url(request.user)
            if request.user.is_authenticated else None),
        'og_url': settings.SITE_URL + reverse('detail', args=[pk]),
        'og_image_url': (
            settings.SITE_URL + cartoon.preview.url
            if cartoon.preview else None),
        'og_description': (
            cartoon.description[:200] if cartoon.description
            else 'Мультфильм «{}» от {}'.format(
                cartoon.title, _display_name(cartoon.author) or 'Аноним')),
    }
    if cartoon.frames_data:
        context['frames_json'] = json.dumps(cartoon.frames_data)
    if isinstance(cartoon.tags, list) and cartoon.tags:
        context['sorted_tags'] = sorted(
            t for t in cartoon.tags if isinstance(t, str))
    return render(request, 'cartoons/detail.html', context)


@require_POST
def delete_cartoon(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    cartoon = get_object_or_404(Cartoon, pk=pk)
    cartoon.delete()
    return JsonResponse({'ok': True, 'redirect_url': reverse('index')})


@require_POST
def delete_own_cartoon(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    cartoon = get_object_or_404(Cartoon, pk=pk)
    if cartoon.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)
    cartoon.delete()
    return JsonResponse({'ok': True, 'redirect_url': reverse('index')})


@require_GET
def get_recommendations(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)
    author_filter = request.GET.get('filter', 'all')
    sort = request.GET.get('sort', 'trending')
    if sort not in ('trending', 'trending_24h', 'new', 'popular'):
        sort = 'trending'
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 10

    if request.user.is_authenticated:
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        pref.rec_sort = sort
        pref.rec_author_filter = (author_filter == 'author')
        pref.save(update_fields=['rec_sort', 'rec_author_filter'])

    qs = Cartoon.objects.all()
    if author_filter == 'author' and cartoon.author:
        qs = qs.filter(author=cartoon.author)
    qs = qs.exclude(pk=pk)

    # Считаем лайки/просмотры через коррелированные подзапросы, а не
    # через annotate(Count(...)) на нескольких связях сразу: несколько
    # Count() c join к разным related-таблицам в одном запросе дают
    # декартово произведение строк до GROUP BY (лайки × просмотры на
    # каждый мульт), и запрос резко замедляется по мере роста лайков
    # и просмотров. Подзапросы этого не делают - каждый считается
    # отдельно на свою таблицу.
    now = timezone.now()
    likes_time_filter = Q()
    if sort == 'trending':
        likes_time_filter = Q(created_at__gte=now - timedelta(days=7))
    elif sort == 'trending_24h':
        likes_time_filter = Q(created_at__gte=now - timedelta(hours=24))

    if sort == 'new':
        order = ['-created_at']
    else:  # trending, trending_24h, popular
        likes_subquery = (
            CartoonLike.objects.filter(
                likes_time_filter, cartoon=OuterRef('pk'))
            .order_by().values('cartoon')
            .annotate(c=Count('id')).values('c')
        )
        qs = qs.annotate(sort_val=Coalesce(
            Subquery(likes_subquery, output_field=IntegerField()), 0))
        order = ['-sort_val', '-created_at']

    views_subquery = (
        CartoonView.objects.filter(cartoon=OuterRef('pk'))
        .order_by().values('cartoon')
        .annotate(c=Count('id')).values('c')
    )
    qs = qs.annotate(unique_views_count=Coalesce(
        Subquery(views_subquery, output_field=IntegerField()), 0))

    if request.user.is_authenticated:
        viewed_ids = list(
            CartoonView.objects.filter(
                user=request.user).values_list(
                'cartoon_id', flat=True)
        )
        qs = qs.annotate(
            is_viewed=Case(
                When(pk__in=viewed_ids, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        order = ['is_viewed'] + order

    qs = qs.select_related(
        'author',
        'author__preference',
        'author__preference__avatar').order_by(*order)

    start = (page - 1) * per_page
    end = start + per_page
    # +1 лишний, чтобы узнать has_next без отдельного count() на всём
    # (потенциально большом) отсортированном/аннотированном qs
    page_qs = list(qs[start:end + 1])
    has_next = len(page_qs) > per_page
    page_qs = page_qs[:per_page]

    show_author = (author_filter != 'author')
    html = ''.join(
        render_to_string('cartoons/cartoon_card.html',
                         {'cartoon': c,
                          'show_author': show_author,
                          'compact': True},
                         request=request)
        for c in page_qs
    )

    return JsonResponse({
        'html': html,
        'empty': (page == 1 and len(page_qs) == 0),
        'has_next': has_next,
    })


@require_POST
def toggle_cartoon_like(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    cartoon = get_object_or_404(Cartoon, pk=pk)
    like, created = CartoonLike.objects.get_or_create(
        cartoon=cartoon, user=request.user
    )
    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({'liked': liked, 'count': cartoon.likes.count()})


def _get_seen_cutoff(request, cartoon):
    """Таймстамп "последнего просмотра комментариев" автора мульта,
    но только для самого автора - все остальные получают None, то
    есть "не считать/не показывать бейдж непрочитанных"."""
    if (request.user.is_authenticated
            and cartoon.author_id == request.user.id):
        return cartoon.author_last_seen_comments
    return None


def _serialize_comment(comment, request, current_level=0,
                       max_inline_level=2, root_level=0,
                       cartoon_author_id=None, seen_cutoff=None):
    """Сериализует комментарий с вложенными ответами до
    max_inline_level.

    seen_cutoff (datetime или None) - таймстамп "последнего
    просмотра комментариев" автора мульта, захваченный в начале
    визита на эту страницу - используется для подсчёта
    new_replies_count (ответы на любой глубине, созданные после
    этого момента). Имеет смысл/передаётся только когда текущий
    зритель - автор мульта; None означает "не показывать бейдж
    непрочитанных" для всех остальных.
    """
    if request.user.is_authenticated:
        user_liked = comment.likes.filter(user=request.user).exists()
    else:
        user_liked = False

    author_url = _profile_url(comment.author) if comment.author else None

    likes_count = comment.likes_count

    replies_data = []
    has_more_replies = False
    has_deeper_replies = False
    per_used = 0

    if current_level < max_inline_level:
        rel = current_level - root_level
        per_used = 2 if rel == 0 else 1
        per_load = 3
        qs = comment.replies.select_related(
            'author', 'author__preference', 'author__preference__avatar')
        if request.user.is_authenticated:
            qs = qs.annotate(
                is_mine=Case(
                    When(
                        author=request.user,
                        then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField())
            ).order_by('is_mine', '-is_pinned', '-likes_count', 'created_at')
        else:
            qs = qs.order_by('-is_pinned', '-likes_count', 'created_at')
        total_r = qs.count()
        has_more_replies = total_r > per_used
        for r in qs[:per_used]:
            replies_data.append(
                _serialize_comment(
                    r,
                    request,
                    current_level + 1,
                    max_inline_level,
                    root_level,
                    cartoon_author_id,
                    seen_cutoff))
    elif current_level == max_inline_level:
        has_deeper_replies = comment.replies.exists()

    # Удалённый автором комментарий: текст и личность автора скрыты,
    # но лайки/закреп/ответы остаются рабочими (см. is_deleted ниже,
    # реальная строка в БД не удаляется - иначе пропали бы ответы).
    if comment.is_deleted:
        is_own = False
        display_text = 'Комментарий удалён'
        display_author_url = None
        display_avatar_url = _get_user_avatar_url(None)
        display_avatar_link_url = None
    else:
        is_own = (request.user.is_authenticated
                  and comment.author_id == request.user.id)
        display_text = comment.text
        display_author_url = author_url
        display_avatar_url = _get_user_avatar_url(comment.author)
        display_avatar_link_url = _avatar_link_url(comment.author)

    is_cartoon_author = (
        request.user.is_authenticated
        and cartoon_author_id is not None
        and request.user.id == cartoon_author_id)
    can_pin = is_cartoon_author
    can_delete = request.user.is_authenticated and request.user.is_staff
    can_delete_own = (
        not comment.is_deleted
        and (is_own or (is_cartoon_author and not is_own
                        and comment.author_id is not None)))

    can_block_author = (
        not comment.is_deleted
        and request.user.is_authenticated
        and comment.author_id is not None
        and comment.author_id != request.user.id
        and not comment.author.is_staff)
    author_pref = (
        getattr(comment.author, 'preference', None)
        if can_block_author else None)
    show_block_label = can_block_author and (
        is_cartoon_author or (author_pref and author_pref.is_troll))
    is_blocked_author = show_block_label and UserBlock.objects.filter(
        blocker=request.user, blocked=comment.author).exists()

    total_replies_count = _count_descendant_comments(comment.id)
    new_replies_count = (
        _count_descendant_comments(comment.id, created_after=seen_cutoff)
        if seen_cutoff is not None else 0)

    return {
        'id': comment.id,
        'author': '' if comment.is_deleted else comment.display_author(),
        'author_url': display_author_url,
        'avatar_url': display_avatar_url,
        'avatar_link_url': display_avatar_link_url,
        'text': display_text,
        'is_deleted': comment.is_deleted,
        'is_edited': comment.is_edited,
        'is_pinned': comment.is_pinned,
        'is_own': is_own,
        'can_pin': can_pin,
        'can_delete': can_delete,
        'can_delete_own': can_delete_own,
        'show_block_label': show_block_label,
        'is_blocked_author': is_blocked_author,
        'block_url': (
            reverse(
                'toggle_block_user', args=[comment.author.username])
            if show_block_label else None),
        'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
        'likes_count': likes_count,
        'user_liked': user_liked,
        'level': comment.level,
        'per_used': per_used,
        'per_load': per_load if current_level < max_inline_level else 3,
        'replies': replies_data,
        'has_more_replies': has_more_replies,
        'has_deeper_replies': has_deeper_replies,
        'replies_count': total_replies_count,
        'new_replies_count': new_replies_count,
    }


@require_GET
def get_comments(request, pk):
    cartoon = get_object_or_404(Cartoon, pk=pk)
    page = max(1, int(request.GET.get('page', 1)))
    sort = request.GET.get('sort', 'popular')
    per_page = 10

    qs = Comment.objects.filter(cartoon=cartoon, parent=None).select_related(
        'author', 'author__preference', 'author__preference__avatar'
    )
    if request.user.is_authenticated:
        qs = qs.annotate(
            is_mine=Case(
                When(
                    author=request.user,
                    then=Value(0)),
                default=Value(1),
                output_field=IntegerField())
        )
        if sort == 'newest':
            qs = qs.order_by('is_mine', '-is_pinned', '-created_at')
        else:
            qs = qs.order_by(
                'is_mine',
                '-is_pinned',
                '-likes_count',
                '-created_at')
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
    seen_cutoff = _get_seen_cutoff(request, cartoon)
    data = [
        _serialize_comment(
            c,
            request,
            max_inline_level=0,
            cartoon_author_id=cartoon_author_id,
            seen_cutoff=seen_cutoff) for c in comments]

    return JsonResponse({
        'comments': data,
        'has_next': end < total,
        'total': total,
    })


@require_GET
def get_replies(request, comment_pk):
    parent = get_object_or_404(
        Comment.objects.select_related('cartoon'),
        pk=comment_pk)

    try:
        per_page = int(request.GET.get('per_page', 0))
        if per_page < 1 or per_page > 50:
            raise ValueError
    except (ValueError, TypeError):
        per_page = 10

    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except (ValueError, TypeError):
        offset = 0

    qs = parent.replies.select_related(
        'author',
        'author__preference',
        'author__preference__avatar')
    if request.user.is_authenticated:
        qs = qs.annotate(
            is_mine=Case(
                When(
                    author=request.user,
                    then=Value(0)),
                default=Value(1),
                output_field=IntegerField())
        ).order_by('is_mine', '-is_pinned', '-likes_count', 'created_at')
    else:
        qs = qs.order_by('-is_pinned', '-likes_count', 'created_at')

    total = qs.count()
    start = offset
    end = offset + per_page
    replies = list(qs[start:end])

    child_level = parent.level + 1
    cartoon_author_id = parent.cartoon.author_id
    seen_cutoff = _get_seen_cutoff(request, parent.cartoon)
    data = [
        _serialize_comment(
            r,
            request,
            current_level=child_level,
            max_inline_level=0,
            cartoon_author_id=cartoon_author_id,
            seen_cutoff=seen_cutoff) for r in replies]

    return JsonResponse({'comments': data, 'has_next': end < total})


@require_GET
def get_thread(request, comment_pk):
    """Возвращает ветку для модалки: корневой комментарий +
    постраничные прямые ответы на большой глубине вложенности."""
    root = get_object_or_404(
        Comment.objects.select_related('cartoon'),
        pk=comment_pk)
    page = max(1, int(request.GET.get('page', 1)))
    per_page = 10

    qs = root.replies.select_related(
        'author',
        'author__preference',
        'author__preference__avatar')
    if request.user.is_authenticated:
        qs = qs.annotate(
            is_mine=Case(
                When(
                    author=request.user,
                    then=Value(0)),
                default=Value(1),
                output_field=IntegerField())
        ).order_by('is_mine', '-is_pinned', '-likes_count', 'created_at')
    else:
        qs = qs.order_by('-is_pinned', '-likes_count', 'created_at')

    per_page = 3
    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    replies = list(qs[start:end])

    cartoon_author_id = root.cartoon.author_id
    seen_cutoff = _get_seen_cutoff(request, root.cartoon)
    max_inline = root.level + 3
    child_level = root.level + 1
    replies_data = [
        _serialize_comment(
            r,
            request,
            current_level=child_level,
            max_inline_level=max_inline,
            root_level=child_level,
            cartoon_author_id=cartoon_author_id,
            seen_cutoff=seen_cutoff) for r in replies]

    root_data = _serialize_comment(
        root,
        request,
        current_level=root.level,
        max_inline_level=root.level - 1,
        root_level=root.level,
        cartoon_author_id=cartoon_author_id,
        seen_cutoff=seen_cutoff)
    root_data['replies'] = replies_data
    root_data['has_more_replies'] = end < total
    root_data['per_used'] = per_page
    root_data['per_load'] = per_page

    return JsonResponse(
        {'root': root_data, 'has_next': end < total, 'page': page})


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
        return JsonResponse(
            {'error': 'Войдите, чтобы оставить комментарий'}, status=403)

    if cartoon.author_id and UserBlock.objects.filter(
            blocker_id=cartoon.author_id, blocked=request.user).exists():
        return JsonResponse(
            {'error': 'Автор заблокировал вас'}, status=403)

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

    if request.user == cartoon.author:
        Cartoon.objects.filter(
            pk=pk).update(
            author_last_seen_comments=timezone.now())

    data = _serialize_comment(
        comment,
        request,
        current_level=level,
        max_inline_level=level - 1,
        cartoon_author_id=cartoon.author_id,
        seen_cutoff=_get_seen_cutoff(request, cartoon))
    return JsonResponse(data, status=201)


@require_POST
def mark_comments_seen(request, pk):
    """Вызывается (через navigator.sendBeacon), когда автор мульта
    уходит со страницы мульта - сбрасывает author_last_seen_comments,
    чтобы бейджи непрочитанных ответов и счётчик "новых комментариев"
    на личной странице начинали считать заново от этого момента, а
    не раньше."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    updated = Cartoon.objects.filter(
        pk=pk, author=request.user
    ).update(author_last_seen_comments=timezone.now())
    if not updated:
        return JsonResponse({'error': 'forbidden'}, status=403)
    return JsonResponse({'ok': True})


@require_POST
def pin_comment(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    comment = get_object_or_404(
        Comment.objects.select_related('cartoon'),
        pk=comment_pk)
    if comment.cartoon.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)
    comment.is_pinned = not comment.is_pinned
    comment.save(update_fields=['is_pinned'])
    return JsonResponse({'pinned': comment.is_pinned})


@require_GET
def get_comment_descendants_count(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    get_object_or_404(Comment, pk=comment_pk)
    return JsonResponse({'count': _count_descendant_comments(comment_pk)})


@require_POST
def delete_comment(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    comment = get_object_or_404(Comment, pk=comment_pk)
    comment.delete()
    return JsonResponse({'ok': True})


@require_POST
def delete_own_comment(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    comment = get_object_or_404(
        Comment.objects.select_related('cartoon'), pk=comment_pk)
    is_cartoon_author = comment.cartoon.author == request.user
    if comment.author != request.user and not is_cartoon_author:
        return JsonResponse({'error': 'forbidden'}, status=403)
    if comment.is_deleted:
        return JsonResponse({'error': 'Комментарий уже удалён'}, status=400)
    # Не удаляем саму запись - иначе пропали бы ответы под ней
    # (Comment.parent -> on_delete=CASCADE). Просто прячем текст и
    # авторство, оставляя лайки/закреп/ответы рабочими.
    comment.text = ''
    comment.is_deleted = True
    comment.save(update_fields=['text', 'is_deleted'])
    return JsonResponse({'ok': True})


@require_POST
def edit_comment(request, comment_pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    comment = get_object_or_404(Comment, pk=comment_pk)
    if comment.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)
    if comment.is_deleted:
        return JsonResponse({'error': 'Комментарий удалён'}, status=400)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    text = body.get('text', '').strip()
    if not text:
        return JsonResponse(
            {'error': 'Комментарий не может быть пустым'}, status=400)
    if len(text) > 2000:
        return JsonResponse(
            {'error': 'Слишком длинный (макс. 2000 символов)'}, status=400)
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
        comment=comment, user=request.user
    )
    if not created:
        like.delete()
        liked = False
        Comment.objects.filter(
            pk=comment_pk).update(
            likes_count=F('likes_count') - 1)
    else:
        liked = True
        Comment.objects.filter(
            pk=comment_pk).update(
            likes_count=F('likes_count') + 1)

    comment.refresh_from_db(fields=['likes_count'])
    return JsonResponse({'liked': liked, 'count': comment.likes_count})


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
        if cartoon.author != request.user:
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
        description = request.POST.get('description', '')[:1000]

        try:
            fps = int(fps_str)
            if fps < 1 or fps > 30:
                raise ValueError
        except (ValueError, TypeError):
            return render(request, 'cartoons/editor.html', {
                'cartoon': cartoon,
                'error': 'FPS должен быть целым числом от 1 до 30'
            })

        # Преобразуем теги из JSON и валидируем содержимое
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            tags = []
        tags = _clean_tags(tags)

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
                    UserPreference.objects.create(user=user)
                    send_verification_email(user)
                request.session['pending_user_id'] = user.id
                return redirect('verification_sent')
            except Exception:
                form.add_error(
                    None,
                    'Не удалось отправить письмо подтверждения. '
                    'Попробуйте позже.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def user_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    pref, _ = UserPreference.objects.get_or_create(user=profile_user)
    tab = request.GET.get('tab', 'album')
    if tab not in ('album', 'comments', 'liked', 'favorites'):
        tab = 'album'

    total_cartoons = Cartoon.objects.filter(author=profile_user).count()

    user_note = ''
    if request.user.is_authenticated and request.user != profile_user:
        try:
            note_obj = UserNote.objects.get(
                author=request.user, about=profile_user)
            user_note = note_obj.text
        except UserNote.DoesNotExist:
            pass

    is_own_profile = request.user == profile_user

    can_block = (
        request.user.is_authenticated
        and not is_own_profile
        and not profile_user.is_staff)
    is_blocked = (
        can_block
        and UserBlock.objects.filter(
            blocker=request.user, blocked=profile_user).exists())

    context = {
        'profile_user': profile_user,
        'profile_display_name': _display_name(profile_user),
        'profile_description': pref.description,
        'active_tab': tab,
        'user_note': user_note,
        'is_own_profile': is_own_profile,
        'total_cartoons': total_cartoons,
        'profile_avatar_url': _get_user_avatar_url(profile_user),
        'avatar_link_url': _avatar_link_url(profile_user),
        'can_block': can_block,
        'is_blocked': is_blocked,
        'block_url': (
            reverse('toggle_block_user', args=[profile_user.username])
            if can_block else None),
    }

    if tab == 'album':
        sort = request.GET.get('sort', 'new')
        if sort not in SORT_LABELS:
            sort = 'new'

        if sort == 'popular':
            cartoon_list = Cartoon.objects.filter(
                author=profile_user).annotate(
                like_count=Count('likes', distinct=True),
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-is_pinned', '-like_count', '-created_at')
        elif sort == 'trending':
            week_ago = timezone.now() - timedelta(days=7)
            cartoon_list = Cartoon.objects.filter(
                author=profile_user).annotate(
                recent_likes=Count(
                    'likes',
                    filter=Q(
                        likes__created_at__gte=week_ago),
                    distinct=True),
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-is_pinned', '-recent_likes', '-created_at')
        elif sort == 'trending_24h':
            day_ago = timezone.now() - timedelta(hours=24)
            cartoon_list = Cartoon.objects.filter(
                author=profile_user).annotate(
                recent_likes=Count(
                    'likes',
                    filter=Q(
                        likes__created_at__gte=day_ago),
                    distinct=True),
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-is_pinned', '-recent_likes', '-created_at')
        else:
            cartoon_list = Cartoon.objects.filter(
                author=profile_user).annotate(
                unique_views_count=Count('unique_views', distinct=True),
            ).order_by('-is_pinned', '-created_at')

        if is_own_profile:
            cartoon_list = cartoon_list.annotate(
                new_comments_count=Count(
                    'comments',
                    filter=(
                        Q(comments__created_at__gt=F(
                            'author_last_seen_comments')) |
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
    fav, created = Favorite.objects.get_or_create(
        user=request.user, cartoon=cartoon)
    if not created:
        fav.delete()
        favorited = False
    else:
        favorited = True

    return JsonResponse({'favorited': favorited})


@require_GET
def get_user_profile_comments(request, username):
    profile_user = get_object_or_404(User, username=username)

    comment_type = request.GET.get('type', 'user')
    sort = request.GET.get('sort', 'newest')
    page = max(1, int(request.GET.get('page', 1)))
    per_page = 10

    if comment_type == 'cartoon':
        base_filter = Comment.objects.filter(
            cartoon__author=profile_user, is_deleted=False)
        related = ('author', 'author__preference', 'cartoon')
    else:
        base_filter = Comment.objects.filter(
            author=profile_user, is_deleted=False)
        related = ('cartoon',)

    total = base_filter.count()
    start = (page - 1) * per_page
    end = start + per_page

    if sort == 'popular':
        page_qs = list(
            base_filter.select_related(*related)
            .order_by('-likes_count', '-created_at')[start:end]
        )
    else:
        ids = list(base_filter.order_by(
            '-created_at').values_list('id', flat=True)[start:end])
        page_qs = list(
            Comment.objects.filter(id__in=ids)
            .select_related(*related)
            .order_by('-created_at')
        )

    comment_ids = [c.id for c in page_qs]
    if request.user.is_authenticated:
        liked_ids = set(
            CommentLike.objects.filter(
                comment_id__in=comment_ids, user=request.user)
            .values_list('comment_id', flat=True)
        )
    else:
        liked_ids = set()

    if comment_type == 'user':
        author_url = _profile_url(profile_user)
        avatar_url = _get_user_avatar_url(profile_user)
        avatar_link_url = _avatar_link_url(profile_user)

    data = []
    for c in page_qs:
        user_liked = c.id in liked_ids

        if comment_type == 'cartoon':
            author_url = _profile_url(c.author) if c.author else None
            avatar_url = _get_user_avatar_url(c.author)
            avatar_link_url = _avatar_link_url(c.author)

        data.append({
            'id': c.id,
            'author': c.display_author(),
            'author_url': author_url,
            'avatar_url': avatar_url,
            'avatar_link_url': avatar_link_url,
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

    if not cartoon.preview:
        return JsonResponse({'error': 'У мульта нет превью'}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}

    try:
        avatar_content = _build_avatar_gif(cartoon, body)
    except Exception as e:
        return JsonResponse(
            {'error': f'Ошибка создания аватара: {e}'}, status=500)

    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    if pref.avatar_gif:
        pref.avatar_gif.delete(save=False)
    pref.avatar = cartoon
    pref.avatar_gif.save(
        f'avatar_{
            request.user.id}.gif',
        avatar_content,
        save=False)
    pref.save()

    return JsonResponse({
        'ok': True,
        'avatar_url': pref.avatar_gif.url,
    })


@require_POST
def delete_avatar(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    if pref.avatar_gif:
        pref.avatar_gif.delete(save=False)
    pref.avatar = None
    pref.save()

    return JsonResponse(
        {'ok': True, 'avatar_url': _get_user_avatar_url(request.user)})


def _extract_cartoon_pk_from_link(link):
    """Достаёт pk мульта из вставленной админом строки - полной
    ссылки на страницу мульта, голого пути или просто числа.
    Возвращает None (а не выбрасывает исключение) для всего
    нераспознанного, чтобы вызывающий код мог показать понятную
    ошибку "битая ссылка" вместо 500-й."""
    link = (link or '').strip()
    if not link:
        return None
    match = re.search(r'/cartoon/(\d+)/?', link)
    if match:
        return int(match.group(1))
    if link.isdigit():
        return int(link)
    return None


def _require_superuser(request):
    return (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.is_superuser)


@login_required
def admin_default_avatar_crop(request, pk):
    """Страница обрезки общесайтового аватара по умолчанию, доступна
    только суперпользователю. Открывается со страницы редактирования
    SiteSettings в админке (см. SiteSettingsAdmin.response_change),
    где вставленная ссылка разбирается и валидируется - эта вьюха
    независимо перепроверяет права и пригодность мульта, поскольку
    один лишь URL легко угадать/подделать кому угодно."""
    if not _require_superuser(request):
        return HttpResponseForbidden(
            'Только суперпользователь может это сделать.')
    cartoon = get_object_or_404(Cartoon, pk=pk)
    fc = _frames_count(cartoon)
    if not cartoon.preview or not (1 <= fc <= 10):
        messages.error(
            request,
            'У этого мульта нет подходящего превью для аватара '
            '(нужно от 1 до 10 кадров).')
        return redirect('admin:cartoons_sitesettings_change', 1)
    return render(request, 'cartoons/admin_default_avatar_crop.html', {
        'cartoon': cartoon,
    })


@require_POST
def set_default_avatar(request, pk):
    if not _require_superuser(request):
        return JsonResponse({'error': 'forbidden'}, status=403)

    cartoon = get_object_or_404(Cartoon, pk=pk)
    fc = _frames_count(cartoon)
    if not (1 <= fc <= 10):
        return JsonResponse(
            {'error': 'Мульт должен иметь от 1 до 10 кадров'}, status=400)
    if not cartoon.preview:
        return JsonResponse({'error': 'У мульта нет превью'}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}

    try:
        avatar_content = _build_avatar_gif(cartoon, body)
    except Exception as e:
        return JsonResponse(
            {'error': f'Ошибка создания аватара: {e}'}, status=500)

    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
    if site_settings.default_avatar_gif:
        site_settings.default_avatar_gif.delete(save=False)
    site_settings.default_avatar_gif.save(
        'default_avatar.gif', avatar_content, save=False)
    site_settings.save()

    return JsonResponse({
        'ok': True,
        'avatar_url': site_settings.default_avatar_gif.url,
    })


@require_GET
def get_avatar_cartoons(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)

    per_page = 12
    offset = max(0, int(request.GET.get('offset', 0)))

    qs = Cartoon.objects.filter(
        author=request.user).only(
        'id', 'title', 'preview', 'frames_data')

    eligible = [
        {'id': c.id, 'title': c.title,
            'preview_url': c.preview.url if c.preview else None}
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


def privacy_policy(request):
    return render(request, 'cartoons/privacy_policy.html')


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

    # send_verification_email сама обновляет токен (expires_at,
    # updated_at) через update_or_create и отправляет письмо.
    send_verification_email(user)

    messages.success(request, 'Письмо с подтверждением отправлено повторно.')
    return redirect('verification_sent')


def _resolve_user_by_identifier(raw):
    """Находит цель для UserBlock по произвольному тексту - это
    может быть голый C-key или вставленная ссылка на профиль (C-key
    и есть последний сегмент этой ссылки): пользователь может
    добавить кого-то в чёрный список "по нику или ссылке"."""
    raw = (raw or '').strip()
    if not raw:
        return None
    if '/' in raw:
        segments = [s for s in raw.split('/') if s]
        raw = segments[-1] if segments else raw
    return User.objects.filter(username=raw).first()


@require_POST
def toggle_block_user(request, username):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'error': 'forbidden'}, status=400)
    if target.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    block, created = UserBlock.objects.get_or_create(
        blocker=request.user, blocked=target)
    if not created:
        block.delete()
        blocked = False
    else:
        blocked = True
    return JsonResponse({'blocked': blocked})


@require_POST
def blocklist_add(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)

    target = _resolve_user_by_identifier(body.get('identifier', ''))
    if target is None:
        return JsonResponse(
            {'error': 'Пользователь не найден'}, status=404)
    if target == request.user:
        return JsonResponse(
            {'error': 'Нельзя заблокировать самого себя'}, status=400)
    if target.is_staff:
        return JsonResponse(
            {'error': 'Нельзя заблокировать этого пользователя'}, status=403)

    UserBlock.objects.get_or_create(blocker=request.user, blocked=target)
    return JsonResponse({
        'ok': True,
        'username': target.username,
        'display_name': _display_name(target),
        'profile_url': _profile_url(target),
        'block_url': reverse(
            'toggle_block_user', args=[target.username]),
    })


@require_POST
def toggle_cartoon_pin(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login_required'}, status=401)
    cartoon = get_object_or_404(Cartoon, pk=pk)
    if cartoon.author != request.user:
        return JsonResponse({'error': 'forbidden'}, status=403)
    cartoon.is_pinned = not cartoon.is_pinned
    cartoon.save(update_fields=['is_pinned'])
    return JsonResponse({'pinned': cartoon.is_pinned})


@login_required
def account_settings(request):
    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    blocklist = User.objects.filter(
        blocked_by_users__blocker=request.user
    ).select_related('preference').order_by('username')
    context = {
        'password_form': PasswordChangeForm(user=request.user),
        'current_username': request.user.username,
        'current_display_name': pref.display_name,
        'current_description': pref.description,
        'blocklist': blocklist,
    }
    return render(request, 'cartoons/account_settings.html', context)


@require_POST
@login_required
def change_password(request):
    form = PasswordChangeForm(user=request.user, data=request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Пароль успешно изменён.')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(reverse('account_settings') + '?tab=password')


@require_POST
@login_required
def update_username(request):
    """Меняет C-key (User.username) - технический идентификатор для
    входа и ссылки на профиль. Требования те же, что раньше были у
    ника: до 15 символов, только буквы/цифры/@/./+/-/_."""
    new_username = request.POST.get('username', '').strip()
    redirect_url = reverse('account_settings') + '?tab=profile'

    if not new_username or new_username == request.user.username:
        return redirect(redirect_url)

    if len(new_username) > 15:
        messages.error(
            request, 'C-key не может быть длиннее 15 символов.')
        return redirect(redirect_url)
    try:
        User._meta.get_field('username').run_validators(new_username)
    except Exception:
        messages.error(
            request,
            'C-key может содержать только буквы, цифры и символы '
            '@/./+/-/_')
        return redirect(redirect_url)
    if User.objects.filter(
            username=new_username).exclude(pk=request.user.pk).exists():
        messages.error(request, 'Этот C-key уже занят.')
        return redirect(redirect_url)

    request.user.username = new_username
    request.user.save(update_fields=['username'])
    messages.success(request, 'C-key изменён.')
    return redirect(redirect_url)


@require_POST
@login_required
def update_display_name(request):
    new_name = request.POST.get('display_name', '').strip()
    redirect_url = reverse('account_settings') + '?tab=profile'

    if len(new_name) > 15:
        messages.error(
            request, 'Отображаемое имя не может быть длиннее 15 символов.')
        return redirect(redirect_url)

    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    pref.display_name = new_name
    pref.save(update_fields=['display_name'])
    messages.success(request, 'Отображаемое имя сохранено.')
    return redirect(redirect_url)


@require_POST
@login_required
def update_description(request):
    text = request.POST.get('description', '').strip()
    if len(text) > 1000:
        messages.error(
            request, 'Описание слишком длинное (макс. 1000 символов)')
        return redirect(reverse('account_settings') + '?tab=description')
    pref, _ = UserPreference.objects.get_or_create(user=request.user)
    pref.description = text
    pref.save(update_fields=['description'])
    messages.success(request, 'Описание сохранено.')
    return redirect(reverse('account_settings') + '?tab=description')
