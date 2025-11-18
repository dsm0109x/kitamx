/**
 * AUTH PASSWORD RESET - ENHANCED VERSION
 * Validación en tiempo real + AJAX + Loading states
 *
 * Features:
 * - ✅ Validación client-side en tiempo real
 * - ✅ AJAX form submission
 * - ✅ Multi-stage loading
 * - ✅ Manejo de errores con toast
 * - ✅ Turnstile integration
 * - ✅ Analytics tracking
 *
 * @version 2.0 - Enhanced
 * @created 2025-10-20
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
            console.log('✅ Turnstile validation successful (password reset)');
        }
    };

    window.onTurnstileError = function(error) {
        console.error('❌ Turnstile error:', error);
        if (typeof showToast !== 'undefined') {
            showToast('Error en la verificación de seguridad. Intenta de nuevo.', 'error');
        }
    };

    // ========================================
    // 2. VALIDATION HELPERS
    // ========================================

    const ValidationHelpers = {
        /**
         * Validar email
         */
        validateEmail(email) {
            if (!email || email.trim() === '') {
                return { valid: false, message: 'El correo electrónico es requerido' };
            }

            const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!regex.test(email)) {
                return { valid: false, message: 'Ingresa un correo electrónico válido' };
            }

            return { valid: true, message: '' };
        },

        /**
         * Validar Turnstile token
         */
        validateTurnstile(token) {
            if (!token || token.trim() === '') {
                return { valid: false, message: 'Por favor completa la verificación de seguridad' };
            }

            return { valid: true, message: '' };
        }
    };

    // ========================================
    // 3. UI HELPERS
    // ========================================

    const UIHelpers = {
        /**
         * Mostrar error en campo
         */
        setFieldError(input, message) {
            if (!input) return;

            input.classList.add('is-invalid');
            input.classList.remove('is-valid');

            // Crear o actualizar mensaje de error
            let errorDiv = input.parentElement.querySelector('.form-error');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.className = 'form-error';
                errorDiv.setAttribute('role', 'alert');
                input.parentElement.appendChild(errorDiv);
            }

            errorDiv.innerHTML = `<small>${message}</small>`;
        },

        /**
         * Mostrar campo válido
         */
        setFieldValid(input) {
            if (!input) return;

            input.classList.add('is-valid');
            input.classList.remove('is-invalid');

            // Remover mensaje de error
            const errorDiv = input.parentElement.querySelector('.form-error');
            if (errorDiv) {
                errorDiv.remove();
            }
        },

        /**
         * Limpiar validación de campo
         */
        clearFieldValidation(input) {
            if (!input) return;

            input.classList.remove('is-valid', 'is-invalid');

            const errorDiv = input.parentElement.querySelector('.form-error');
            if (errorDiv) {
                errorDiv.remove();
            }
        }
    };

    // ========================================
    // 4. REAL-TIME VALIDATION
    // ========================================

    function initRealtimeValidation() {
        const form = document.querySelector('.auth-form');
        if (!form) return;

        // Email validation
        const emailInput = form.querySelector('input[name="email"]');
        if (emailInput) {
            emailInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validateEmail(this.value);
                if (!result.valid) {
                    UIHelpers.setFieldError(this, result.message);
                } else {
                    UIHelpers.setFieldValid(this);
                }
            });

            // Limpiar error mientras escribe
            emailInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) {
                    UIHelpers.clearFieldValidation(this);
                }
            });
        }

        console.log('✅ Real-time validation initialized');
    }

    // ========================================
    // 5. FORM VALIDATION (antes de submit)
    // ========================================

    function validateForm(form) {
        let isValid = true;

        // Validar email
        const emailInput = form.querySelector('input[name="email"]');
        if (emailInput) {
            const result = ValidationHelpers.validateEmail(emailInput.value);
            if (!result.valid) {
                UIHelpers.setFieldError(emailInput, result.message);
                isValid = false;
            } else {
                UIHelpers.setFieldValid(emailInput);
            }
        }

        // Validar Turnstile
        const turnstileInput = form.querySelector('input[name="cf_turnstile_response"]');
        if (turnstileInput) {
            const result = ValidationHelpers.validateTurnstile(turnstileInput.value);
            if (!result.valid) {
                showToast(result.message, 'error');
                isValid = false;
            }
        }

        return isValid;
    }

    // ========================================
    // 6. AJAX FORM SUBMISSION
    // ========================================

    function initAjaxSubmit() {
        const form = document.querySelector('.auth-form');
        const submitBtn = document.getElementById('resetSubmit');

        if (!form || !submitBtn) {
            console.warn('⚠️ Form or submit button not found');
            return;
        }

        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Validar formulario
            if (!validateForm(form)) {
                return;
            }

            // Loading states with progress
            submitBtn.classList.add('is-loading');
            submitBtn.disabled = true;

            // Multi-stage loading
            if (typeof loading !== 'undefined' && loading.start) {
                loading.start([
                    'Validando email...',
                    'Generando enlace seguro...',
                    'Enviando correo...'
                ]);
            } else if (typeof showLoading !== 'undefined') {
                showLoading('Enviando enlace de recuperación...');
            }

            const formData = new FormData(form);

            try {
                // Stage 1 → 2
                if (typeof loading !== 'undefined' && loading.next) {
                    loading.next();
                }

                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                // Stage 2 → 3
                if (typeof loading !== 'undefined' && loading.next) {
                    loading.next();
                }

                // Parse response
                let data;
                try {
                    const text = await response.text();
                    let parsed = JSON.parse(text);

                    // Fix para debug toolbar wrapper
                    if (parsed.html && typeof parsed.html === 'string') {
                        data = JSON.parse(parsed.html);
                    } else {
                        data = parsed;
                    }
                } catch (parseError) {
                    console.error('❌ JSON parse error:', parseError);
                    throw new Error('Server returned invalid JSON');
                }

                if (response.ok && data.success) {
                    // ✅ Success
                    if (typeof loading !== 'undefined' && loading.done) {
                        loading.done();
                    } else if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    showToast('✅ Revisa tu email. Te enviamos el enlace de recuperación.', 'success');

                    // Analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'password_reset_success', {
                            'event_category': 'authentication',
                            'event_label': 'ajax-password-reset',
                            'value': 1
                        });
                    }

                    // Redirect a página de confirmación
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/accounts/password/reset/done/';
                    }, 2000);

                } else {
                    // ❌ Error
                    if (typeof loading !== 'undefined' && loading.cancel) {
                        loading.cancel();
                    } else if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    submitBtn.classList.remove('is-loading');
                    submitBtn.disabled = false;

                    // ✅ RESETEAR TURNSTILE después de error (token de un solo uso)
                    if (typeof turnstile !== 'undefined') {
                        try {
                            const turnstileWidget = document.querySelector('.cf-turnstile');
                            if (turnstileWidget) {
                                turnstile.reset(turnstileWidget);
                                console.log('🔄 Turnstile reseteado después de error');
                            }
                        } catch (e) {
                            console.warn('No se pudo resetear Turnstile:', e);
                        }
                    }

                    // Mostrar errores por campo
                    if (data.errors) {
                        for (const [field, errors] of Object.entries(data.errors)) {
                            const input = form.querySelector(`[name="${field}"]`);
                            if (input && errors.length > 0) {
                                UIHelpers.setFieldError(input, errors[0]);
                            }
                        }
                    }

                    // Error global
                    if (data.error) {
                        showToast(data.error, 'error');
                    } else {
                        showToast('Por favor corrige los errores del formulario', 'error');
                    }

                    // Analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'password_reset_validation_error', {
                            'event_category': 'authentication',
                            'event_label': 'ajax-password-reset',
                            'value': 0
                        });
                    }
                }

            } catch (error) {
                console.error('❌ Password reset error:', error);

                // Use Error Recovery System si está disponible
                if (typeof window.ErrorRecovery !== 'undefined') {
                    window.ErrorRecovery.handleError(error, {
                        url: form.action,
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        onSuccess: (data) => {
                            if (data.success) {
                                showToast('✅ Revisa tu email. Te enviamos el enlace.', 'success');
                                setTimeout(() => {
                                    window.location.href = data.redirect_url || '/accounts/password/reset/done/';
                                }, 2000);
                            }
                        },
                        onError: () => {
                            submitBtn.classList.remove('is-loading');
                            submitBtn.disabled = false;
                        }
                    }, {
                        context: 'password_reset',
                        autoRetry: true
                    });
                } else {
                    // BUG FIX #82: Fallback - usar mensaje del error si está disponible
                    if (typeof hideLoading !== 'undefined') hideLoading();
                    const errorMsg = error.message || 'Error de conexión. Por favor intenta de nuevo.';
                    showToast(errorMsg, 'error');
                }

                submitBtn.classList.remove('is-loading');
                submitBtn.disabled = false;

                // Analytics
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'password_reset_network_error', {
                        'event_category': 'authentication',
                        'event_label': 'ajax-password-reset',
                        'value': 0
                    });
                }
            }
        });

        console.log('✅ AJAX form submission initialized');
    }

    // ========================================
    // 7. INIT ON DOM READY
    // ========================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initRealtimeValidation();
            initAjaxSubmit();
            console.log('✅ Auth Password Reset Enhanced initialized');
        } catch (error) {
            console.error('❌ Auth Password Reset Enhanced initialization error:', error);
        }
    }

    // Auto-initialize
    init();

})();
