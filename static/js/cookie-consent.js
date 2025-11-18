/**
 * Simple Cookie Consent Banner - GDPR Compliant
 *
 * Lightweight solution for cookie consent without external dependencies.
 * Stores consent in localStorage and shows banner only once.
 *
 * @version 1.0
 */

'use strict';

const KitaCookieConsent = (function() {
    // Debug mode (only with ?debug=1 in URL)
    const DEBUG = new URLSearchParams(window.location.search).get('debug') === '1';
    const log = DEBUG ? console.log.bind(console) : () => {};
    const warn = DEBUG ? console.warn.bind(console) : () => {};

    const STORAGE_KEY = 'kita_cookie_consent';
    const BANNER_ID = 'cookieConsentBanner';

    /**
     * Check if user has already given consent
     */
    function hasConsent() {
        try {
            const consent = localStorage.getItem(STORAGE_KEY);
            // Return true only if explicitly accepted or rejected (consent exists)
            // Return false if null (first time visitor)
            return consent !== null;
        } catch (e) {
            // localStorage might be blocked
            return false;
        }
    }

    /**
     * Save user consent
     */
    function saveConsent(accepted) {
        try {
            localStorage.setItem(STORAGE_KEY, accepted ? 'accepted' : 'rejected');
        } catch (e) {
            console.warn('[Cookie Consent] Could not save to localStorage:', e);
        }
    }

    /**
     * Hide banner with animation
     */
    function hideBanner() {
        const banner = document.getElementById(BANNER_ID);
        if (!banner) return;

        banner.style.opacity = '0';
        banner.style.transform = 'translateY(100%)';

        setTimeout(() => {
            banner.remove();
        }, 300);
    }

    /**
     * Handle accept button click
     */
    function handleAccept() {
        saveConsent(true);
        hideBanner();

        // Initialize analytics (GA4) if accepted
        initAnalytics();
    }

    /**
     * Handle reject button click
     */
    function handleReject() {
        saveConsent(false);
        hideBanner();
    }

    /**
     * Create and show consent banner
     */
    function showBanner() {
        // Don't show if already consented
        if (hasConsent()) {
            // User already accepted, init analytics
            if (typeof window.initAnalytics === 'function') {
                window.initAnalytics();
            }
            return;
        }

        // Create banner HTML
        const banner = document.createElement('div');
        banner.id = BANNER_ID;
        banner.className = 'cookie-consent-banner';
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-label', 'Aviso de cookies');
        banner.setAttribute('aria-live', 'polite');

        banner.innerHTML = `
            <div class="cookie-consent-content">
                <div class="cookie-consent-text">
                    <span class="iconoir-cookie me-2"></span>
                    <p class="mb-0">
                        Usamos cookies esenciales para el funcionamiento del sitio y cookies analíticas (Google Analytics) para mejorar tu experiencia.
                        <a href="/legal/cookies/" class="cookie-consent-link" target="_blank" rel="noopener">
                            Más información
                        </a>
                    </p>
                </div>
                <div class="cookie-consent-actions">
                    <button type="button"
                            class="btn btn-sm btn-outline-light"
                            id="cookieReject"
                            aria-label="Rechazar cookies opcionales">
                        Solo necesarias
                    </button>
                    <button type="button"
                            class="btn btn-sm btn-light"
                            id="cookieAccept"
                            aria-label="Aceptar todas las cookies">
                        Aceptar todas
                    </button>
                </div>
            </div>
        `;

        // Add to page
        document.body.appendChild(banner);

        // Trigger animation
        setTimeout(() => {
            banner.style.opacity = '1';
            banner.style.transform = 'translateY(0)';
        }, 100);

        // Attach event listeners
        document.getElementById('cookieAccept')?.addEventListener('click', handleAccept);
        document.getElementById('cookieReject')?.addEventListener('click', handleReject);
    }

    /**
     * Initialize Google Analytics 4 (GA4)
     * Only called when user accepts analytics cookies
     */
    function initAnalytics() {
        // Check if gtag is available (loaded from base template)
        if (typeof window.gtag === 'function') {
            // Update consent mode to granted
            window.gtag('consent', 'update', {
                'analytics_storage': 'granted'
            });
            log('[Cookie Consent] GA4 analytics enabled');
        } else {
            warn('[Cookie Consent] gtag not found - GA4 not loaded');
        }
    }

    /**
     * Initialize cookie consent
     */
    function init() {
        // Wait for DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        // Check if user already consented
        if (hasConsent()) {
            const consent = localStorage.getItem(STORAGE_KEY);
            if (consent === 'accepted') {
                // User already accepted, init analytics
                initAnalytics();
            }
            return;
        }

        // Show banner after short delay for better UX
        setTimeout(showBanner, 1000);
    }

    /**
     * Reset consent (for "Manage Cookies" button in footer)
     */
    function resetConsent() {
        try {
            localStorage.removeItem(STORAGE_KEY);

            // Disable analytics
            if (typeof window.gtag === 'function') {
                window.gtag('consent', 'update', {
                    'analytics_storage': 'denied'
                });
            }

            showBanner();
        } catch (e) {
            console.warn('[Cookie Consent] Could not reset consent:', e);
        }
    }

    // Public API
    return {
        init: init,
        hasConsent: hasConsent,
        reset: resetConsent
    };
})();

// Auto-initialize
KitaCookieConsent.init();

// Global function for footer button
window.resetCookieConsent = function() {
    KitaCookieConsent.reset();
};
