/**
 * URL Constants - Spanish URLs for Kita Project
 *
 * Centralizes all URL patterns in JavaScript for frontend consistency.
 * All user-facing URLs are in Spanish for better SEO and UX in the Mexican market.
 *
 * Usage:
 *   import { URLS } from './url-constants.js';
 *   fetch(URLS.PANEL.AJAX_TAREAS_PENDIENTES);
 *
 * Or in plain JS:
 *   <script src="{% static 'js/url-constants.js' %}"></script>
 *   fetch(URLS.PANEL.AJAX_TAREAS_PENDIENTES);
 *
 * Author: Kita Team
 * Date: 2025-11-14
 * Version: 1.0.0
 */

const URLS = {
    // ============================================
    // MAIN SECTIONS (Base paths)
    // ============================================

    PANEL: {
        BASE: '/panel/',
        AJAX_TAREAS_PENDIENTES: '/panel/ajax/tareas-pendientes/',
        AJAX_ACTIVIDAD: '/panel/ajax/actividad/',
        AJAX_ESTADISTICAS_RAPIDAS: '/panel/ajax/estadisticas-rapidas/',
        CREAR_ENLACE_FORM: '/panel/crear-enlace-form/',
        CREAR_ENLACE: '/panel/crear-enlace/',
        DETALLE: (type, id) => `/panel/detalle/${type}/${id}/`,
        CLIENTES_RECIENTES: '/panel/clientes-recientes/',
        RATE_LIMIT_INFO: '/panel/rate-limit-info/',
        API_BUSCAR: '/panel/api/buscar/',
    },

    ENLACES: {
        BASE: '/enlaces/',
        AJAX_DATOS: '/enlaces/ajax/datos/',
        AJAX_ESTADISTICAS: '/enlaces/ajax/estadisticas/',
        EXPORTAR: (format) => `/enlaces/exportar/${format}/`,
        DETALLE: (id) => `/enlaces/detalle/${id}/`,
        DUPLICAR: '/enlaces/duplicar/',
        CANCELAR: '/enlaces/cancelar/',
        ENVIAR_RECORDATORIO: '/enlaces/enviar-recordatorio/',
        EDITAR_DATOS: (id) => `/enlaces/editar-datos/${id}/`,
        EDITAR: '/enlaces/editar/',
    },

    FACTURAS: {
        BASE: '/facturas/',
        SUBIR: '/facturas/subir/',
        AJAX_FACTURAS: '/facturas/ajax/facturas/',
        AJAX_ESTADISTICAS: '/facturas/ajax/estadisticas/',
        DETALLE: (id) => `/facturas/detalle/${id}/`,
        CANCELAR: '/facturas/cancelar/',
        REENVIAR: '/facturas/reenviar/',
        DESCARGAR: (id, type) => `/facturas/descargar/${id}/${type}/`,
        EXPORTAR: '/facturas/exportar/',
        CSD_VALIDAR_LOCAL: '/facturas/csd/validar-local/',
        CSD_GUARDAR_COMPLETO: '/facturas/csd/guardar-completo/',
    },

    CUENTA: {
        BASE: '/cuenta/',
        ACTUALIZAR_PERFIL: '/cuenta/actualizar-perfil/',
        CAMBIAR_CONTRASENA: '/cuenta/cambiar-contrasena/',
        SESIONES: '/cuenta/sesiones/',
        REVOCAR_SESION: '/cuenta/revocar-sesion/',
        VERIFICAR_EMAIL: '/cuenta/verificar-email/',
    },

    NEGOCIO: {
        BASE: '/negocio/',
        EMPRESA: '/negocio/empresa/',
        ACTUALIZAR_EMPRESA: '/negocio/actualizar-empresa/',
        CSD: '/negocio/csd/',
        CSD_DESACTIVAR: '/negocio/csd/desactivar/',
        CSD_VALIDAR_AJAX: '/negocio/csd/validar-ajax/',
        CSD_SUBIR_AJAX: '/negocio/csd/subir-ajax/',
        INTEGRACIONES: '/negocio/integraciones/',
        ACTUALIZAR_MP: '/negocio/actualizar-mp-integracion/',
        PROBAR_MP: '/negocio/probar-conexion-mp/',
        ACTUALIZAR_WHATSAPP: '/negocio/actualizar-whatsapp/',
        PROBAR_WHATSAPP: '/negocio/probar-whatsapp/',
        ACTUALIZAR_EMAIL: '/negocio/actualizar-email/',
        PROBAR_EMAIL: '/negocio/probar-email/',
        NOTIFICACIONES: '/negocio/notificaciones/',
        ACTUALIZAR_NOTIFICACIONES: '/negocio/actualizar-notificaciones/',
        AVANZADO: '/negocio/avanzado/',
        ACTUALIZAR_AVANZADO: '/negocio/actualizar-avanzado/',
        WEBHOOKS: '/negocio/webhooks/',
    },

    AUDITORIA: {
        BASE: '/auditoria/',
        AJAX_REGISTROS: '/auditoria/ajax/registros/',
        AJAX_ESTADISTICAS: '/auditoria/ajax/estadisticas/',
        DETALLE: (id) => `/auditoria/detalle/${id}/`,
        EXPORTAR: '/auditoria/exportar/',
    },

    SUSCRIPCION: {
        BASE: '/suscripcion/',
        ACTIVAR: '/suscripcion/activar/',
        CANCELAR: '/suscripcion/cancelar/',
        PAGAR_VENCIDO: '/suscripcion/pagar-vencido/',
        DETALLE_PAGO: (id) => `/suscripcion/detalle-pago/${id}/`,
        REINTENTAR_PAGO: (id) => `/suscripcion/reintentar-pago/${id}/`,
        ESTADISTICAS: '/suscripcion/estadisticas/',
    },

    INCORPORACION: {
        BASE: '/incorporacion/',
        PASO1: '/incorporacion/paso1/',
        PASO2: '/incorporacion/paso2/',
        PASO3: '/incorporacion/paso3/',
        PASO4: '/incorporacion/paso4/',
        COMPLETADO: '/incorporacion/completado/',
        SUSCRIPCION_EXITO: '/incorporacion/suscripcion/exito/',
        SUSCRIPCION_ERROR: '/incorporacion/suscripcion/error/',
        SUSCRIPCION_PENDIENTE: '/incorporacion/suscripcion/pendiente/',
        API_VALIDAR_RFC: '/incorporacion/api/validar-rfc/',
        API_VALIDAR_RAZON_SOCIAL: '/incorporacion/api/validar-razon-social/',
        API_DESCONECTAR_MP: '/incorporacion/api/desconectar-mp/',
        API_INICIAR_PRUEBA: '/incorporacion/api/iniciar-prueba/',
    },

    IA: {
        BASE: '/ia/',
        CHAT_FLUJO: '/ia/chat/flujo/',
        CHAT_MENSAJE: '/ia/chat/mensaje/',
        CHAT_CONFIRMAR: '/ia/chat/confirmar/',
    },

    // ============================================
    // PUBLIC PAYMENT URLS (Creative branding)
    // ============================================

    PAGOS: {
        HOLA: (token) => `/hola/${token}/`,
        EXITO: (token) => `/exito/${token}/`,
        ERROR: (token) => `/error/${token}/`,
        PENDIENTE: (token) => `/pendiente/${token}/`,
        FACTURAR: (token) => `/facturar/${token}/`,
        DESCARGAR: (token, uuid) => `/descargar/${token}/${uuid}/`,
        TRACK_VIEW: '/track-view/',
        TRACK_INTERACTION: '/track-interaction/',
    },

    // ============================================
    // API ENDPOINTS (Internal)
    // ============================================

    API: {
        CODIGO_POSTAL: '/api/address/postal-code/',
        SUGGEST_STREETS: '/api/address/suggest-streets/',
        REVERSE_GEOCODE: '/api/address/reverse-geocode/',
        LOOKUP_RECIPIENT: '/api/recipients/lookup/',
    },

    // ============================================
    // LEGAL (Already in Spanish)
    // ============================================

    LEGAL: {
        PRIVACIDAD: '/legal/privacidad/',
        TERMINOS: '/legal/terminos/',
        COOKIES: '/legal/cookies/',
    },

    // ============================================
    // AUTH (Already in Spanish)
    // ============================================

    AUTH: {
        REGISTRARME: '/registrarme/',
        INGRESAR: '/ingresar/',
        SALIR: '/salir/',
        RECUPERAR_CONTRASENA: '/recuperar-contrasena/',
        VERIFICAR_EMAIL: '/verificar-email/',
        GOOGLE_LOGIN: '/accounts/google/login/',
    },

    // ============================================
    // TECHNICAL (Keep in English)
    // ============================================

    WEBHOOKS: {
        MERCADOPAGO: '/webhooks/mercadopago/',
        POSTMARK: '/webhooks/postmark/',
        KITA_BILLING: '/webhooks/kita-billing/',
    },

    HEALTH: {
        CHECK: '/health/',
        DETAILED: '/health/detailed/',
        READINESS: '/health/readiness/',
        LIVENESS: '/health/liveness/',
    },

    // ============================================
    // UTILITY FUNCTIONS
    // ============================================

    /**
     * Build URL with query parameters
     * @param {string} baseUrl - Base URL
     * @param {Object} params - Query parameters
     * @returns {string} Full URL with query string
     */
    buildWithParams: function(baseUrl, params) {
        if (!params || Object.keys(params).length === 0) {
            return baseUrl;
        }

        const queryString = Object.keys(params)
            .filter(key => params[key] !== null && params[key] !== undefined)
            .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
            .join('&');

        return `${baseUrl}?${queryString}`;
    },

    /**
     * Check if current path matches a pattern
     * @param {string} pattern - Pattern to match
     * @returns {boolean}
     */
    isCurrentPath: function(pattern) {
        return window.location.pathname.includes(pattern);
    },

    /**
     * Navigate to URL
     * @param {string} url - URL to navigate to
     */
    goto: function(url) {
        window.location.href = url;
    },
};

// ============================================
// EXPORT FOR ES6 MODULES
// ============================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { URLS };
}

// ============================================
// GLOBAL WINDOW OBJECT (for non-module scripts)
// ============================================

if (typeof window !== 'undefined') {
    window.URLS = URLS;
}

// Freeze object to prevent modifications
Object.freeze(URLS);

console.log('✅ URL Constants loaded (Spanish URLs)');
