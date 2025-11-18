"""Forms for accounts app with enhanced validation."""
from __future__ import annotations
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils import timezone
from allauth.account.forms import SignupForm, LoginForm, ResetPasswordForm

from .models import User, UserProfile
from .validators import E164PhoneValidator, TurnstileValidator


class KitaSignupForm(SignupForm):
    """
    Custom signup form for Kita with enhanced validation.

    Extends allauth SignupForm to include additional fields
    required for the Mexican market.
    """
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Apellidos'
        })
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        error_messages={
            'required': 'Debes aceptar los términos y condiciones'
        }
    )
    privacy_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        error_messages={
            'required': 'Debes aceptar la política de privacidad'
        }
    )
    accepts_marketing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    # Turnstile token (hidden field, populated by widget)
    cf_turnstile_response = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,  # We'll validate in clean()
        label=''
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with custom widget attributes."""
        super().__init__(*args, **kwargs)

        # Customize existing fields
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Correo electrónico'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña'
        })

    def save(self, request: HttpRequest) -> User:
        """
        Save the user with additional fields.

        Args:
            request: HTTP request object

        Returns:
            Created User instance

        Raises:
            ValidationError: If email is already in use (generic message)
        """
        try:
            user = super().save(request)
        except ValueError as e:
            # Allauth raises ValueError when email already exists
            # Convert to ValidationError with generic message (no data leakage)
            raise ValidationError(
                'No pudimos crear tu cuenta. Por favor, verifica tus datos o intenta con otro correo.'
            )

        # Save additional fields
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.accepts_marketing = self.cleaned_data.get('accepts_marketing', False)

        # Record terms acceptance
        if self.cleaned_data.get('terms_accepted'):
            user.terms_accepted_at = timezone.now()
        if self.cleaned_data.get('privacy_accepted'):
            user.privacy_accepted_at = timezone.now()

        user.save()
        return user

    def clean_cf_turnstile_response(self) -> str:
        """
        Validate Turnstile token server-side.

        This prevents bot registrations by verifying the Turnstile
        challenge response with Cloudflare's API.
        """
        token = self.cleaned_data.get('cf_turnstile_response', '')

        # Get request from form (passed via self.request if available)
        request = getattr(self, 'request', None)
        ip_address = None

        if request:
            ip_address = TurnstileValidator.get_client_ip(request)

        # Validate token
        validator = TurnstileValidator()
        validator(token, ip_address)

        return token


class KitaLoginForm(LoginForm):
    """
    Custom login form for Kita with enhanced styling and anti-bot protection.

    Extends allauth LoginForm with Bootstrap classes and Turnstile validation.
    """

    # Turnstile token (hidden field, populated by widget)
    cf_turnstile_response = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,  # We'll validate in clean()
        label=''
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with custom widget attributes."""
        super().__init__(*args, **kwargs)

        # Customize fields
        self.fields['login'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Correo electrónico'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })
        self.fields['remember'].widget.attrs.update({
            'class': 'form-check-input'
        })

    def clean_cf_turnstile_response(self) -> str:
        """
        Validate Turnstile token server-side to prevent credential stuffing.

        This critical security measure blocks automated login attempts
        and brute force attacks.
        """
        token = self.cleaned_data.get('cf_turnstile_response', '')

        # Get request from form
        request = getattr(self, 'request', None)
        ip_address = None

        if request:
            ip_address = TurnstileValidator.get_client_ip(request)

        # Validate token
        validator = TurnstileValidator()
        validator(token, ip_address)

        return token


class KitaResetPasswordForm(ResetPasswordForm):
    """
    Custom password reset form with anti-bot protection.

    Extends allauth ResetPasswordForm with Turnstile validation
    to prevent email flooding attacks.
    """

    # Turnstile token (hidden field, populated by widget)
    cf_turnstile_response = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,  # We'll validate in clean()
        label=''
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with custom widget attributes."""
        super().__init__(*args, **kwargs)

        # Customize email field
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Correo electrónico'
        })

    def clean_cf_turnstile_response(self) -> str:
        """
        Validate Turnstile token server-side to prevent email flooding.

        This critical security measure blocks automated password reset
        requests that could be used to harass users or DoS email service.
        """
        token = self.cleaned_data.get('cf_turnstile_response', '')

        # Get request from form
        request = getattr(self, 'request', None)
        ip_address = None

        if request:
            ip_address = TurnstileValidator.get_client_ip(request)

        # Validate token
        validator = TurnstileValidator()
        validator(token, ip_address)

        return token


class UserProfileForm(forms.ModelForm):
    """
    Form for editing user profile preferences.

    Handles user preferences including timezone, language,
    theme and notification settings.
    """

    class Meta:
        model = UserProfile
        fields = [
            'bio', 'location', 'website', 'timezone', 'language', 'theme',
            'email_notifications', 'push_notifications', 'sms_notifications'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Cuéntanos un poco sobre ti...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ciudad, País'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://tu-sitio-web.com'
            }),
            'timezone': forms.Select(attrs={'class': 'form-select'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'push_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserUpdateForm(forms.ModelForm):
    """
    Form for updating user basic information.

    Handles updates to user's personal information
    with enhanced phone validation.
    """

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellidos'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono'
            }),
        }

    def clean_phone(self) -> str:
        """
        Validate and format phone number.

        Returns:
            Formatted phone number in E.164 format

        Raises:
            ValidationError: If phone format is invalid
        """
        phone = self.cleaned_data.get('phone', '')
        if phone:
            try:
                validator = E164PhoneValidator()
                phone = validator(phone)
            except ValidationError:
                raise ValidationError('Ingresa un número de teléfono válido')
        return phone


class PasswordChangeForm(forms.Form):
    """
    Custom password change form with security validation.

    Enforces password complexity requirements and
    validates current password before allowing change.
    """
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña actual'
        }),
        label='Contraseña actual'
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nueva contraseña'
        }),
        label='Nueva contraseña'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmar nueva contraseña'
        }),
        label='Confirmar nueva contraseña'
    )

    def __init__(self, user: User, *args: Any, **kwargs: Any) -> None:
        """
        Initialize with user instance.

        Args:
            user: User instance changing password
            *args: Variable arguments
            **kwargs: Keyword arguments
        """
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self) -> str:
        """
        Validate current password.

        Returns:
            Current password if valid

        Raises:
            ValidationError: If password is incorrect
        """
        current_password = self.cleaned_data['current_password']
        if not self.user.check_password(current_password):
            raise ValidationError('La contraseña actual es incorrecta')
        return current_password

    def clean(self) -> dict[str, Any]:
        """
        Validate form and ensure passwords match.

        Returns:
            Cleaned form data

        Raises:
            ValidationError: If passwords don't match or are invalid
        """
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise ValidationError('Las nuevas contraseñas no coinciden')

            # Validate password strength
            if len(new_password1) < 8:
                raise ValidationError('La contraseña debe tener al menos 8 caracteres')

            # Check for at least one uppercase, one lowercase, and one number
            has_upper = any(c.isupper() for c in new_password1)
            has_lower = any(c.islower() for c in new_password1)
            has_digit = any(c.isdigit() for c in new_password1)

            if not (has_upper and has_lower and has_digit):
                raise ValidationError(
                    'La contraseña debe contener mayúsculas, minúsculas y números'
                )

        return cleaned_data

    def save(self) -> User:
        """
        Save the new password.

        Returns:
            Updated User instance
        """
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save(update_fields=['password'])
        return self.user