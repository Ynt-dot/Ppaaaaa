from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email',
                             widget=forms.EmailInput(attrs={'class':
                                                            'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует.')
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        # Русские подсказки
        self.fields['username'].help_text = 'Обязательное поле. Не более 150 с\
имволов. Только буквы, цифры и символы @/./+/-/_.'
        self.fields['password1'].help_text = 'Пароль должен содержать минимум \
8 символов и не может быть слишком простым или состоять только из цифр.'
        self.fields['password2'].help_text = 'Введите тот же пароль для подтве\
рждения.'
