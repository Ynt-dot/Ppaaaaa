from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls import include

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.editor, name='editor_create'),
    path('edit/<int:pk>/', views.editor, name='editor_edit'),
    path('cartoon/<int:pk>/', views.detail, name='detail'),
    path('cartoon/<int:pk>/like/', views.toggle_cartoon_like,
         name='toggle_cartoon_like'),
    path('cartoon/<int:pk>/comments/', views.get_comments, name='get_comments'),
    path('cartoon/<int:pk>/comments/add/', views.add_comment,
         name='add_comment'),
    path('comment/<int:comment_pk>/edit/', views.edit_comment, name='edit_comment'),
    path('comment/<int:comment_pk>/like/', views.toggle_comment_like,
         name='toggle_comment_like'),
    path('comment/<int:comment_pk>/replies/', views.get_replies, name='get_replies'),
    path('comment/<int:comment_pk>/thread/', views.get_thread, name='get_thread'),
    path('set-comment-sort/', views.set_comment_sort, name='set_comment_sort'),
    path('register/', views.register, name='register'),
    path('user/<str:username>/', views.user_profile, name='user_profile'),
    path('user/<str:username>/comments/', views.get_user_profile_comments,
         name='user_profile_comments'),
    path('user/<str:username>/note/', views.save_user_note, name='save_user_note'),
    path('cartoon/<int:pk>/recommendations/', views.get_recommendations, name='get_recommendations'),
    path('cartoon/<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('cartoon/<int:pk>/set-as-avatar/', views.set_as_avatar, name='set_as_avatar'),
    path('my-avatar-cartoons/', views.get_avatar_cartoons, name='get_avatar_cartoons'),
    path('delete-avatar/', views.delete_avatar, name='delete_avatar'),
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    path(
        'verification-sent/',
        views.verification_sent,
        name='verification_sent'
    ),
    path(
        'resend-verification/',
        views.resend_verification,
        name='resend_verification'
    ),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
