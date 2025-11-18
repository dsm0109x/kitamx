"""
URL Constants - Spanish URLs for Kita Project

Centralizes all URL patterns in Spanish for consistency and easy maintenance.
All user-facing URLs are in Spanish for better SEO and UX in the Mexican market.

Author: Kita Team
Date: 2025-11-14
"""

# ============================================
# MAIN SECTIONS (App prefixes)
# ============================================

URL_PANEL = 'panel'  # Dashboard
URL_ENLACES = 'enlaces'  # Links
URL_FACTURAS = 'facturas'  # Invoicing
URL_CUENTA = 'cuenta'  # Account
URL_NEGOCIO = 'negocio'  # Business settings
URL_AUDITORIA = 'auditoria'  # Audit logs
URL_SUSCRIPCION = 'suscripcion'  # Subscription/Billing
URL_INCORPORACION = 'incorporacion'  # Onboarding
URL_IA = 'ia'  # AI Assistant

# ============================================
# COMMON ACTIONS (used across apps)
# ============================================

URL_CREAR = 'crear'  # Create
URL_EDITAR = 'editar'  # Edit
URL_ELIMINAR = 'eliminar'  # Delete
URL_DETALLE = 'detalle'  # Detail
URL_EXPORTAR = 'exportar'  # Export
URL_CANCELAR = 'cancelar'  # Cancel
URL_DUPLICAR = 'duplicar'  # Duplicate
URL_ACTIVAR = 'activar'  # Activate
URL_DESACTIVAR = 'desactivar'  # Deactivate
URL_ACTUALIZAR = 'actualizar'  # Update
URL_GUARDAR = 'guardar'  # Save
URL_SUBIR = 'subir'  # Upload
URL_DESCARGAR = 'descargar'  # Download
URL_ENVIAR = 'enviar'  # Send
URL_REENVIAR = 'reenviar'  # Resend
URL_VALIDAR = 'validar'  # Validate

# ============================================
# DATA FETCHING (AJAX/API)
# ============================================

URL_AJAX = 'ajax'  # AJAX endpoints
URL_API = 'api'  # API endpoints
URL_DATOS = 'datos'  # Data
URL_ESTADISTICAS = 'estadisticas'  # Stats
URL_BUSCAR = 'buscar'  # Search

# ============================================
# DASHBOARD SPECIFIC
# ============================================

URL_PANEL_TAREAS_PENDIENTES = 'tareas-pendientes'  # Pending tasks
URL_PANEL_ACTIVIDAD = 'actividad'  # Activity stream
URL_PANEL_ESTADISTICAS_RAPIDAS = 'estadisticas-rapidas'  # Quick stats
URL_PANEL_CREAR_ENLACE = 'crear-enlace'  # Create link
URL_PANEL_CREAR_ENLACE_FORM = 'crear-enlace-form'  # Create link form

# ============================================
# LINKS SPECIFIC
# ============================================

URL_ENLACES_RECORDATORIO = 'enviar-recordatorio'  # Send reminder

# ============================================
# PAYMENTS SPECIFIC (Public URLs)
# ============================================

URL_HOLA = 'hola'  # Public payment link prefix (creative, keep)
URL_EXITO = 'exito'  # Success
URL_ERROR = 'error'  # Failure
URL_PENDIENTE = 'pendiente'  # Pending
URL_FACTURAR = 'facturar'  # Self-service invoicing

# ============================================
# INVOICING SPECIFIC
# ============================================

URL_FACTURAS_CSD = 'csd'  # CSD certificates
URL_FACTURAS_CSD_VALIDAR_LOCAL = 'validar-local'  # Validate locally
URL_FACTURAS_CSD_GUARDAR_COMPLETO = 'guardar-completo'  # Save complete

# ============================================
# ONBOARDING SPECIFIC
# ============================================

URL_INCORPORACION_PASO1 = 'paso1'  # Step 1
URL_INCORPORACION_PASO2 = 'paso2'  # Step 2
URL_INCORPORACION_PASO3 = 'paso3'  # Step 3
URL_INCORPORACION_PASO4 = 'paso4'  # Step 4
URL_INCORPORACION_COMPLETADO = 'completado'  # Success/Completed
URL_INCORPORACION_VALIDAR_RFC = 'validar-rfc'  # Validate RFC
URL_INCORPORACION_VALIDAR_RAZON_SOCIAL = 'validar-razon-social'  # Validate business name
URL_INCORPORACION_DESCONECTAR_MP = 'desconectar-mp'  # Disconnect MercadoPago
URL_INCORPORACION_INICIAR_PRUEBA = 'iniciar-prueba'  # Start trial

# ============================================
# ACCOUNT SPECIFIC
# ============================================

