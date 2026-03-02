from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.editor, name='editor_create'),
    path('edit/<int:pk>/', views.editor, name='editor_edit'),
    path('cartoon/<int:pk>/', views.detail, name='detail'),
    path('register/', views.register, name='register'),
    path('user/<str:username>/', views.user_profile, name='user_profile'),
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
