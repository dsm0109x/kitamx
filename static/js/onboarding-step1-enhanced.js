/**
 * ONBOARDING STEP 1 - ENHANCED
 * Validación en tiempo real + AJAX + Auto-save + Unified UX
 *
 * Features:
 * - ✅ Validación en tiempo real (todos los campos)
 * - ✅ RFC AJAX validation (mantiene existente)
 * - ✅ AJAX form submission
 * - ✅ Auto-save con LocalStorage
 * - ✅ Sub-steps tracking
 * - ✅ Loading states
 * - ✅ Toast notifications
 * - ✅ Estados visuales (.is-valid, .is-invalid)
 *
 * @version 2.0 - Enhanced + Unified with auth
 */

'use strict';

(function() {
    // ========================================
    // 1. VALIDATION HELPERS
    // ========================================

    const ValidationHelpers = {
        validateRequired(value, fieldName) {
            if (!value || value.trim() === '') {
                return { valid: false, message: `${fieldName} es requerido` };
            }
            return { valid: true, message: '' };
        },

        validateName(value, fieldName) {
            if (!value || value.trim() === '') {
                return { valid: false, message: `${fieldName} es requerido` };
            }
            if (value.trim().length < 2) {
                return { valid: false, message: `${fieldName} debe tener al menos 2 caracteres` };
            }
            return { valid: true, message: '' };
        },

        validateBusinessName(value) {
            const trimmed = value.trim();

            if (!trimmed) {
                return { valid: false, message: 'Razón social es requerida' };
            }
            if (trimmed.length < 3) {
                return { valid: false, message: 'Razón social debe tener al menos 3 caracteres' };
            }
            if (trimmed.length > 255) {
                return { valid: false, message: 'Razón social no puede exceder 255 caracteres' };
            }

            // Validar caracteres permitidos (mismo patrón que backend)
            const validCharsPattern = /^[A-Za-zÀ-ÿÑñ0-9\s\-.,&'\"()]+$/;
            if (!validCharsPattern.test(trimmed)) {
                return { valid: false, message: 'Razón social contiene caracteres inválidos' };
            }

            return { valid: true, message: '' };
        },

        validateEmail(email) {
            if (!email || email.trim() === '') {
                return { valid: false, message: 'El email es requerido' };
            }

            const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!regex.test(email)) {
                return { valid: false, message: 'Formato de email inválido' };
            }

            if (email.length > 254) {
                return { valid: false, message: 'Email no puede exceder 254 caracteres' };
            }

            return { valid: true, message: '' };
        },

        validatePhone(phone) {
            // Phone es opcional
            if (!phone || phone.trim() === '') {
                return { valid: true, message: '' };
            }

            const cleaned = phone.replace(/\D/g, '');
            if (cleaned.length !== 10) {
                return { valid: false, message: 'El teléfono debe tener 10 dígitos' };
            }

            return { valid: true, message: '' };
        },

        validatePostalCode(code) {
            if (!code || code.trim() === '') {
                return { valid: false, message: 'El código postal es requerido' };
            }

            const cleaned = code.replace(/\D/g, '');
            if (cleaned.length !== 5) {
                return { valid: false, message: 'Debe tener 5 dígitos' };
            }

            return { valid: true, message: '' };
        },

        validateFiscalRegime(regime) {
            if (!regime || regime === '') {
                return { valid: false, message: 'Selecciona tu régimen fiscal' };
            }

            // Validar que sea uno de los códigos permitidos
            const validRegimes = ['612', '626', '621', '606', '605', '615'];
            if (!validRegimes.includes(regime)) {
                return { valid: false, message: 'Régimen fiscal inválido' };
            }

            return { valid: true, message: '' };
        }
    };

    // ========================================
    // 2. UI HELPERS
    // ========================================

    const UIHelpers = {
        setFieldError(input, message) {
            if (!input) return;

            input.classList.add('is-invalid');
            input.classList.remove('is-valid', 'is-validating');

            // Crear o actualizar mensaje de error
            let errorDiv = input.parentElement.querySelector('.invalid-feedback');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback d-block';
                errorDiv.setAttribute('role', 'alert');

                // Insertar antes del form-text si existe
                const formText = input.parentElement.querySelector('.form-text');
                if (formText) {
                    input.parentElement.insertBefore(errorDiv, formText);
                } else {
                    input.parentElement.appendChild(errorDiv);
                }
            }

            errorDiv.textContent = message;
            input.setAttribute('aria-invalid', 'true');
        },

        setFieldValid(input) {
            if (!input) return;

            input.classList.add('is-valid');
            input.classList.remove('is-invalid', 'is-validating');

            // Remover mensaje de error
            const errorDiv = input.parentElement.querySelector('.invalid-feedback');
            if (errorDiv && !errorDiv.id) {  // No remover si tiene ID (puede ser del form)
                errorDiv.remove();
            }

            input.setAttribute('aria-invalid', 'false');
        },

        clearFieldValidation(input) {
            if (!input) return;

            input.classList.remove('is-valid', 'is-invalid', 'is-validating');

            const errorDiv = input.parentElement.querySelector('.invalid-feedback');
            if (errorDiv && !errorDiv.id) {
                errorDiv.remove();
            }

            input.removeAttribute('aria-invalid');
        },

        setFieldValidating(input) {
            if (!input) return;
            input.classList.add('is-validating');
            input.classList.remove('is-valid', 'is-invalid');
        }
    };

    // ========================================
    // 3. AUTO-SAVE SYSTEM
    // ========================================

    const AutoSave = {
        prefix: 'kita_onboarding_step1_',

        save(name, value) {
            try {
                // BUG FIX #27: Test storage availability and handle quota exceeded
                const testKey = this.prefix + '__test__';
                localStorage.setItem(testKey, value);
                localStorage.removeItem(testKey);

                // If test passed, save actual data
                localStorage.setItem(this.prefix + name, value);
            } catch (e) {
                if (e.name === 'QuotaExceededError') {
                    console.error('LocalStorage quota exceeded');
                    if (typeof showToast !== 'undefined') {
                        showToast('⚠️ Espacio de almacenamiento lleno. Guarda tu progreso pronto.', 'warning');
                    }
                } else {
                    console.warn('LocalStorage not available:', e);
                }
            }
        },

        restore(name) {
            try {
                return localStorage.getItem(this.prefix + name) || '';
            } catch (e) {
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

            const inputs = form.querySelectorAll('input:not([type="hidden"]), textarea, select');
            let fieldsRestored = 0;

            inputs.forEach(input => {
                // Restaurar valores guardados
                const saved = this.restore(input.name);
                if (saved && !input.value) {
                    input.value = saved;
                    fieldsRestored++;
                }

                // Guardar mientras escribe (debounced)
                input.addEventListener('input', this.debounce(() => {
                    this.save(input.name, input.value);
                    this.showIndicator();
                }, 2000));
            });

            if (fieldsRestored > 0) {
                if (typeof showToast !== 'undefined') {
                    showToast(`✓ ${fieldsRestored} campos restaurados del borrador`, 'info');
                }
            }

            console.log('✅ Auto-save initialized');
        },

        showIndicator() {
            const indicator = document.getElementById('autoSaveIndicator');
            if (!indicator) return;

            indicator.textContent = '✓ Borrador guardado';
            indicator.classList.add('show');

            setTimeout(() => {
                indicator.classList.remove('show');
            }, 2000);
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
    // 4. SUB-STEPS TRACKING
    // ========================================

    function updateSubStepProgress(field) {
        const section = field.closest('[data-section]')?.dataset.section;

        // Reset all substeps
        document.querySelectorAll('.sub-steps li').forEach(li => {
            li.classList.remove('active');
        });

        // Mark current substep
        const substepBasic = document.getElementById('substep-basic');
        const substepFiscal = document.getElementById('substep-fiscal');
        const substepAddress = document.getElementById('substep-address');

        if (section === 'basic') {
            substepBasic?.classList.add('active');
        } else if (section === 'fiscal') {
            substepBasic?.classList.add('completed');
            substepFiscal?.classList.add('active');
        } else if (section === 'address') {
            substepBasic?.classList.add('completed');
            substepFiscal?.classList.add('completed');
            substepAddress?.classList.add('active');
        }
    }

    // ========================================
    // 5. RFC VALIDATION (AJAX) - ENHANCED WITH TIMEOUT & LOCAL VALIDATION
    // ========================================

    let rfcValidationTimeout;
    let lastValidatedRFC = '';
    let rfcAbortController = null;

    function initRFCValidation() {
        const rfcField = document.getElementById('id_rfc');
        if (!rfcField) return;

        rfcField.addEventListener('input', function() {
            const rfc = this.value.trim().toUpperCase();
            this.value = rfc;

            clearTimeout(rfcValidationTimeout);
            UIHelpers.clearFieldValidation(this);

            // Validar longitud exacta (solo personas físicas = 13 caracteres)
            if (rfc.length < 13) return;  // Esperar a que termine de escribir

            if (rfc.length !== 13) {
                UIHelpers.setFieldError(this, 'RFC debe tener exactamente 13 caracteres (solo personas físicas)');
                return;
            }

            // BUG FIX #21: Validación LOCAL de formato ANTES del AJAX (ahorra requests)
            // Persona Física: 4 letras + 6 dígitos + 2 caracteres alfanuméricos + 1 dígito verificador (0-9 o A)
            const rfcPattern = /^[A-ZÑ&]{4}\d{6}[A-Z0-9]{2}[0-9A]$/;
            if (!rfcPattern.test(rfc)) {
                UIHelpers.setFieldError(this, 'Formato de RFC inválido - Debe ser: 4 letras + 6 dígitos + 3 caracteres (homoclave)');
                return;  // No hacer AJAX si formato es inválido
            }

            // Detectar RFCs genéricos conocidos
            const invalidRFCs = ['XAXX010101000', 'XEXX010101000', 'AAA010101AAA'];
            if (invalidRFCs.includes(rfc)) {
                UIHelpers.setFieldError(this, 'RFC genérico no permitido');
                return;
            }

            // Detectar fechas inválidas (000000)
            if (rfc.includes('000000')) {
                UIHelpers.setFieldError(this, 'RFC con fecha inválida');
                return;
            }

            UIHelpers.setFieldValidating(this);

            rfcValidationTimeout = setTimeout(async () => {
                // Cache check
                if (rfc === lastValidatedRFC) {
                    UIHelpers.setFieldValid(rfcField);
                    return;
                }

                // Cancelar request pendiente si existe
                if (rfcAbortController) {
                    rfcAbortController.abort();
                }

                // Nuevo AbortController para este request
                rfcAbortController = new AbortController();
                const timeoutId = setTimeout(() => rfcAbortController.abort(), 10000);

                try {
                    const response = await fetch('/incorporacion/api/validar-rfc/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken()
                        },
                        body: JSON.stringify({ rfc: rfc }),
                        signal: rfcAbortController.signal  // ← Timeout + cancelación
                    });

                    clearTimeout(timeoutId);

                    const data = await response.json();

                    if (data.valid) {
                        UIHelpers.setFieldValid(rfcField);
                        lastValidatedRFC = rfc;
                        if (typeof showToast !== 'undefined') {
                            showToast('✓ RFC válido y disponible', 'success');
                        }
                    } else {
                        UIHelpers.setFieldError(rfcField, data.message);
                    }
                } catch (err) {
                    clearTimeout(timeoutId);

                    // Diferenciar entre abort y network error
                    if (err.name === 'AbortError') {
                        console.log('[RFC] Request cancelled or timeout');
                        UIHelpers.setFieldError(rfcField, 'Validación interrumpida - intenta de nuevo');
                    } else {
                        console.error('[RFC] Validation error:', err);
                        UIHelpers.setFieldError(rfcField, 'Error de conexión - verifica tu internet');
                    }
                } finally {
                    rfcAbortController = null;
                }
            }, 500);  // BUG FIX #16: Reduced from 800ms to 500ms for better UX
        });

        // BUG FIX #3: Auto-uppercase y clear cache en blur para forzar re-validación
        rfcField.addEventListener('blur', function() {
            this.value = this.value.trim().toUpperCase();
            // Invalidar cache para forzar re-validación en siguiente input
            // Previene que RFC tomado por otro usuario pase validación
            lastValidatedRFC = '';
        });

        console.log('✅ RFC validation initialized (solo personas físicas)');
    }

    // ========================================
    // 6. REAL-TIME VALIDATION
    // ========================================

    function initRealtimeValidation() {
        const form = document.getElementById('step1Form');
        if (!form) return;

        // Nombre comercial
        const nameInput = form.querySelector('input[name="name"]');
        if (nameInput) {
            nameInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validateName(this.value, 'Nombre comercial');
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
            nameInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        // Razón social (validación completa)
        const businessNameInput = form.querySelector('input[name="business_name"]');
        if (businessNameInput) {
            businessNameInput.addEventListener('blur', function() {
                const value = this.value.trim();

                if (!value) {
                    UIHelpers.setFieldError(this, 'Razón social es requerida');
                } else if (value.length < 3) {
                    UIHelpers.setFieldError(this, 'Razón social debe tener al menos 3 caracteres');
                } else if (value.length > 255) {
                    UIHelpers.setFieldError(this, 'Razón social no puede exceder 255 caracteres');
                } else if (!/^[A-Za-zÀ-ÿÑñ0-9\s\-.,&'\"()]+$/.test(value)) {
                    UIHelpers.setFieldError(this, 'Razón social contiene caracteres inválidos (solo letras, números y . , - & \' " ( ))');
                } else {
                    UIHelpers.setFieldValid(this);
                }
            });
            businessNameInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        // Email - readonly, siempre válido (no necesita validación)

        // Phone - Simple validation (10 dígitos mexicanos)
        const phoneInput = form.querySelector('input[name="phone"]');
        if (phoneInput) {
            phoneInput.addEventListener('input', function() {
                // Solo números
                this.value = this.value.replace(/\D/g, '').substring(0, 10);
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });

            phoneInput.addEventListener('blur', function() {
                const value = this.value.trim();

                // Opcional, solo validar si tiene valor
                if (value) {
                    if (value.length !== 10) {
                        UIHelpers.setFieldError(this, 'El teléfono debe tener exactamente 10 dígitos');
                    } else {
                        UIHelpers.setFieldValid(this);
                    }
                } else {
                    UIHelpers.clearFieldValidation(this);
                }
            });
        }

        // Postal code con validación de rangos
        const postalCodeInput = form.querySelector('input[name="codigo_postal"]');
        if (postalCodeInput) {
            postalCodeInput.addEventListener('input', function() {
                // Solo números, max 5
                this.value = this.value.replace(/[^0-9]/g, '').substring(0, 5);
                UIHelpers.clearFieldValidation(this);
            });

            // BUG FIX #34: ELIMINADA validación de rangos hardcoded (duplicación con SEPOMEX)
            // Delegar 100% validación a address-autocomplete.js que consulta DB SEPOMEX (fuente de verdad)
            postalCodeInput.addEventListener('blur', function() {
                const cp = this.value.trim();

                // Solo validación básica de formato
                if (!cp) {
                    UIHelpers.setFieldError(this, 'Código postal es requerido');
                    return;
                }

                if (cp.length !== 5) {
                    UIHelpers.setFieldError(this, 'Código postal debe tener exactamente 5 dígitos');
                    return;
                }

                // BUG FIX #23: Rechazar "00000" que es inválido
                if (cp === '00000') {
                    UIHelpers.setFieldError(this, 'Código postal inválido');
                    return;
                }

                // Si pasa validación básica, marcar como validating
                // address-autocomplete.js tomará control y validará contra SEPOMEX DB
                UIHelpers.setFieldValidating(this);
            }, { once: false });  // No usar once, address-autocomplete también escucha blur
        }

        // Colonia - validación completa del hidden field
        const coloniaHidden = form.querySelector('input[name="colonia"]');
        const coloniaSelect = document.getElementById('id_colonia_select');
        const coloniaCustom = document.getElementById('id_colonia_custom');

        if (coloniaHidden) {
            const validateColonia = () => {
                const value = coloniaHidden.value.trim();

                if (!value) {
                    // Si está vacío, marcar como inválido el visible
                    if (coloniaSelect && coloniaSelect.style.display !== 'none') {
                        UIHelpers.setFieldError(coloniaSelect, 'Selecciona tu colonia');
                    }
                    if (coloniaCustom && coloniaCustom.style.display !== 'none') {
                        UIHelpers.setFieldError(coloniaCustom, 'Escribe el nombre de tu colonia');
                    }
                    return;
                }

                // Si tiene valor, marcar como válido
                // La validación de que corresponda al CP se hace en el backend (clean method)
                if (coloniaSelect && coloniaSelect.style.display !== 'none') {
                    UIHelpers.setFieldValid(coloniaSelect);
                }
                if (coloniaCustom && coloniaCustom.style.display !== 'none') {
                    UIHelpers.setFieldValid(coloniaCustom);
                }
            };

            // Watch for changes in hidden field
            const observer = new MutationObserver(validateColonia);
            observer.observe(coloniaHidden, {
                attributes: true,
                attributeFilter: ['value']
            });

            // Validar cuando cambia el select
            if (coloniaSelect) {
                coloniaSelect.addEventListener('change', function() {
                    coloniaHidden.value = this.value;
                    validateColonia();
                });
            }

            // Validar cuando escribe en custom input
            if (coloniaCustom) {
                coloniaCustom.addEventListener('input', function() {
                    coloniaHidden.value = this.value;
                    validateColonia();
                });

                coloniaCustom.addEventListener('blur', function() {
                    validateColonia();
                });
            }
        }

        // Calle - validación completa
        const calleInput = form.querySelector('input[name="calle"]');
        if (calleInput) {
            calleInput.addEventListener('blur', function() {
                const value = this.value.trim();

                if (!value) {
                    UIHelpers.setFieldError(this, 'Calle es requerida');
                } else if (value.length < 3) {
                    UIHelpers.setFieldError(this, 'Calle debe tener al menos 3 caracteres');
                } else if (value.length > 255) {
                    UIHelpers.setFieldError(this, 'Calle no puede exceder 255 caracteres');
                } else {
                    UIHelpers.setFieldValid(this);
                }
            });
            calleInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        // Número exterior - validación con formato
        const numeroExteriorInput = form.querySelector('input[name="numero_exterior"]');
        if (numeroExteriorInput) {
            numeroExteriorInput.addEventListener('blur', function() {
                const value = this.value.trim();

                if (!value) {
                    UIHelpers.setFieldError(this, 'Número exterior es requerido');
                } else if (value.length > 20) {
                    UIHelpers.setFieldError(this, 'Número exterior no puede exceder 20 caracteres');
                } else if (!/^[A-Za-z0-9\-]+$/.test(value)) {
                    UIHelpers.setFieldError(this, 'Solo letras, números y guiones (ej: 250, 123-A)');
                } else {
                    UIHelpers.setFieldValid(this);
                }
            });
            numeroExteriorInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        // Número interior (opcional)
        const numeroInteriorInput = form.querySelector('input[name="numero_interior"]');
        if (numeroInteriorInput) {
            numeroInteriorInput.addEventListener('blur', function() {
                // Opcional, solo validar si tiene valor
                if (this.value.trim()) {
                    UIHelpers.setFieldValid(this);
                } else {
                    UIHelpers.clearFieldValidation(this);
                }
            });
        }

        // BUG FIX #5: Municipio (readonly, auto-filled - validar con input event en vez de MutationObserver)
        // MutationObserver no detecta cambios a .value property, solo attributes
        const municipioInput = form.querySelector('input[name="municipio"]');
        if (municipioInput) {
            // Usar input event para detectar cambios programáticos
            municipioInput.addEventListener('input', function() {
                if (this.value.trim()) {
                    UIHelpers.setFieldValid(this);
                }
            });
            // También validar en blur
            municipioInput.addEventListener('blur', function() {
                if (this.value.trim()) {
                    UIHelpers.setFieldValid(this);
                }
            });
        }

        // BUG FIX #5: Estado (readonly, auto-filled - validar con input event en vez de MutationObserver)
        const estadoInput = form.querySelector('input[name="estado"]');
        if (estadoInput) {
            // Usar input event para detectar cambios programáticos
            estadoInput.addEventListener('input', function() {
                if (this.value.trim()) {
                    UIHelpers.setFieldValid(this);
                }
            });
            // También validar en blur
            estadoInput.addEventListener('blur', function() {
                if (this.value.trim()) {
                    UIHelpers.setFieldValid(this);
                }
            });
        }

        // Fiscal regime
        const fiscalRegimeSelect = form.querySelector('select[name="fiscal_regime"]');
        if (fiscalRegimeSelect) {
            fiscalRegimeSelect.addEventListener('change', function() {
                const result = ValidationHelpers.validateFiscalRegime(this.value);
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
        }

        // Address
        const addressInput = form.querySelector('textarea[name="address"]');
        if (addressInput) {
            addressInput.addEventListener('blur', function() {
                const result = ValidationHelpers.validateRequired(this.value, 'Dirección fiscal');
                result.valid ? UIHelpers.setFieldValid(this) : UIHelpers.setFieldError(this, result.message);
            });
            addressInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) UIHelpers.clearFieldValidation(this);
            });
        }

        console.log('✅ Real-time validation initialized');
    }

    // ========================================
    // 7. AJAX FORM SUBMISSION
    // ========================================

    function initAjaxSubmit() {
        const form = document.getElementById('step1Form');
        const submitBtn = document.getElementById('submitBtn');

        if (!form || !submitBtn) {
            console.warn('⚠️ Form or submit button not found');
            return;
        }

        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Validar HTML5 constraints
            if (!form.checkValidity()) {
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });

                    const fieldName = firstInvalid.labels && firstInvalid.labels[0]
                        ? firstInvalid.labels[0].textContent.trim()
                        : 'Campo';

                    if (typeof showToast !== 'undefined') {
                        showToast(`${fieldName}: ${firstInvalid.validationMessage}`, 'error');
                    }
                }
                return;
            }

            // Loading states
            submitBtn.classList.add('btn-submitting');
            submitBtn.disabled = true;

            const btnContent = submitBtn.querySelector('.btn-content');
            const btnLoading = submitBtn.querySelector('.btn-loading');

            if (btnContent) btnContent.classList.add('d-none');
            if (btnLoading) btnLoading.classList.remove('d-none');

            // Multi-stage loading (nueva API)
            if (typeof loading !== 'undefined' && loading.start) {
                loading.start([
                    'Validando datos fiscales...',
                    'Verificando RFC...',
                    'Guardando información...'
                ]);
            } else if (typeof showLoading !== 'undefined') {
                showLoading('Guardando tu información...');
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

                // Parse response (con fix para debug toolbar)
                const text = await response.text();
                let parsed = JSON.parse(text);

                let data;
                if (parsed.html && typeof parsed.html === 'string') {
                    data = JSON.parse(parsed.html);
                } else {
                    data = parsed;
                }

                if (response.ok && data.success) {
                    // ✅ Success
                    AutoSave.clear();

                    // Hide loading (nueva API)
                    if (typeof loading !== 'undefined' && loading.done) {
                        loading.done();
                    } else if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    if (typeof showToast !== 'undefined') {
                        showToast('✓ Información guardada exitosamente', 'success');
                    }

                    // Redirect
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/incorporacion/paso2/';
                    }, 1000);

                } else {
                    // ❌ Error
                    // Hide loading (nueva API)
                    if (typeof loading !== 'undefined' && loading.cancel) {
                        loading.cancel();
                    } else if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    submitBtn.classList.remove('btn-submitting');
                    submitBtn.disabled = false;
                    if (btnContent) btnContent.classList.remove('d-none');
                    if (btnLoading) btnLoading.classList.add('d-none');

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
                    if (data.error && typeof showToast !== 'undefined') {
                        showToast(data.error, 'error');
                    }
                }

            } catch (error) {
                console.error('❌ Onboarding submit error:', error);

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
                                AutoSave.clear();
                                showToast('✓ Información guardada exitosamente', 'success');
                                setTimeout(() => {
                                    window.location.href = data.redirect_url || '/incorporacion/paso2/';
                                }, 1000);
                            }
                        },
                        onError: () => {
                            submitBtn.classList.remove('btn-submitting');
                            submitBtn.disabled = false;
                            if (btnContent) btnContent.classList.remove('d-none');
                            if (btnLoading) btnLoading.classList.add('d-none');
                        }
                    }, {
                        context: 'onboarding_step1',
                        autoRetry: true
                    });
                } else {
                    // BUG FIX #82: Fallback - usar mensaje del error si está disponible
                    if (typeof hideLoading !== 'undefined') hideLoading();
                    if (typeof showToast !== 'undefined') {
                        const errorMsg = error.message || 'Error de conexión. Por favor intenta de nuevo.';
                        showToast(errorMsg, 'error');
                    }
                }

                submitBtn.classList.remove('btn-submitting');
                submitBtn.disabled = false;
                if (btnContent) btnContent.classList.remove('d-none');
                if (btnLoading) btnLoading.classList.add('d-none');
            }
        });

        console.log('✅ AJAX form submission initialized');
    }

    // ========================================
    // 8. TOOLTIPS
    // ========================================

    function initTooltips() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        if (typeof bootstrap !== 'undefined') {
            tooltipTriggerList.map(el => new bootstrap.Tooltip(el));
        }
        console.log('✅ Tooltips initialized');
    }

    // ========================================
    // 9. MOBILE HELP EXPANDABLE
    // ========================================

    function initMobileHelp() {
        const isMobile = window.innerWidth < 992;
        if (!isMobile) return;

        const fieldsWithHelp = document.querySelectorAll('[data-help-target]');

        fieldsWithHelp.forEach(field => {
            field.addEventListener('focus', function() {
                const helpId = this.dataset.helpTarget;
                const helpElement = document.getElementById(helpId);

                if (helpElement) {
                    document.querySelectorAll('.help-expandable').forEach(el => {
                        el.classList.remove('show');
                    });
                    helpElement.classList.add('show');
                }
            });

            field.addEventListener('blur', function() {
                const helpId = this.dataset.helpTarget;
                const helpElement = document.getElementById(helpId);

                if (helpElement) {
                    setTimeout(() => {
                        helpElement.classList.remove('show');
                    }, 200);
                }
            });
        });

        console.log('✅ Mobile help initialized');
    }

    // ========================================
    // 10. SUB-STEP FOCUS TRACKING
    // ========================================

    function initSubStepTracking() {
        const fieldsWithTips = document.querySelectorAll('[data-tip]');
        fieldsWithTips.forEach(field => {
            field.addEventListener('focus', () => {
                updateSubStepProgress(field);
            });
        });

        console.log('✅ Sub-step tracking initialized');
    }

    // ========================================
    // 11. UTILS
    // ========================================

    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }

    // ========================================
    // 12. INIT ON DOM READY + VALIDATE PREFILLED VALUES
    // ========================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            const form = document.getElementById('step1Form');

            initTooltips();
            AutoSave.init(form);
            initRFCValidation();
            initRealtimeValidation();
            initMobileHelp();
            initSubStepTracking();
            initAjaxSubmit();

            // ========================================
            // VALIDATE PREFILLED VALUES (edit mode)
            // ========================================
            // Si el usuario regresa a step 1, validar campos que ya tienen valor

            setTimeout(() => {
                // Nombre Comercial
                const nameInput = form.querySelector('input[name="name"]');
                if (nameInput && nameInput.value.trim().length >= 2) {
                    UIHelpers.setFieldValid(nameInput);
                }

                // Razón Social
                const businessNameInput = form.querySelector('input[name="business_name"]');
                if (businessNameInput && businessNameInput.value.trim().length >= 3) {
                    const result = ValidationHelpers.validateBusinessName(businessNameInput.value);
                    if (result.valid) UIHelpers.setFieldValid(businessNameInput);
                }

                // RFC - Si tiene 13 caracteres, trigger validación AJAX
                const rfcInput = document.getElementById('id_rfc');
                if (rfcInput && rfcInput.value.trim().length === 13) {
                    console.log('🆔 RFC prellenado detectado, validando...');
                    // Trigger input event para que se valide
                    rfcInput.dispatchEvent(new Event('input', { bubbles: true }));
                }

                // Régimen Fiscal
                const regimeSelect = form.querySelector('select[name="fiscal_regime"]');
                if (regimeSelect && regimeSelect.value) {
                    UIHelpers.setFieldValid(regimeSelect);
                }

                // Email - readonly, ya tiene .is-valid en HTML

                // Teléfono
                const phoneInput = form.querySelector('input[name="phone"]');
                if (phoneInput && phoneInput.value.trim().length === 10) {
                    UIHelpers.setFieldValid(phoneInput);
                }

                // Municipio y Estado (readonly, si tienen valor)
                const municipioInput = form.querySelector('input[name="municipio"]');
                if (municipioInput && municipioInput.value.trim()) {
                    UIHelpers.setFieldValid(municipioInput);
                }

                const estadoInput = form.querySelector('input[name="estado"]');
                if (estadoInput && estadoInput.value.trim()) {
                    UIHelpers.setFieldValid(estadoInput);
                }

                // Calle
                const calleInput = form.querySelector('input[name="calle"]');
                if (calleInput && calleInput.value.trim().length >= 3) {
                    UIHelpers.setFieldValid(calleInput);
                }

                // Número Exterior
                const numExtInput = form.querySelector('input[name="numero_exterior"]');
                if (numExtInput && numExtInput.value.trim()) {
                    UIHelpers.setFieldValid(numExtInput);
                }

                // Número Interior (opcional)
                const numIntInput = form.querySelector('input[name="numero_interior"]');
                if (numIntInput && numIntInput.value.trim()) {
                    UIHelpers.setFieldValid(numIntInput);
                }

                console.log('✅ Prefilled values validated');
            }, 500);  // Delay para que address-autocomplete.js termine de cargar

            console.log('✅ Onboarding Step 1 Enhanced initialized');
        } catch (error) {
            console.error('❌ Onboarding Step 1 initialization error:', error);
        }
    }

    // Auto-initialize
    init();

})();
