"""
Centralized constants for Kita application.

This module provides application-wide constants to ensure consistency
and prevent duplication across models, forms, and templates.
"""

# ========================================
# FISCAL REGIMES (SAT - México)
# ========================================

# Regímenes fiscales más comunes para PERSONAS FÍSICAS
# Fuente: Anexo 20 del Código Fiscal de la Federación
FISCAL_REGIMES_PERSONAS_FISICAS = [
    ('612', '612 - Personas Físicas con Actividades Empresariales y Profesionales'),
    ('626', '626 - Régimen Simplificado de Confianza (RESICO)'),
    ('621', '621 - Incorporación Fiscal'),
    ('606', '606 - Arrendamiento'),
    ('605', '605 - Sueldos y Salarios'),
    ('615', '615 - Régimen de los ingresos por obtención de premios'),
]

# Choices para Django models/forms (con opción vacía)
FISCAL_REGIME_CHOICES = [('', 'Selecciona tu régimen fiscal')] + FISCAL_REGIMES_PERSONAS_FISICAS

# Solo códigos válidos (para validación)
VALID_FISCAL_REGIME_CODES = [code for code, _ in FISCAL_REGIMES_PERSONAS_FISICAS]

# Descripciones cortas para UI
FISCAL_REGIME_SHORT_NAMES = {
    '612': 'Actividades Empresariales y Profesionales',
    '626': 'RESICO',
    '621': 'Incorporación Fiscal',
    '606': 'Arrendamiento',
    '605': 'Sueldos y Salarios',
    '615': 'Premios',
}

# ========================================
# BUSINESS SETTINGS
# ========================================

# Trial period
DEFAULT_TRIAL_DAYS = 30

# Payment link expiry options (days)
LINK_EXPIRY_OPTIONS = [1, 3, 7]

# Monthly subscription price (MXN)
MONTHLY_SUBSCRIPTION_PRICE = 299.00
