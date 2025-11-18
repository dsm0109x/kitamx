/**
 * AUTH SIGNUP - ENHANCED VERSION
 * Validación en tiempo real + AJAX + Password strength + Auto-save
 *
 * Features:
 * - ✅ Validación progresiva (campo por campo)
 * - ✅ Password strength meter visual
 * - ✅ AJAX form submission
 * - ✅ Auto-save form data (LocalStorage)
 * - ✅ Manejo de errores con toast
 * - ✅ Loading states
 * - ✅ Turnstile integration
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
            showToast('Error en la verificación anti-bot. Por favor, recarga la página.', 'error');
        }
    };

    // ========================================
    // 2. VALIDATION HELPERS
    // ========================================

    const ValidationHelpers = {
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

        validateName(name, fieldLabel) {
            if (!name || name.trim() === '') {
                return { valid: false, message: `${fieldLabel} es requerido` };
            }

            if (name.length < 2) {
                return { valid: false, message: `${fieldLabel} debe tener al menos 2 caracteres` };
            }

            return { valid: true, message: '' };
        },

        validatePhone(phone) {
            // Phone es opcional
            if (!phone || phone.trim() === '') {
                return { valid: true, message: '' };
            }

            // Validación básica (10 dígitos para México)
            const cleaned = phone.replace(/\D/g, '');
            if (cleaned.length !== 10) {
                return { valid: false, message: 'El teléfono debe tener 10 dígitos' };
            }

            return { valid: true, message: '' };
        },

        validatePassword(password) {
            if (!password || password.trim() === '') {
                return { valid: false, message: 'La contraseña es requerida' };
            }

            if (password.length < 8) {
                return { valid: false, message: 'Mínimo 8 caracteres' };
            }

            const hasUpper = /[A-Z]/.test(password);
            const hasLower = /[a-z]/.test(password);
            const hasNumber = /\d/.test(password);

            if (!hasUpper || !hasLower || !hasNumber) {
                return { valid: false, message: 'Debe contener mayúsculas, minúsculas y números' };
            }

            return { valid: true, message: '' };
        },

        validatePasswordMatch(password1, password2) {
            if (!password2 || password2.trim() === '') {
                return { valid: false, message: 'Confirma tu contraseña' };
            }

            if (password1 !== password2) {
                return { valid: false, message: 'Las contraseñas no coinciden' };
            }

            return { valid: true, message: '' };
        },

        validateCheckbox(checked, message) {
            if (!checked) {
                return { valid: false, message };
            }
            return { valid: true, message: '' };
        },

        validateTurnstile(token) {
            if (!token || token.trim() === '') {
                return { valid: false, message: 'Por favor completa la verificación de seguridad' };
            }
            return { valid: true, message: '' };
        }
    };

    // ========================================
    // 3. PASSWORD STRENGTH CHECKER
    // ========================================

    const PasswordStrength = {
        check(password) {
            let strength = 0;
            const checks = {
                length: password.length >= 8,
                lowercase: /[a-z]/.test(password),
                uppercase: /[A-Z]/.test(password),
                number: /\d/.test(password),
                special: /[^a-zA-Z0-9]/.test(password)
            };

            strength = Object.values(checks).filter(Boolean).length;

            const levels = [
                { max: 0, label: 'Ingresa una contraseña', color: '#9ca3af', width: '0%', class: 'none' },
                { max: 2, label: 'Muy débil', color: '#dc2626', width: '20%', class: 'weak' },
                { max: 3, label: 'Débil', color: '#f59e0b', width: '40%', class: 'fair' },
                { max: 4, label: 'Media', color: '#fbbf24', width: '60%', class: 'good' },
                { max: 5, label: 'Fuerte', color: '#15803d', width: '100%', class: 'strong' }
            ];

            const level = levels.find(l => strength <= l.max) || levels[levels.length - 1];

            return {
                strength,
                ...level,
                checks
            };
        },

        render(password, container) {
            if (!container) return;

            const result = this.check(password);

            container.innerHTML = `
                <div class="password-strength-meter">
                    <div class="strength-bar">
                        <div class="strength-fill strength-${result.class}"
                             style="width: ${result.width}; background-color: ${result.color};">
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-2">
                        <span class="strength-text" style="color: ${result.color}; font-size: 0.85rem; font-weight: 600;">
                            ${result.label}
                        </span>
                        ${result.strength > 0 ? `
                        <div class="strength-requirements" style="font-size: 0.75rem; color: #6b7280;">
                            ${result.checks.length ? '✓' : '○'} 8+ caracteres
                            ${result.checks.uppercase && result.checks.lowercase ? '✓' : '○'} Mayús/Minús
                            ${result.checks.number ? '✓' : '○'} Números
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
    };

    // ========================================
    // 4. UI HELPERS
    // ========================================

    const UIHelpers = {
        setFieldError(input, message) {
            if (!input) return;

            input.classList.add('is-invalid');
            input.classList.remove('is-valid');

            let errorDiv = input.parentElement.querySelector('.form-error');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.className = 'form-error';
                errorDiv.setAttribute('role', 'alert');
                input.parentElement.appendChild(errorDiv);
            }

            errorDiv.innerHTML = `<small>${message}</small>`;
        },

        setFieldValid(input) {
            if (!input) return;

            input.classList.add('is-valid');
            input.classList.remove('is-invalid');

            const errorDiv = input.parentElement.querySelector('.form-error');
            if (errorDiv) {
                errorDiv.remove();
            }
        },

        clearFieldValidation(input) {
            if (!input) return;
            input.classList.remove('is-valid', 'is-invalid');

            const errorDiv = input.parentElement.querySelector('.form-error');
            if (errorDiv) {
                errorDiv.remove();
            }
        },

        setFieldValidating(input) {
            if (!input) return;
            input.classList.add('is-validating');
            input.classList.remove('is-valid', 'is-invalid');
        },

        clearFieldValidating(input) {
            if (!input) return;
            input.classList.remove('is-validating');
        }
    };

    // ========================================
    // 5. AUTO-SAVE FORM DATA
    // ========================================

    const AutoSave = {
        prefix: 'kita_signup_',

        save(name, value) {
            try {
                localStorage.setItem(this.prefix + name, value);
            } catch (e) {
                console.warn('LocalStorage not available:', e);
            }
        },

        restore(name) {
            try {
                return localStorage.getItem(this.prefix + name) || '';
            } catch (e) {
                console.warn('LocalStorage not available:', e);
                return '';
            }
        },

        clear() {
            try {
                const keys = Object.keys(localStorage);
                keys.filter(k => k.startsWith(this.prefix)).forEach(k => {
                    localStorage.removeItem(k);
                });
            } catch (e) {
                console.warn('LocalStorage not available:', e);
            }
        },

        init(form) {
            if (!form) return;

            // Campos a guardar (excluir passwords y checkboxes)
            const inputs = form.querySelectorAll('input:not([type="password"]):not([type="checkbox"]):not([type="hidden"])');

            inputs.forEach(input => {
                // Restaurar valores guardados
                const saved = this.restore(input.name);
                if (saved && !input.value) {
                    input.value = saved;
                }

                // Guardar mientras escribe (debounced)
                input.addEventListener('input', this.debounce(() => {
                    this.save(input.name, input.value);
                }, 500));
            });

            console.log('✅ Auto-save initialized');
        },

        debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    };

    // ========================================
    // 6. UTILS
    // ========================================

    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) return csrfInput.value;
        const csrfCookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return csrfCookie ? csrfCookie.split('=')[1] : '';
    }

    // ========================================
    // 7. PASSWORD TOGGLE
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
    // 8. REAL-TIME VALIDATION
    // ========================================

    function initRealtimeValidation() {
        const form = document.querySelector('.auth-form');
        if (!form) return;

        // First name
        const firstNameInput = form.querySelector('input[name="first_name"]');
        if (firstNameInput) {
            firstNameInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validateName(this.value, 'El nombre');
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
            firstNameInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        // Last name
        const lastNameInput = form.querySelector('input[name="last_name"]');
        if (lastNameInput) {
            lastNameInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validateName(this.value, 'Los apellidos');
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
            lastNameInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        // Email con AJAX availability check
        const emailInput = form.querySelector('input[name="email"]');
        let emailCheckTimeout;

        if (emailInput) {
            emailInput.addEventListener('blur', async function() {
                const email = this.value.trim();

                // 1. Validación de formato primero
                const formatResult = ValidationHelpers.validateEmail(email);
                if (!formatResult.valid) {
                    UIHelpers.setFieldError(this, formatResult.message);
                    return;
                }

                // 2. AJAX check de disponibilidad
                UIHelpers.setFieldValidating(this);

                clearTimeout(emailCheckTimeout);
                emailCheckTimeout = setTimeout(async () => {
                    try {
                        const response = await fetch('/cuenta/verificar-email/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCsrfToken()
                            },
                            body: JSON.stringify({ email })
                        });

                        const data = await response.json();

                        UIHelpers.clearFieldValidating(this);

                        if (data.available) {
                            UIHelpers.setFieldValid(this);
                        } else {
                            UIHelpers.setFieldError(this, data.message || 'Este email ya está registrado');
                        }

                    } catch (error) {
                        console.error('Email check error:', error);
                        // Silent fail - no bloquear signup si falla check
                        UIHelpers.clearFieldValidating(this);
                        UIHelpers.setFieldValid(this);
                    }
                }, 800);
            });

            emailInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) {
                    UIHelpers.clearFieldValidation(this);
                }
            });
        }

        // Phone (opcional) con auto-format
        const phoneInput = form.querySelector('input[name="phone"]');
        if (phoneInput) {
            phoneInput.addEventListener('input', function() {
                // Limpiar validación si estaba inválido
                if (this.classList.contains('is-invalid')) {
                    UIHelpers.clearFieldValidation(this);
                }

                // ✅ Auto-format: (55) 1234-5678
                let value = this.value.replace(/\D/g, ''); // Solo números

                if (value.length > 10) {
                    value = value.substring(0, 10); // Max 10 dígitos
                }

                let formatted = '';
                if (value.length > 0) {
                    formatted = '(' + value.substring(0, 2);
                    if (value.length >= 2) {
                        formatted += ') ' + value.substring(2, 6);
                    }
                    if (value.length >= 6) {
                        formatted += '-' + value.substring(6, 10);
                    }
                }

                this.value = formatted;
            });

            phoneInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validatePhone(this.value);
                if (!result.valid) {
                    UIHelpers.setFieldError(this, result.message);
                } else if (this.value.trim()) {
                    UIHelpers.setFieldValid(this);
                } else {
                    UIHelpers.clearFieldValidation(this);
                }
            });
        }

        // Password 1 con strength meter
        const password1Input = form.querySelector('input[name="password1"]');
        const strengthContainer = document.createElement('div');
        if (password1Input) {
            // Insertar strength meter después del wrapper
            const wrapper = password1Input.closest('.password-wrapper') || password1Input.parentElement;
            wrapper.parentElement.insertBefore(strengthContainer, wrapper.nextSibling);

            password1Input.addEventListener('input', function() {
                PasswordStrength.render(this.value, strengthContainer);
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });

            password1Input.addEventListener('blur', function() {
                const result = ValidationHelpers.validatePassword(this.value);
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
        }

        // Password 2 (confirmación)
        const password2Input = form.querySelector('input[name="password2"]');
        if (password2Input && password1Input) {
            password2Input.addEventListener('blur', function() {
                const result = ValidationHelpers.validatePasswordMatch(password1Input.value, this.value);
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
            password2Input.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        console.log('✅ Real-time validation initialized');
    }

    // ========================================
    // 9. FORM VALIDATION (antes de submit)
    // ========================================

    function validateForm(form) {
        let isValid = true;

        // Validar todos los campos
        const validations = [
            { name: 'first_name', validator: (v) => ValidationHelpers.validateName(v, 'El nombre') },
            { name: 'last_name', validator: (v) => ValidationHelpers.validateName(v, 'Los apellidos') },
            { name: 'email', validator: ValidationHelpers.validateEmail },
            { name: 'phone', validator: ValidationHelpers.validatePhone },
            { name: 'password1', validator: ValidationHelpers.validatePassword }
        ];

        validations.forEach(({ name, validator }) => {
            const input = form.querySelector(`input[name="${name}"]`);
            if (input) {
                const result = validator(input.value);
                if (!result.valid) {
                    UIHelpers.setFieldError(input, result.message);
                    isValid = false;
                } else {
                    UIHelpers.setFieldValid(input);
                }
            }
        });

        // Validar password match
        const password1 = form.querySelector('input[name="password1"]');
        const password2 = form.querySelector('input[name="password2"]');
        if (password1 && password2) {
            const result = ValidationHelpers.validatePasswordMatch(password1.value, password2.value);
            if (!result.valid) {
                UIHelpers.setFieldError(password2, result.message);
                isValid = false;
            } else {
                UIHelpers.setFieldValid(password2);
            }
        }

        // Validar checkboxes
        const termsCheckbox = form.querySelector('input[name="terms_accepted"]');
        if (termsCheckbox && !termsCheckbox.checked) {
            showToast('Debes aceptar los términos y condiciones', 'error');
            isValid = false;
        }

        const privacyCheckbox = form.querySelector('input[name="privacy_accepted"]');
        if (privacyCheckbox && !privacyCheckbox.checked) {
            showToast('Debes aceptar el aviso de privacidad', 'error');
            isValid = false;
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
    // 10. AJAX FORM SUBMISSION
    // ========================================

    function initAjaxSubmit() {
        const form = document.querySelector('.auth-form');
        const submitBtn = document.getElementById('signupSubmit');

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
            loading.start([
                'Validando información...',
                'Creando tu cuenta...',
                'Configurando perfil...'
            ]);

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

                // Parsear response con fix para debug toolbar wrapper
                let data;
                const text = await response.text();
                let parsed = JSON.parse(text);

                // 🐛 FIX: Si el JSON viene en data.html (debug toolbar wrapper)
                if (parsed.html && typeof parsed.html === 'string') {
                    data = JSON.parse(parsed.html);
                } else {
                    data = parsed;
                }

                if (response.ok && data.success) {
                    // ✅ Success - Limpiar auto-save
                    AutoSave.clear();
                    loading.done();
                    showToast('¡Cuenta creada exitosamente! Redirigiendo...', 'success');

                    // Analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'signup_success', {
                            'event_category': 'authentication',
                            'event_label': 'ajax-signup',
                            'value': 1
                        });
                    }

                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/incorporacion/';
                    }, 1500);

                } else {
                    // ❌ Error
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

                    // Errores por campo
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
                    } else if (data.errors && data.errors.__all__) {
                        // ✅ Mostrar error genérico del backend
                        showToast(data.errors.__all__[0], 'error');
                    } else {
                        showToast('Por favor corrige los errores del formulario', 'error');
                    }

                    // Analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'signup_validation_error', {
                            'event_category': 'authentication',
                            'event_label': 'ajax-signup',
                            'value': 0
                        });
                    }
                }

            } catch (error) {
                console.error('❌ Signup error:', error);

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
                            AutoSave.clear();
                            showToast('¡Cuenta creada exitosamente!', 'success');
                            setTimeout(() => {
                                window.location.href = data.redirect_url || '/incorporacion/';
                            }, 1500);
                        }
                    },
                    onError: () => {
                        submitBtn.classList.remove('is-loading');
                        submitBtn.disabled = false;
                    }
                }, {
                    context: 'signup',
                    autoRetry: true
                });

                submitBtn.classList.remove('is-loading');
                submitBtn.disabled = false;

                if (typeof gtag !== 'undefined') {
                    gtag('event', 'signup_network_error', {
                        'event_category': 'authentication',
                        'event_label': 'ajax-signup',
                        'value': 0
                    });
                }
            }
        });

        console.log('✅ AJAX form submission initialized');
    }

    // ========================================
    // 11. GOOGLE OAUTH LOADING
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

            if (typeof gtag !== 'undefined') {
                gtag('event', 'signup_google_oauth', {
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
    // 12. INIT ON DOM READY
    // ========================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            const form = document.querySelector('.auth-form');
            AutoSave.init(form);
            initRealtimeValidation();
            initAjaxSubmit();
            initGoogleOAuthLoading();
            console.log('✅ Auth Signup Enhanced initialized');
        } catch (error) {
            console.error('❌ Auth Signup Enhanced initialization error:', error);
        }
    }

    // Auto-initialize
    init();

})();
