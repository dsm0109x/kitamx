"""
Custom template filters for email templates.
"""
from django import template
from django.utils.formats import localize
from django.utils import timezone
from datetime import datetime
import pytz

register = template.Library()


@register.filter(name='currency_mx')
def currency_mx(value):
    """
    Format currency with Mexican formatting (comas).

    Example:
        1000.50 → 1,000.50
        500000 → 500,000.00
    """
    try:
        value = float(value)
        # Formatear con comas y 2 decimales
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return value


@register.filter(name='friendly_date')
def friendly_date(value):
    """
    Convert datetime to friendly Spanish format.

    Example:
        2025-11-15 14:30 → 15 de noviembre, 2025
    """
    if not value:
        return ''

    try:
        mexico_tz = pytz.timezone('America/Mexico_City')

        if isinstance(value, str):
            # ✅ String viene de metadata ya en timezone México
            # Parsear y hacer aware en México
            naive_dt = datetime.strptime(value, '%d/%m/%Y %H:%M')
            value = mexico_tz.localize(naive_dt)
        elif timezone.is_aware(value):
            # ✅ Datetime aware - convertir a México
            value = value.astimezone(mexico_tz)

        months_es = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }

        day = value.day
        month = months_es[value.month]
        year = value.year

        return f"{day} de {month}, {year}"
    except (ValueError, TypeError, AttributeError):
        return value


@register.filter(name='friendly_datetime')
def friendly_datetime(value):
    """
    Convert datetime to friendly Spanish format with time.

    Example:
        2025-11-15 14:30 → 15 de noviembre, 2025 a las 14:30
    """
    if not value:
        return ''

    try:
        mexico_tz = pytz.timezone('America/Mexico_City')

        if isinstance(value, str):
            # ✅ String viene de metadata ya en timezone México
            # Parsear y hacer aware en México
            naive_dt = datetime.strptime(value, '%d/%m/%Y %H:%M')
            value = mexico_tz.localize(naive_dt)
        elif timezone.is_aware(value):
            # ✅ Datetime aware - convertir a México
            value = value.astimezone(mexico_tz)

        months_es = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }

        day = value.day
        month = months_es[value.month]
        year = value.year
        hour = value.strftime('%H:%M')

        return f"{day} de {month}, {year} a las {hour}"
    except (ValueError, TypeError, AttributeError):
        return value


@register.filter(name='friendly_datetime_short')
def friendly_datetime_short(value):
    """
    Convert datetime to short friendly format.

    Example:
        2025-11-15 14:30 → 15 nov, 14:30
    """
    if not value:
        return ''

    try:
        mexico_tz = pytz.timezone('America/Mexico_City')

        if isinstance(value, str):
            # ✅ String viene de metadata ya en timezone México
            # Parsear y hacer aware en México
            naive_dt = datetime.strptime(value, '%d/%m/%Y %H:%M')
            value = mexico_tz.localize(naive_dt)
        elif timezone.is_aware(value):
            # ✅ Datetime aware - convertir a México
            value = value.astimezone(mexico_tz)

        months_short = {
            1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr',
            5: 'may', 6: 'jun', 7: 'jul', 8: 'ago',
            9: 'sep', 10: 'oct', 11: 'nov', 12: 'dic'
        }

        day = value.day
        month = months_short[value.month]
        hour = value.strftime('%H:%M')

        return f"{day} {month}, {hour}"
    except (ValueError, TypeError, AttributeError):
        return value
