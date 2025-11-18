/**
 * AUTH LOGIN - Event Delegation & Loading State
 * Consolidated JavaScript for login page
 *
 * Features:
 * - Turnstile integration (Normal Mode)
 * - Password toggle functionality
 * - Loading state on submit (matches home implementation)
 * - Analytics tracking
 * - CSP-compliant (no inline handlers)
 *
 * @version 1.0
 */

'use strict';

(function() {
    // ========================================
    // 1. TURNSTILE CALLBACKS
    // ========================================

    window.onTurnstileSuccess = function(token) {
        const hiddenField = document.querySelector('input[name="cf_turnstile_response"]');
        if (hiddenField) {
            hiddenField.value = token;
            console.log('✅ Turnstile validation successful (normal mode)');
        }
    };

    window.onTurnstileError = function(error) {
        console.error('❌ Turnstile error:', error);
        if (typeof showToast !== 'undefined') {
            showToast('Error en la verificación de seguridad. Intenta de nuevo.', 'error');
        }
    };

    // ========================================
    // 2. PASSWORD TOGGLE (Event Delegation)
    // ========================================

    document.addEventListener('click', function(e) {
        const toggle = e.target.closest('.password-toggle');
        if (!toggle) return;

        const targetId = toggle.dataset.target;
        const input = document.getElementById(targetId);
        const icon = toggle.querySelector('.toggle-icon');

        if (input && icon) {
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('iconoir-eye');
                icon.classList.add('iconoir-eye-closed');
                toggle.setAttribute('aria-label', 'Ocultar contraseña');
            } else {
                input.type = 'password';
                icon.classList.remove('iconoir-eye-closed');
                icon.classList.add('iconoir-eye');
                toggle.setAttribute('aria-label', 'Mostrar contraseña');
            }
        }
    });

    // ========================================
    // 3. LOADING STATE ON SUBMIT (Matches Home Implementation)
    // ========================================

    function initLoadingState() {
        const form = document.querySelector('.auth-form');
        const submitBtn = document.getElementById('loginSubmit');

        if (!form || !submitBtn) {
            console.warn('⚠️ Form or submit button not found');
            return;
        }

        form.addEventListener('submit', function(e) {
            // Aplicar loading state al botón
            const btnText = submitBtn.querySelector('.btn-text');
            let originalContent;

            if (btnText) {
                originalContent = btnText.innerHTML;
                btnText.textContent = 'Cargando';
            }

            submitBtn.classList.add('is-loading');
            submitBtn.disabled = true;

            // Analytics tracking
            if (typeof gtag !== 'undefined') {
                gtag('event', 'login_submit', {
                    'event_category': 'authentication',
                    'event_label': 'login-form',
                    'value': 1
                });
            }

            console.log('🔄 Loading state applied to login button');

            // Reset después de 5s por si la navegación falla
            // (En navegación exitosa, la página se recarga antes)
            setTimeout(() => {
                submitBtn.classList.remove('is-loading');
                submitBtn.disabled = false;
                if (btnText && originalContent) {
                    btnText.innerHTML = originalContent;
                }
            }, 5000);
        });

        console.log('✅ Loading state initialized');
    }

    // ========================================
    // 4. GOOGLE OAUTH LOADING STATE
    // ========================================

    function initGoogleOAuthLoading() {
        const googleBtn = document.querySelector('[href*="/accounts/google/login/"]');
        if (!googleBtn) return;

        googleBtn.addEventListener('click', function(e) {
            const btnText = this.querySelector('span:last-child');
            if (btnText) {
                btnText.textContent = 'Cargando';
            }
            this.classList.add('is-loading');

            // Analytics
            if (typeof gtag !== 'undefined') {
                gtag('event', 'login_google_oauth', {
                    'event_category': 'authentication',
                    'event_label': 'google-oauth',
                    'value': 1
                });
            }

            console.log('🔄 Google OAuth loading state applied');
        });

        console.log('✅ Google OAuth loading initialized');
    }

    // ========================================
    // 5. INIT ON DOM READY
    // ========================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initLoadingState();
            initGoogleOAuthLoading();
            console.log('✅ Auth Login initialized');
        } catch (error) {
            console.error('❌ Auth Login initialization error:', error);
        }
    }

    // Auto-initialize
    init();

})();
