/**
 * AUTH LOGIN - ENHANCED VERSION
 * Validación en tiempo real + AJAX submit + Manejo de errores con toast
 *
 * Features:
 * - ✅ Validación client-side en tiempo real
 * - ✅ AJAX form submission
 * - ✅ Manejo de errores con toast system
 * - ✅ Loading states (botón + global)
 * - ✅ Password toggle
 * - ✅ Turnstile integration
 * - ✅ Analytics tracking
 *
 * @version 2.0 - Enhanced
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
            console.log('✅ Turnstile validation successful');
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
         * Validar password
         */
        validatePassword(password) {
            if (!password || password.trim() === '') {
                return { valid: false, message: 'La contraseña es requerida' };
            }

            if (password.length < 8) {
                return { valid: false, message: 'La contraseña debe tener al menos 8 caracteres' };
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
        },

        /**
         * Mostrar loading en campo (durante AJAX)
         */
        setFieldValidating(input) {
            if (!input) return;

            input.classList.add('is-validating');
            input.classList.remove('is-valid', 'is-invalid');
        },

        /**
         * Limpiar loading de campo
         */
        clearFieldValidating(input) {
            if (!input) return;
            input.classList.remove('is-validating');
        }
    };

    // ========================================
    // 4. PASSWORD TOGGLE
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
    // 5. RATE LIMITING TRACKER
    // ========================================

    const RateLimitTracker = {
        storageKey: 'kita_login_attempts',
        maxAttempts: 5,
        windowMinutes: 5,

        getAttempts() {
            try {
                const data = localStorage.getItem(this.storageKey);
                if (!data) return [];

                const attempts = JSON.parse(data);
                const cutoff = Date.now() - (this.windowMinutes * 60 * 1000);

                // Filtrar solo intentos recientes (últimos 5 minutos)
                return attempts.filter(timestamp => timestamp > cutoff);
            } catch (e) {
                return [];
            }
        },

        addAttempt() {
            try {
                const attempts = this.getAttempts();
                attempts.push(Date.now());
                localStorage.setItem(this.storageKey, JSON.stringify(attempts));
                return attempts.length;
            } catch (e) {
                return 0;
            }
        },

        getRemainingAttempts() {
            const attempts = this.getAttempts();
            return Math.max(0, this.maxAttempts - attempts.length);
        },

        isLocked() {
            return this.getRemainingAttempts() === 0;
        },

        clear() {
            try {
                localStorage.removeItem(this.storageKey);
            } catch (e) {
                // Silent fail
            }
        },

        showWarning() {
            const remaining = this.getRemainingAttempts();

            if (remaining <= 2 && remaining > 0) {
                // Mostrar advertencia cuando quedan 2 o menos intentos
                const warningEl = document.createElement('div');
                warningEl.className = 'alert alert-warning mt-3';
                warningEl.setAttribute('role', 'alert');
                warningEl.style.cssText = `
                    border-left: 3px solid #f59e0b;
                    animation: shake 0.3s ease;
                `;
                warningEl.innerHTML = `
                    <strong>⚠️ Advertencia:</strong>
                    Te quedan <strong>${remaining} intento${remaining > 1 ? 's' : ''}</strong> antes de bloquearte temporalmente.
                `;

                const form = document.querySelector('.auth-form');
                if (form) {
                    // Remover warning anterior si existe
                    const existingWarning = form.querySelector('.alert-warning');
                    if (existingWarning) existingWarning.remove();

                    // Insertar nuevo warning
                    form.appendChild(warningEl);

                    // Auto-scroll
                    warningEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            } else if (remaining === 0) {
                // Mostrar mensaje de bloqueo
                showToast('Demasiados intentos fallidos. Espera 5 minutos.', 'error');
            }
        }
    };

    // ========================================
    // 6. REAL-TIME VALIDATION
    // ========================================

    function initRealtimeValidation() {
        const form = document.querySelector('.auth-form');
        if (!form) return;

        // Email validation
        const emailInput = form.querySelector('input[name="login"]');
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

        // Password validation
        const passwordInput = form.querySelector('input[name="password"]');
        if (passwordInput) {
            passwordInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validatePassword(this.value);
                if (!result.valid) {
                    UIHelpers.setFieldError(this, result.message);
                } else {
                    UIHelpers.setFieldValid(this);
                }
            });

            // Limpiar error mientras escribe
            passwordInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) {
                    UIHelpers.clearFieldValidation(this);
                }
            });
        }

        console.log('✅ Real-time validation initialized');
    }

    // ========================================
    // 6. FORM VALIDATION (antes de submit)
    // ========================================

    function validateForm(form) {
        let isValid = true;

        // Validar email
        const emailInput = form.querySelector('input[name="login"]');
        if (emailInput) {
            const result = ValidationHelpers.validateEmail(emailInput.value);
            if (!result.valid) {
                UIHelpers.setFieldError(emailInput, result.message);
                isValid = false;
            } else {
                UIHelpers.setFieldValid(emailInput);
            }
        }

        // Validar password
        const passwordInput = form.querySelector('input[name="password"]');
        if (passwordInput) {
            const result = ValidationHelpers.validatePassword(passwordInput.value);
            if (!result.valid) {
                UIHelpers.setFieldError(passwordInput, result.message);
                isValid = false;
            } else {
                UIHelpers.setFieldValid(passwordInput);
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
    // 7. AJAX FORM SUBMISSION
    // ========================================

    function initAjaxSubmit() {
        const form = document.querySelector('.auth-form');
        const submitBtn = document.getElementById('loginSubmit');

        if (!form || !submitBtn) {
            console.warn('⚠️ Form or submit button not found');
            return;
        }

        form.addEventListener('submit', async function(e) {
            e.preventDefault(); // ✅ Prevenir submit tradicional

            // Validar formulario
            if (!validateForm(form)) {
                return;
            }

            // Loading states with progress
            submitBtn.classList.add('is-loading');
            submitBtn.disabled = true;

            // Multi-stage loading
            loading.start([
                'Validando datos...',
                'Verificando credenciales...',
                'Iniciando sesión...'
            ]);

            // Preparar datos
            const formData = new FormData(form);

            try {
                // Stage 1 → 2
                loading.next();

                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                // Stage 2 → 3
                loading.next();

                console.log('📦 Response status:', response.status);
                console.log('📦 Response OK:', response.ok);
                console.log('📦 Response content-type:', response.headers.get('content-type'));

                // Intentar parsear JSON con manejo de errores
                let data;
                try {
                    const text = await response.text();
                    console.log('📦 Response text (first 500 chars):', text.substring(0, 500));

                    let parsed = JSON.parse(text);
                    console.log('📦 First parse:', parsed);

                    // 🐛 FIX: Si el JSON viene en data.html (debug toolbar wrapper)
                    if (parsed.html && typeof parsed.html === 'string') {
                        console.log('⚠️ JSON wrapped in html field, parsing again...');
                        data = JSON.parse(parsed.html);
                        console.log('📦 Actual data after double parse:', data);
                    } else {
                        data = parsed;
                    }

                    console.log('📦 Final data.error exists:', !!data.error);
                    console.log('📦 Final data.error value:', data.error);
                } catch (parseError) {
                    console.error('❌ JSON parse error:', parseError);
                    console.log('📦 Response was not valid JSON');
                    throw new Error('Server returned invalid JSON');
                }

                if (response.ok && data.success) {
                    // ✅ Success
                    // Limpiar rate limit counter
                    RateLimitTracker.clear();

                    loading.done();
                    showToast('¡Sesión iniciada exitosamente!', 'success');

                    // Analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'login_success', {
                            'event_category': 'authentication',
                            'event_label': 'ajax-login',
                            'value': 1
                        });
                    }

                    // Esperar animación de toast antes de redirigir
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/panel/';
                    }, 1000);

                } else {
                    // ❌ Error de validación
                    loading.cancel();
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

                    // ✅ Registrar intento fallido si es error de credenciales
                    if (data.error_type === 'invalid_credentials') {
                        const attemptCount = RateLimitTracker.addAttempt();
                        console.log(`⚠️ Failed login attempt ${attemptCount}/${RateLimitTracker.maxAttempts}`);

                        // Mostrar warning si quedan pocos intentos
                        RateLimitTracker.showWarning();
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

                    // Error global con toast mejorado
                    if (data.error) {
                        showToast(data.error, 'error');

                        // Si hay link de ayuda (ej: recuperar contraseña), mostrarlo
                        if (data.help_link && data.error_type === 'invalid_credentials') {
                            // Crear mensaje con link después de un delay
                            setTimeout(() => {
                                const helpMessage = document.createElement('div');
                                helpMessage.className = 'auth-helper-link';
                                helpMessage.style.cssText = `
                                    text-align: center;
                                    margin-top: 1rem;
                                    padding: 1rem;
                                    background: #f0f9ff;
                                    border-left: 3px solid #0284c7;
                                    border-radius: 8px;
                                    animation: fade-in 0.3s ease;
                                `;
                                helpMessage.innerHTML = `
                                    <p style="margin: 0; color: #4b5563; font-size: 0.9rem;">
                                        💡 <strong>¿Olvidaste tu contraseña?</strong><br>
                                        <a href="${data.help_link}"
                                           style="color: #0284c7; text-decoration: underline; font-weight: 600;">
                                            Recupérala aquí en menos de 1 minuto
                                        </a>
                                    </p>
                                `;

                                // Insertar después del formulario
                                const existingHelper = form.parentElement.querySelector('.auth-helper-link');
                                if (existingHelper) {
                                    existingHelper.remove();
                                }
                                form.parentElement.insertBefore(helpMessage, form.nextSibling);
                            }, 500);
                        }
                    } else {
                        showToast('Por favor corrige los errores del formulario', 'error');
                    }

                    // Analytics con tipo de error
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'login_validation_error', {
                            'event_category': 'authentication',
                            'event_label': data.error_type || 'unknown',
                            'value': 0
                        });
                    }
                }

            } catch (error) {
                console.error('❌ Login error:', error);

                // Use Error Recovery System
                const recovery = window.ErrorRecovery.handleError(error, {
                    url: form.action,
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    onSuccess: (data) => {
                        if (data.success) {
                            showToast('¡Sesión iniciada exitosamente!', 'success');
                            setTimeout(() => {
                                window.location.href = data.redirect_url || '/panel/';
                            }, 1000);
                        }
                    },
                    onError: () => {
                        submitBtn.classList.remove('is-loading');
                        submitBtn.disabled = false;
                    }
                }, {
                    context: 'login',
                    autoRetry: true
                });

                submitBtn.classList.remove('is-loading');
                submitBtn.disabled = false;

                // Analytics
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'login_network_error', {
                        'event_category': 'authentication',
                        'event_label': 'ajax-login',
                        'value': 0
                    });
                }
            }
        });

        console.log('✅ AJAX form submission initialized');
    }

    // ========================================
    // 8. GOOGLE OAUTH LOADING STATE
    // ========================================

    function initGoogleOAuthLoading() {
        const googleBtn = document.querySelector('[href*="/accounts/google/login/"]');
        if (!googleBtn) return;

        googleBtn.addEventListener('click', function(e) {
            const btnText = this.querySelector('span:last-child');
            if (btnText) {
                btnText.textContent = 'Cargando...';
            }
            this.classList.add('is-loading');
            showLoading('Conectando con Google...');

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
    // 9. INIT ON DOM READY
    // ========================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initRealtimeValidation();
            initAjaxSubmit();
            initGoogleOAuthLoading();
            console.log('✅ Auth Login Enhanced initialized');
        } catch (error) {
            console.error('❌ Auth Login Enhanced initialization error:', error);
        }
    }

    // Auto-initialize
    init();

})();
