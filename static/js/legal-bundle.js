/**
 * KITA LEGAL PAGES BUNDLE
 * Loading states para páginas legales
 *
 * @version 1.1 - Ripple eliminado
 * @size ~1.5KB
 */

'use strict';

// Conditional logger
const DEBUG = typeof window !== 'undefined' && (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.port === '8000'
);
const log = DEBUG ? console.log.bind(console) : () => {};

// ========================================
// LOADING STATE PARA BOTONES LEGALES
// ========================================
const LegalButtonLoading = (function() {
    function init() {
        const buttons = document.querySelectorAll(
            '.legal-footer .btn-outline-secondary, ' +
            '.legal-footer .btn-outline-primary, ' +
            '.legal-footer .btn-accent, ' +
            '.legal-footer .btn-primary'
        );

        buttons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                // No aplicar si es un link interno (anchor) o mailto
                const href = this.getAttribute('href');
                if (!href || href.startsWith('#') || href.startsWith('mailto:')) return;

                // Analytics tracking
                const trackingId = this.dataset.tracking;
                if (trackingId) {
                    log(`📊 Legal Nav Click: ${trackingId}`);
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'legal_navigation', {
                            'event_category': 'engagement',
                            'event_label': trackingId,
                            'value': 1
                        });
                    }
                }

                // Aplicar loading state
                const btnText = this.querySelector('.btn-text');
                let originalContent;

                if (btnText) {
                    originalContent = btnText.innerHTML;
                    btnText.textContent = 'Cargando';
                } else {
                    // Fallback para botones sin .btn-text
                    const textNodes = Array.from(this.childNodes).filter(
                        node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                    );
                    if (textNodes.length > 0) {
                        originalContent = textNodes[0].textContent;
                        textNodes[0].textContent = 'Cargando';
                    }
                }

                this.classList.add('is-loading');

                // Reset después de 5s
                setTimeout(() => {
                    this.classList.remove('is-loading');
                    if (btnText && originalContent) {
                        btnText.innerHTML = originalContent;
                    } else if (originalContent) {
                        const textNodes = Array.from(this.childNodes).filter(
                            node => node.nodeType === Node.TEXT_NODE
                        );
                        if (textNodes.length > 0) {
                            textNodes[0].textContent = originalContent;
                        }
                    }
                }, 5000);

                log(`🔄 Loading state applied to: ${trackingId || 'legal button'}`);
            });
        });

        log(`✅ Legal button loading initialized on ${buttons.length} buttons`);
    }

    return { init };
})();

// ========================================
// RIPPLE EFFECT - ELIMINADO
// ========================================
// Usuario no quiere efecto ripple en ningún botón

// ========================================
// INIT
// ========================================
function initLegalBundle() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLegalBundle);
        return;
    }

    try {
        LegalButtonLoading.init();
        // LegalButtonRipple.init(); - ELIMINADO

        log('✅ Legal Bundle initialized');
    } catch (err) {
        console.error('[Legal Bundle] Init error:', err);
    }
}

// Auto-initialize
initLegalBundle();
