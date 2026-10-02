"""
Конфигурация URL для проекта Ppaaaaa.

Список `urlpatterns` направляет URL-адреса на view. Подробнее см.:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Примеры:
Функциональные view
    1. Добавьте импорт: from my_app import views
    2. Добавьте URL в urlpatterns: path('', views.home, name='home')
View на основе классов
    1. Добавьте импорт: from other_app.views import Home
    2. Добавьте URL в urlpatterns: path('', Home.as_view(), name='home')
Подключение другого URLconf
    1. Импортируйте функцию include(): from django.urls import include, path
    2. Добавьте URL в urlpatterns: path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('cartoons.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
