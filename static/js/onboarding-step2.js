/**
 * Onboarding Step 2: MercadoPago OAuth Integration
 *
 * BUG FIX #64: Extracted from inline <script> in step2.html
 *
 * Handles:
 * - OAuth connection flow with PKCE
 * - Disconnect functionality
 * - Skip confirmation modal
 * - FAQ toggle interactions
 * - OAuth error handling
 * - Loading states and analytics
 *
 * @version 1.0
 */

'use strict';

(function() {
    // Get configuration from data attributes
    const config = {
        step3Url: document.getElementById('onboarding-config')?.dataset.step3Url || '/incorporacion/paso3/',  // 🇪🇸 Migrado
        disconnectUrl: document.getElementById('onboarding-config')?.dataset.disconnectUrl || '/incorporacion/api/desconectar-mp/',  // 🇪🇸 Migrado
        mpConnected: document.getElementById('onboarding-config')?.dataset.mpConnected === 'true',
        hasOauthCode: document.getElementById('onboarding-config')?.dataset.hasOauthCode === 'true'
    };

    // Utility: Get CSRF token
    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) return csrfInput.value;
        const csrfCookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return csrfCookie ? csrfCookie.split('=')[1] : '';
    }

    // ========================================
    // FAQ TOGGLE FUNCTIONALITY
    // ========================================
    function initFAQToggle() {
        const faqContainer = document.querySelector('.faq-container');
        if (!faqContainer) return;

        faqContainer.addEventListener('click', function(e) {
            const question = e.target.closest('.faq-question');
            if (!question) return;

            const faqItem = question.parentElement;
            const answer = faqItem.querySelector('.faq-answer');
            const isActive = question.classList.contains('active');

            // Toggle active state
            question.classList.toggle('active');
            answer.classList.toggle('active');

            // Update aria-expanded
            question.setAttribute('aria-expanded', !isActive);
        });
    }

    // ========================================
    // CONNECT BUTTON HANDLER
    // ========================================
    function initConnectButton() {
        const connectBtn = document.getElementById('connectBtn');
        let isConnecting = false; // Flag to prevent double-click

        if (!connectBtn) return;

        connectBtn.addEventListener('click', function(e) {
            e.preventDefault();

            // Prevent double-click
            if (isConnecting) {
                return;
            }
            isConnecting = true;

            // Disable button
            this.disabled = true;

            // Change button text with loading state
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Redirigiendo a Mercado Pago®...';

            // Use Loading Progress System
            if (typeof loading !== 'undefined' && loading.start) {
                loading.start([
                    'Preparando conexión...',
                    'Redirigiendo a Mercado Pago®...'
                ]);

                // Stage transition
                setTimeout(() => loading.next(), 300);
            } else {
                // Fallback
                const loadingTopbar = document.getElementById('loadingTopbar');
                const loadingMessage = document.getElementById('loadingMessage');
                if (loadingTopbar) loadingTopbar.classList.add('active');
                if (loadingMessage) loadingMessage.classList.add('active');
            }

            // Analytics
            if (typeof gtag !== 'undefined') {
                gtag('event', 'mp_connect_start', {
                    'event_category': 'onboarding',
                    'event_label': 'step2_mercadopago'
                });
            }

            // Redirect after brief delay
            setTimeout(() => {
                window.location.href = this.href;
            }, 600);
        });
    }

    // ========================================
    // RECONNECT BUTTON HANDLER
    // ========================================
    function initReconnectButton() {
        const reconnectBtn = document.getElementById('reconnectBtn');
        if (!reconnectBtn) return;

        reconnectBtn.addEventListener('click', function(e) {
            e.preventDefault();

            // Disable button
            this.disabled = true;

            // Change text
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Reconectando...';

            // Loading
            if (typeof loading !== 'undefined' && loading.start) {
                loading.start([
                    'Preparando reconexión...',
                    'Redirigiendo a Mercado Pago®...'
                ]);
                setTimeout(() => loading.next(), 300);
            }

            // Analytics
            if (typeof gtag !== 'undefined') {
                gtag('event', 'mp_reconnect_start', {
                    'event_category': 'settings',
                    'event_label': 'mercadopago'
                });
            }

            // Redirect
            setTimeout(() => {
                window.location.href = this.href;
            }, 600);
        });
    }

    // ========================================
    // SKIP MODAL FUNCTIONALITY
    // ========================================
    window.showSkipModal = function() {
        // Check if already skipped before (sessionStorage memory - only this session)
        const skipMemoryKey = 'kita_skip_mp_confirmed';
        const alreadySkipped = sessionStorage.getItem(skipMemoryKey);

        if (alreadySkipped === 'true') {
            // Already confirmed skip, go directly to next step
            window.location.href = config.step3Url;
            return;
        }

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('skipModal'));
        modal.show();

        // Save decision when confirms skip (in sessionStorage)
        const skipLink = document.querySelector('#skipModal [href*="step3"]');
        if (skipLink) {
            skipLink.addEventListener('click', function() {
                sessionStorage.setItem(skipMemoryKey, 'true');
            }, { once: true });
        }

        // Analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'mp_skip_modal_shown', {
                'event_category': 'onboarding',
                'event_label': 'step2_mercadopago'
            });
        }
    };

    // ========================================
    // DISCONNECT FUNCTIONALITY
    // ========================================
    window.disconnectMP = function() {
        // Show modal instead of confirm()
        const modal = new bootstrap.Modal(document.getElementById('disconnectModal'));
        modal.show();
    };

    window.confirmDisconnect = async function() {
        // Hide modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('disconnectModal'));
        modal.hide();

        // Disable button
        const btn = document.getElementById('confirmDisconnectBtn');
        if (btn) btn.disabled = true;

        // Use Loading Progress System
        if (typeof loading !== 'undefined' && loading.start) {
            loading.start([
                'Desconectando...',
                'Limpiando tokens...',
                'Actualizando configuración...'
            ]);
        } else if (typeof showToast !== 'undefined') {
            showToast('Desconectando Mercado Pago®...', 'info');
        }

        const requestData = {
            url: config.disconnectUrl,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        };

        try {
            const response = await fetch(requestData.url, {
                method: requestData.method,
                headers: requestData.headers
            });

            // Stage transition
            if (typeof loading !== 'undefined' && loading.next) {
                loading.next();
            }

            const result = await response.json();

            // Stage transition
            if (typeof loading !== 'undefined' && loading.next) {
                loading.next();
            }

            if (result.success) {
                // Complete loading
                if (typeof loading !== 'undefined' && loading.done) {
                    loading.done();
                }

                // Show warning if active links exist
                if (result.warning && result.active_links_count > 0) {
                    showToast(`⚠️ ${result.warning}`, 'warning');
                    setTimeout(() => {
                        showToast('Cuenta desconectada exitosamente', 'success');
                    }, 1500);
                } else {
                    showToast('Cuenta desconectada exitosamente', 'success');
                }

                // Analytics
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'mp_disconnect_success', {
                        'event_category': 'settings',
                        'event_label': 'mercadopago',
                        'active_links_count': result.active_links_count || 0
                    });
                }

                setTimeout(() => window.location.reload(), result.warning ? 2500 : 1000);
            } else {
                // Cancel loading
                if (typeof loading !== 'undefined' && loading.cancel) {
                    loading.cancel();
                }

                showToast(result.error || 'Error al desconectar', 'error');
                if (btn) btn.disabled = false;
            }
        } catch (error) {
            console.error('[MP] Disconnect error:', error);

            // Use Error Recovery System if available
            if (typeof window.ErrorRecovery !== 'undefined') {
                window.ErrorRecovery.handleError(error, requestData, {
                    context: 'disconnect_mercadopago',
                    autoRetry: false  // BUG FIX #71: Don't auto-retry DELETE operations
                });

                // Re-enable button on final failure
                if (btn) btn.disabled = false;
            } else {
                // BUG FIX #82: Fallback - usar mensaje del error si está disponible
                if (typeof loading !== 'undefined' && loading.cancel) {
                    loading.cancel();
                }
                const errorMsg = error.message || 'Error de conexión. Por favor intenta de nuevo.';
                showToast(errorMsg, 'error');
                if (btn) btn.disabled = false;
            }

            // Analytics
            if (typeof gtag !== 'undefined') {
                gtag('event', 'mp_disconnect_error', {
                    'event_category': 'errors',
                    'event_label': 'mercadopago',
                    'error_type': window.ErrorRecovery?.getErrorType(error) || 'unknown'
                });
            }
        }
    };

    // ========================================
    // OAUTH ERROR HANDLING
    // ========================================
    function handleOAuthErrors() {
        const urlParams = new URLSearchParams(window.location.search);
        if (!urlParams.has('error')) return;

        const errorType = urlParams.get('error');
        const errorDesc = urlParams.get('error_description');

        console.error('[OAuth] Error:', errorType, errorDesc);

        // Specific error messages
        const errorMessages = {
            'access_denied': 'Cancelaste la autorización. Puedes intentar conectar de nuevo cuando quieras.',
            'invalid_client': 'Error de configuración de la aplicación. Contacta a soporte.',
            'invalid_request': 'Error en la solicitud OAuth. Por favor intenta de nuevo.',
            'unauthorized_client': 'La aplicación no está autorizada. Contacta a soporte.',
            'server_error': 'Mercado Pago® tuvo un problema temporal. Intenta más tarde.',
            'temporarily_unavailable': 'Servicio temporalmente no disponible. Intenta en unos minutos.'
        };

        const message = errorMessages[errorType] || 'No se pudo conectar con Mercado Pago®. Por favor intenta de nuevo.';

        if (typeof showToast !== 'undefined') {
            showToast(message, 'error');
        }

        // Analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'mp_oauth_error', {
                'event_category': 'errors',
                'event_label': 'mercadopago_oauth',
                'error_type': errorType,
                'error_description': errorDesc
            });
        }

        // BUG FIX #74: Clean URL params to prevent re-showing error on reload
        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('error');
        cleanUrl.searchParams.delete('error_description');
        window.history.replaceState({}, document.title, cleanUrl.toString());
    }

    // ========================================
    // OAUTH SUCCESS HANDLER
    // ========================================
    function handleOAuthSuccess() {
        if (!config.mpConnected || !config.hasOauthCode) return;

        // Success callback
        setTimeout(() => {
            showToast('¡Mercado Pago® conectado exitosamente! 🎉', 'success');

            // Analytics
            if (typeof gtag !== 'undefined') {
                gtag('event', 'mp_connect_success', {
                    'event_category': 'onboarding',
                    'event_label': 'step2_mercadopago'
                });
            }
        }, 500);
    }

    // ========================================
    // INITIALIZATION
    // ========================================
    function init() {
        initFAQToggle();
        initConnectButton();
        initReconnectButton();
        handleOAuthErrors();
        handleOAuthSuccess();
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
