import requests
import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email',
                             widget=forms.EmailInput(attrs={'class': 'form-con\
trol'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')

        # Проверка на дубликат в базе
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует.')

        # Проверка через API
        try:
            api_url = f"https://rapid-email-verifier.fly.dev/api/validate?emai\
l={email}"
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException:
            # Если API недоступен, просто логируем и пропускаем проверку
            logger.warning(f"Email verification API failed for {email}")
            return email

        # Анализ результата API
        status = data.get('status')
        if status == 'INVALID_FORMAT':
            raise ValidationError('Некорректный формат email.')
        elif status == 'INVALID_DOMAIN':
            raise ValidationError('Указанный домен не принимает почту.')
        elif status == 'DISPOSABLE':
            raise ValidationError('Одноразовые email-адреса не разрешены.')
        elif status == 'INVALID':
            raise ValidationError('Указанный email не существует.')

        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].help_text = 'Обязательное поле. Не более 150 с\
имволов. Только буквы, цифры и символы @/./+/-/_.'
        self.fields['password1'].help_text = 'Пароль должен содержать минимум \
8 символов и не может быть слишком простым или состоять только из цифр.'
        self.fields['password2'].help_text = 'Введите тот же пароль для подтве\
рждения.'
