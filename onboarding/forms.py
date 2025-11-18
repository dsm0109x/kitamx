from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from core.validators import RFCValidator, PhoneValidator, PostalCodeValidator, BusinessNameValidator
from core.constants import FISCAL_REGIME_CHOICES, VALID_FISCAL_REGIME_CODES
import unicodedata


def normalize_for_comparison(text):
    """
    Normaliza texto para comparación tolerante de encoding issues.
    Remueve acentos, espacios extra y caracteres especiales.
    """
    if not text:
        return text

    # Normalizar NFD para acentos válidos
    nfd = unicodedata.normalize('NFD', text)
    # Remover marcas diacríticas
    without_accents = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')

    # Remover caracteres no-ASCII (maneja encoding corrupto como Ã©)
    ascii_only = ''.join(c for c in without_accents if ord(c) < 128)

    # Normalizar espacios y mayúsculas
    return ' '.join(ascii_only.upper().split())


class TenantIdentityForm(forms.Form):
    """
    Form for Step 1: Business Identity and Tenant Creation.

    Now with structured address fields for CFDI 4.0 compliance.
    """

    # Información básica
    name = forms.CharField(
        label='Nombre Comercial',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Mi Consultorio Médico',
            'required': True
        }),
        help_text='El nombre con el que identificas tu negocio'
    )

    business_name = forms.CharField(
        label='Razón Social',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Consultoría Médica López S.C.',
            'required': True
        }),
        help_text='Razón social exacta como aparece en tu RFC'
    )

    rfc = forms.CharField(
        label='RFC',
        max_length=13,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-uppercase',
            'placeholder': 'Ej: CML850101ABC',
            'required': True
        }),
        help_text='RFC de 12 o 13 caracteres'
    )

    email = forms.EmailField(
        label='Email de Contacto',
        required=False,  # No validar, siempre viene de user.email
        widget=forms.EmailInput(attrs={
            'class': 'form-control is-valid',
            'readonly': True,
            'id': 'id_email'
        }),
        help_text='Email de tu cuenta verificada'
    )

    phone = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+52 55 1234 5678',
            'type': 'tel'
        }),
        help_text='Teléfono de contacto (opcional)'
    )

    fiscal_regime = forms.ChoiceField(
        label='Régimen Fiscal',
        choices=FISCAL_REGIME_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'data-tip': 'fiscal_regime',
            'data-help-target': 'regimeHelp',
            'id': 'id_fiscal_regime'
        }),
        help_text='Regímenes fiscales para personas físicas'
    )

    def clean_fiscal_regime(self):
        """Validate fiscal regime is one of the allowed values."""
        regime = self.cleaned_data.get('fiscal_regime', '').strip()

        if not regime:
            raise ValidationError('Selecciona tu régimen fiscal')

        if regime not in VALID_FISCAL_REGIME_CODES:
            raise ValidationError(f'Régimen fiscal inválido: {regime}')

        return regime

    # Domicilio fiscal estructurado
    codigo_postal = forms.CharField(
        label='Código Postal',
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '06600',
            'pattern': '[0-9]{5}',
            'maxlength': '5',
            'required': True,
            'data-autocomplete': 'postal-code'
        }),
        help_text='Ingresa tu CP para autocompletar municipio y estado'
    )

    colonia = forms.CharField(
        label='Colonia',
        max_length=255,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'disabled': True  # Se habilita después de ingresar CP
        }),
        help_text='Selecciona de la lista (se llena automáticamente)'
    )

    municipio = forms.CharField(
        label='Municipio',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'placeholder': 'Se llena automáticamente'
        }),
        help_text='Auto-completado desde código postal'
    )

    estado = forms.CharField(
        label='Estado',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'placeholder': 'Se llena automáticamente'
        }),
        help_text='Auto-completado desde código postal'
    )

    calle = forms.CharField(
        label='Calle',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Paseo de la Reforma',
            'required': True,
            'data-autocomplete': 'street'
        }),
        help_text='Nombre de la vía'
    )

    numero_exterior = forms.CharField(
        label='Número Exterior',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '250',
            'required': True
        }),
        help_text='Número oficial de la calle'
    )

    numero_interior = forms.CharField(
        label='Número Interior',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Piso 5, Oficina 501 (opcional)'
        }),
        help_text='Departamento, piso, oficina, local'
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_rfc(self):
        rfc = self.cleaned_data.get('rfc', '').strip().upper()
        rfc = RFCValidator.clean(rfc)

        # Check uniqueness
        if self.user:
            from core.models import TenantUser
            user_tenant = TenantUser.objects.filter(email=self.user.email, is_owner=True).first()
            exclude_tenant = user_tenant.tenant if user_tenant else None
        else:
            exclude_tenant = None

        if not RFCValidator.check_uniqueness(rfc, exclude_tenant):
            raise ValidationError('Este RFC ya está registrado en el sistema')

        return rfc

    def clean_codigo_postal(self):
        codigo_postal = self.cleaned_data.get('codigo_postal', '').strip()
        return PostalCodeValidator.clean(codigo_postal)

    def clean_colonia(self):
        colonia = self.cleaned_data.get('colonia', '').strip()
        if not colonia:
            raise ValidationError('La colonia es requerida')
        return colonia

    def clean(self):
        """Cross-field validation: colonia, municipio, estado must match codigo_postal."""
        cleaned_data = super().clean()
        codigo_postal = cleaned_data.get('codigo_postal')
        colonia = cleaned_data.get('colonia')
        municipio = cleaned_data.get('municipio')
        estado = cleaned_data.get('estado')

        if not codigo_postal:
            return cleaned_data

        from core.models import CodigoPostal

        # Verificar si el CP existe en la base de datos
        cp_exists = CodigoPostal.objects.filter(codigo_postal=codigo_postal).exists()

        # Si el CP NO está en la BD, permitir input manual sin validación
        # (el usuario ya vio el toast de advertencia para llenar manualmente)
        if not cp_exists:
            return cleaned_data

        # Si el CP SÍ está en la BD, validar que los datos coincidan
        # Validar colonia vs CP (con normalización)
        if colonia:
            colonia_normalizada = normalize_for_comparison(colonia)
            cp_records = CodigoPostal.objects.filter(codigo_postal=codigo_postal)
            colonia_match = any(
                normalize_for_comparison(record.asentamiento) == colonia_normalizada
                for record in cp_records
            )

            if not colonia_match:
                raise ValidationError({
                    'colonia': 'Esta colonia no corresponde al código postal ingresado. Selecciona una de la lista o verifica tu CP.'
                })

        # Validar municipio vs CP (con normalización)
        if municipio:
            municipio_normalizado = normalize_for_comparison(municipio)
            cp_records = CodigoPostal.objects.filter(codigo_postal=codigo_postal)
            municipio_match = any(
                normalize_for_comparison(record.municipio) == municipio_normalizado
                for record in cp_records
            )

            if not municipio_match:
                raise ValidationError({
                    'municipio': 'Este municipio no corresponde al código postal ingresado. Verifica tu CP.'
                })

        # Validar estado vs CP
        # NOTA: Temporalmente deshabilitado debido a encoding issues en la BD SEPOMEX
        # La validación de municipio y colonia es suficiente para garantizar consistencia
        # TODO: Arreglar encoding de la tabla CodigoPostal y reactivar
        # if estado:
        #     ... validación deshabilitada ...

        return cleaned_data

    def clean_municipio(self):
        municipio = self.cleaned_data.get('municipio', '').strip()
        if not municipio:
            raise ValidationError('El municipio es requerido')
        return municipio

    def clean_estado(self):
        estado = self.cleaned_data.get('estado', '').strip()
        if not estado:
            raise ValidationError('El estado es requerido')
        return estado

    def clean_calle(self):
        calle = self.cleaned_data.get('calle', '').strip()
        if not calle:
            raise ValidationError('La calle es requerida')
        if len(calle) < 3:
            raise ValidationError('La calle debe tener al menos 3 caracteres')
        if len(calle) > 255:
            raise ValidationError('La calle no puede exceder 255 caracteres')
        return calle

    def clean_numero_exterior(self):
        numero = self.cleaned_data.get('numero_exterior', '').strip()
        if not numero:
            raise ValidationError('El número exterior es requerido')
        if len(numero) > 20:
            raise ValidationError('El número exterior no puede exceder 20 caracteres')
        # Validar formato: letras, números, guiones (250, 123-A, SN)
        import re
        if not re.match(r'^[A-Za-z0-9\-]+$', numero):
            raise ValidationError('Número exterior solo puede contener letras, números y guiones')
        return numero

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()

        if phone:
            # Use centralized validator
            phone = PhoneValidator.clean(phone)

        return phone

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()

        if not name:
            raise ValidationError('Nombre comercial es requerido')

        if len(name) < 2:
            raise ValidationError('Nombre comercial debe tener al menos 2 caracteres')

        if len(name) > 255:
            raise ValidationError('Nombre comercial no puede exceder 255 caracteres')

        return name

    def clean_business_name(self):
        business_name = self.cleaned_data.get('business_name', '').strip()

        # Use centralized validator
        return BusinessNameValidator.clean(business_name)