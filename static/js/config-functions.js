/**
 * Global functions for /negocio/ configuration page
 * These functions need to be in global scope for onclick handlers
 */

// ========================================
// CSRF TOKEN HELPER
// ========================================
window.getCsrfToken = function() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) return csrfInput.value;

    const csrfCookie = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='));

    if (csrfCookie) {
        return csrfCookie.split('=')[1];
    }

    return '';
}

// ========================================
// MERCADO PAGO FUNCTIONS
// ========================================
window.connectMercadoPago = function() {
    showToast('Redirigiendo a Mercado Pago® para autorizar...', 'info');
    setTimeout(() => {
        window.location.href = '/negocio/mercadopago/oauth/';
    }, 1000);
}

window.disconnectMercadoPago = function() {
    if (!confirm('¿Desconectar Mercado Pago®?\n\nEsto desactivará tus links de pago activos.')) {
        return;
    }

    fetch('/incorporacion/api/desconectar-mp/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Mercado Pago® desconectado', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(data.error || 'Error desconectando', 'error');
        }
    })
    .catch(error => {
        showToast('Error de conexión', 'error');
    });
}

// ========================================
// CSD CERTIFICATE FUNCTIONS
// ========================================
window.deactivateCSD = function(certId, serialNumber) {
    if (confirm(`¿Desactivar certificado ${serialNumber}?\n\nEsto impedirá generar nuevas facturas con este certificado.`)) {
        // Note: The URL will be resolved by Django template engine
        const url = window.DEACTIVATE_CSD_URL || '/negocio/csd/desactivar/';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ certificate_id: certId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Certificado desactivado', 'success');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast(data.error || 'Error al desactivar', 'error');
            }
        });
    }
}

// ========================================
// TEST CONNECTION FUNCTION
// ========================================
window.testConnection = function(type) {
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    btn.disabled = true;

    let url = '';
    if (type === 'mercadopago' || type === 'mp') {
        url = window.TEST_MP_URL || '/negocio/probar-conexion-mp/';
    } else if (type === 'whatsapp') {
        url = window.TEST_WA_URL || '/negocio/probar-whatsapp/';
    } else if (type === 'email') {
        url = window.TEST_EMAIL_URL || '/negocio/probar-email/';
    }

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message || 'Conexión exitosa', 'success');
        } else {
            showToast(data.error || 'Error en la conexión', 'error');
        }
    })
    .catch(error => {
        showToast('Error de conexión', 'error');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// ========================================
// CSD UPLOAD MODAL FUNCTIONS
// ========================================
// NOTE: CSD modal functions are defined in the template (config/index.html)
// because they use Django template tags and have complex Dropzone initialization.
// The following functions are defined there:
// - window.showUploadCSDModal()
// - window.togglePasswordSettings()
// - window.validateCSDSettings()
// - window.saveCSDSettings()
// - window.checkValidationReadySettings()
// - window.resetValidationSettings()
// - window.setStepActiveSettings()
// - window.setStepCompletedSettings()