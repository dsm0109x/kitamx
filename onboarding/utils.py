import re
import unicodedata
from django.utils.text import slugify
from core.models import Tenant
from core.validators import RFCValidator, PostalCodeValidator, PhoneValidator


def generate_unique_slug(name, max_length=50):
    """
    Generate a unique slug for tenant from business name
    """
    # Create base slug
    base_slug = slugify(name)[:max_length]

    # If empty after slugify, use fallback
    if not base_slug:
        base_slug = 'empresa'

    # Check if slug exists
    slug = base_slug
    counter = 1

    while Tenant.objects.filter(slug=slug).exists():
        # Add counter to make it unique
        counter_str = f'-{counter}'
        max_base_length = max_length - len(counter_str)
        slug = f"{base_slug[:max_base_length]}{counter_str}"
        counter += 1

        # Safety check to prevent infinite loop
        if counter > 9999:
            import uuid
            slug = f"{base_slug[:40]}-{str(uuid.uuid4())[:8]}"
            break

    return slug


def validate_rfc_format(rfc):
    """
    Validate RFC format for Mexican tax ID
    Returns (is_valid, error_message)

    Delegates to centralized validator for consistency.
    """
    is_valid, error_message = RFCValidator.validate(rfc)
    if is_valid:
        return True, "RFC válido"
    return False, error_message


def clean_business_name(name):
    """
    Clean and normalize business name
    """
    if not name:
        return ""

    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name.strip())

    # Normalize unicode characters
    name = unicodedata.normalize('NFKD', name)

    # Capitalize properly
    name = name.title()

    return name


def validate_postal_code_mexico(postal_code):
    """
    Validate Mexican postal code
    Returns (is_valid, error_message)

    Delegates to centralized validator for consistency.
    """
    is_valid, error_message = PostalCodeValidator.validate(postal_code)
    if is_valid:
        return True, "Código postal válido"
    return False, error_message


def format_phone_number(phone):
    """
    Format phone number for Mexico

    Uses centralized phone validator for consistency.
    """
    if not phone:
        return ""

    # Use centralized cleaner
    cleaned = PhoneValidator.clean_number(phone)
    if cleaned:
        return cleaned

    return phone  # Return original if can't format


def get_fiscal_regime_name(code):
    """
    Get the full name of a fiscal regime by code
    """
    regimes = {
        '601': 'General de Ley Personas Morales',
        '603': 'Personas Morales con Fines no Lucrativos',
        '605': 'Sueldos y Salarios e Ingresos Asimilados a Salarios',
        '606': 'Arrendamiento',
        '607': 'Régimen de Enajenación o Adquisición de Bienes',
        '608': 'Demás ingresos',
        '610': 'Residentes en el Extranjero sin Establecimiento Permanente en México',
        '611': 'Ingresos por Dividendos (socios y accionistas)',
        '612': 'Personas Físicas con Actividades Empresariales y Profesionales',
        '614': 'Ingresos por intereses',
        '615': 'Régimen de los ingresos por obtención de premios',
        '616': 'Sin obligaciones fiscales',
        '620': 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos',
        '621': 'Incorporación Fiscal',
        '622': 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras',
        '623': 'Opcional para Grupos de Sociedades',
        '624': 'Coordinados',
        '625': 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas',
        '626': 'Régimen Simplificado de Confianza',
    }

    return regimes.get(code, f"Régimen {code}")