URL_CUENTA_ACTUALIZAR_PERFIL = 'actualizar-perfil'  # Update profile
URL_CUENTA_CAMBIAR_CONTRASENA = 'cambiar-contrasena'  # Change password
URL_CUENTA_SESIONES = 'sesiones'  # Sessions
URL_CUENTA_REVOCAR_SESION = 'revocar-sesion'  # Revoke session
URL_CUENTA_VERIFICAR_EMAIL = 'verificar-email'  # Check email

# ============================================
# BUSINESS SETTINGS SPECIFIC
# ============================================

URL_NEGOCIO_EMPRESA = 'empresa'  # Business info
URL_NEGOCIO_ACTUALIZAR_EMPRESA = 'actualizar-empresa'  # Update business
URL_NEGOCIO_INTEGRACIONES = 'integraciones'  # Integrations
URL_NEGOCIO_NOTIFICACIONES = 'notificaciones'  # Notifications
URL_NEGOCIO_AVANZADO = 'avanzado'  # Advanced
URL_NEGOCIO_WEBHOOKS = 'webhooks'  # Webhooks info
URL_NEGOCIO_ACTUALIZAR_NOTIFICACIONES = 'actualizar-notificaciones'  # Update notifications
URL_NEGOCIO_ACTUALIZAR_AVANZADO = 'actualizar-avanzado'  # Update advanced
URL_NEGOCIO_ACTUALIZAR_MP = 'actualizar-mp-integracion'  # Update MP integration
URL_NEGOCIO_PROBAR_MP = 'probar-conexion-mp'  # Test MP connection
URL_NEGOCIO_ACTUALIZAR_WHATSAPP = 'actualizar-whatsapp'  # Update WhatsApp
URL_NEGOCIO_PROBAR_WHATSAPP = 'probar-whatsapp'  # Test WhatsApp
URL_NEGOCIO_ACTUALIZAR_EMAIL = 'actualizar-email'  # Update email
URL_NEGOCIO_PROBAR_EMAIL = 'probar-email'  # Test email
URL_NEGOCIO_CSD_DESACTIVAR = 'desactivar-csd'  # Deactivate CSD
URL_NEGOCIO_CSD_VALIDAR_AJAX = 'validar-ajax'  # Validate CSD (AJAX)
URL_NEGOCIO_CSD_SUBIR_AJAX = 'subir-ajax'  # Upload CSD (AJAX)

# ============================================
# SUBSCRIPTION/BILLING SPECIFIC
# ============================================

URL_SUSCRIPCION_PAGAR_VENCIDO = 'pagar-vencido'  # Pay overdue
URL_SUSCRIPCION_REINTENTAR_PAGO = 'reintentar-pago'  # Retry payment
URL_SUSCRIPCION_DETALLE_PAGO = 'detalle-pago'  # Payment detail

# ============================================
# AUDIT SPECIFIC
# ============================================

URL_AUDITORIA_REGISTROS = 'registros'  # Logs

# ============================================
# AI SPECIFIC
# ============================================

URL_IA_CHAT_FLUJO = 'flujo'  # Stream
URL_IA_CHAT_MENSAJE = 'mensaje'  # Message
URL_IA_CHAT_CONFIRMAR = 'confirmar'  # Confirm
URL_IA_CHAT = 'chat'  # Chat

# ============================================
# TRACKING (Payments public)
# ============================================

URL_TRACK_VIEW = 'track-view'  # Track view
URL_TRACK_INTERACTION = 'track-interaction'  # Track interaction

# ============================================
# TECHNICAL URLS (Keep in English - standards)
# ============================================

URL_WEBHOOKS = 'webhooks'  # Webhooks (technical standard)
URL_HEALTH = 'health'  # Health checks (DevOps standard)
URL_API_PREFIX = 'api'  # API prefix (technical standard)
URL_ADMIN = 'admin'  # Django admin

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_dashboard_url():
    """Get dashboard base URL"""
    return f'/{URL_PANEL}/'

def get_links_url():
    """Get links base URL"""
    return f'/{URL_ENLACES}/'

def get_invoices_url():
    """Get invoices base URL"""
    return f'/{URL_FACTURAS}/'

def get_account_url():
    """Get account base URL"""
    return f'/{URL_CUENTA}/'

def get_business_url():
    """Get business settings base URL"""
    return f'/{URL_NEGOCIO}/'

def get_subscription_url():
    """Get subscription base URL"""
    return f'/{URL_SUSCRIPCION}/'

def get_onboarding_url():
    """Get onboarding base URL"""
    return f'/{URL_INCORPORACION}/'

def get_public_payment_url(token):
    """Get public payment link URL"""
    return f'/{URL_HOLA}/{token}/'

def get_invoice_download_url(token, uuid):
    """Get invoice download URL"""
    return f'/{URL_DESCARGAR}/{token}/{uuid}/'
