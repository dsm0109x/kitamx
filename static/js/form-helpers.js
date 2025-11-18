/**
 * FORM HELPERS - GLOBAL UTILITIES
 * =================================
 *
 * Utilidades globales para manejo de formularios en Kita Platform.
 * Compatible con componentes de templates/components/
 *
 * Features:
 * - Password visibility toggle (event delegation)
 * - Form validation helpers
 * - Accessible focus management
 * - Error state management
 *
 * @version 1.0
 * @created 2025-10-21
 */

'use strict';

(function() {
    // ========================================
    // 1. PASSWORD VISIBILITY TOGGLE
    // ========================================

    /**
     * Maneja toggles de password con event delegation
     * Compatible con password_field.html component
     */
    function initPasswordToggles() {
        // Event delegation en document para soportar campos dinámicos
        document.addEventListener('click', function(e) {
            const toggleBtn = e.target.closest('.password-toggle');
            if (!toggleBtn) return;

            const targetId = toggleBtn.getAttribute('data-target');
            const input = document.getElementById(targetId);
            const icon = toggleBtn.querySelector('.toggle-icon');

            if (!input || !icon) return;

            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('iconoir-eye');
                icon.classList.add('iconoir-eye-closed');
                toggleBtn.setAttribute('aria-label', 'Ocultar contraseña');
            } else {
                input.type = 'password';
                icon.classList.remove('iconoir-eye-closed');
                icon.classList.add('iconoir-eye');
                toggleBtn.setAttribute('aria-label', 'Mostrar contraseña');
            }
        });

        console.log('✅ Password toggles initialized (event delegation)');
    }

    // ========================================
    // 2. FORM VALIDATION HELPERS
    // ========================================

    /**
     * Agrega clase .is-invalid a input y muestra error
     * Compatible con .form-error (legacy) y .invalid-feedback (bootstrap)
     *
     * @param {HTMLElement} input - El input field
     * @param {String} message - Mensaje de error
     * @param {String} style - 'legacy' o 'bootstrap' (default: 'bootstrap')
     */
    window.showFieldError = function(input, message, style = 'bootstrap') {
        if (!input) return;

        // Agregar clase is-invalid
        input.classList.add('is-invalid');
        input.setAttribute('aria-invalid', 'true');

        // Buscar o crear error div
        const errorSelector = style === 'legacy' ? '.form-error' : '.invalid-feedback';
        let errorDiv = input.parentElement.querySelector(errorSelector);

        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = style === 'legacy' ? 'form-error' : 'invalid-feedback d-block';
            errorDiv.setAttribute('role', 'alert');

            // Insertar después del input o password-wrapper
            const wrapper = input.closest('.password-wrapper');
            if (wrapper) {
                wrapper.parentElement.appendChild(errorDiv);
            } else {
                input.parentElement.appendChild(errorDiv);
            }
        }

        // Set error message
        if (style === 'legacy') {
            errorDiv.innerHTML = `<small>${message}</small>`;
        } else {
            errorDiv.innerHTML = `<span>${message}</span>`;
        }

        // Trigger shake animation
        input.style.animation = 'none';
        setTimeout(() => {
            input.style.animation = '';
        }, 10);
    };

    /**
     * Remueve error de un input
     *
     * @param {HTMLElement} input - El input field
     * @param {String} style - 'legacy' o 'bootstrap' (default: 'bootstrap')
     */
    window.clearFieldError = function(input, style = 'bootstrap') {
        if (!input) return;

        // Remover clase is-invalid
        input.classList.remove('is-invalid');
        input.removeAttribute('aria-invalid');

        // Remover error div
        const errorSelector = style === 'legacy' ? '.form-error' : '.invalid-feedback';
        const errorDiv = input.parentElement.querySelector(errorSelector);

        if (errorDiv) {
            errorDiv.remove();
        }
    };

    /**
     * Marca input como válido
     *
     * @param {HTMLElement} input - El input field
     * @param {String} message - Mensaje de éxito (opcional)
     */
    window.showFieldSuccess = function(input, message = null) {
        if (!input) return;

        // Agregar clase is-valid
        input.classList.add('is-valid');
        input.classList.remove('is-invalid');
        input.removeAttribute('aria-invalid');

        // Si hay mensaje, crear valid-feedback
        if (message) {
            let successDiv = input.parentElement.querySelector('.valid-feedback');

            if (!successDiv) {
                successDiv = document.createElement('div');
                successDiv.className = 'valid-feedback d-block';
                input.parentElement.appendChild(successDiv);
            }

            successDiv.textContent = message;
        }
    };

    /**
     * Resetea estado de validación de input
     *
     * @param {HTMLElement} input - El input field
     */
    window.resetFieldValidation = function(input) {
        if (!input) return;

        input.classList.remove('is-valid', 'is-invalid');
        input.removeAttribute('aria-invalid');

        // Remover mensajes
        const errorDiv = input.parentElement.querySelector('.form-error, .invalid-feedback');
        const successDiv = input.parentElement.querySelector('.valid-feedback');

        if (errorDiv) errorDiv.remove();
        if (successDiv) successDiv.remove();
    };

    // ========================================
    // 3. FORM GROUP ERROR STATE
    // ========================================

    /**
     * Agrega clase .has-error al form-group wrapper
     *
     * @param {HTMLElement} input - El input field
     */
    window.setFormGroupError = function(input) {
        const formGroup = input.closest('.form-group');
        if (formGroup) {
            formGroup.classList.add('has-error');
        }
    };

    /**
     * Remueve clase .has-error del form-group wrapper
     *
     * @param {HTMLElement} input - El input field
     */
    window.clearFormGroupError = function(input) {
        const formGroup = input.closest('.form-group');
        if (formGroup) {
            formGroup.classList.remove('has-error');
        }
    };

    // ========================================
    // 4. FOCUS MANAGEMENT
    // ========================================

    /**
     * Focus en primer campo con error
     */
    window.focusFirstError = function() {
        const firstError = document.querySelector('.form-control.is-invalid, .form-select.is-invalid');
        if (firstError) {
            firstError.focus();
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    };

    // ========================================
    // 5. INITIALIZATION
    // ========================================

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPasswordToggles);
    } else {
        initPasswordToggles();
    }

    console.log('✅ Form Helpers initialized');

})();
