/**
 * KITA GLOBAL UTILITIES
 * Centralized helper functions for reuse across all modules
 * Version: 1.0.0
 */

(function() {
    'use strict';

    window.KitaUtils = {

        /**
         * Get CSRF token from DOM or cookies
         * @returns {string} CSRF token
         */
        getCsrfToken: function() {
            // Try to get from hidden input first
            const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
            if (csrfInput) {
                return csrfInput.value;
            }

            // Fallback to cookie
            const csrfCookie = document.cookie
                .split('; ')
                .find(row => row.startsWith('csrftoken='));

            return csrfCookie ? csrfCookie.split('=')[1] : '';
        },

        /**
         * Escape HTML to prevent XSS
         * @param {string} text - Text to escape
         * @returns {string} Escaped HTML
         */
        escapeHtml: function(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * Copy text to clipboard with feedback
         * @param {string} text - Text to copy
         * @param {string} successMsg - Success message
         */
        copyToClipboard: function(text, successMsg = 'Copiado al portapapeles') {
            navigator.clipboard.writeText(text).then(
                () => {
                    if (typeof showToast !== 'undefined') {
                        showToast(successMsg, 'success');
                    }
                },
                (err) => {
                    console.error('Clipboard error:', err);
                    if (typeof showToast !== 'undefined') {
                        showToast('Error al copiar', 'error');
                    }
                }
            );
        },

        /**
         * Format currency amount
         * @param {number} amount - Amount to format
         * @param {string} currency - Currency code
         * @returns {string} Formatted currency
         */
        formatCurrency: function(amount, currency = 'MXN') {
            return `$${parseFloat(amount).toFixed(2)} ${currency}`;
        },

        /**
         * Format date
         * @param {string|Date} dateStr - Date to format
         * @param {object} options - Intl.DateTimeFormat options
         * @returns {string} Formatted date
         */
        formatDate: function(dateStr, options = {}) {
            const date = new Date(dateStr);
            const defaultOptions = {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                ...options
            };
            return date.toLocaleDateString('es-MX', defaultOptions);
        },

        /**
         * Format date and time
         * @param {string|Date} dateStr - Date to format
         * @returns {string} Formatted date and time
         */
        formatDateTime: function(dateStr) {
            const date = new Date(dateStr);
            return date.toLocaleString('es-MX', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        /**
         * Debounce function calls
         * @param {function} func - Function to debounce
         * @param {number} wait - Wait time in milliseconds
         * @returns {function} Debounced function
         */
        debounce: function(func, wait = 300) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },

        /**
         * Throttle function calls
         * @param {function} func - Function to throttle
         * @param {number} limit - Limit time in milliseconds
         * @returns {function} Throttled function
         */
        throttle: function(func, limit = 300) {
            let inThrottle;
            return function(...args) {
                if (!inThrottle) {
                    func.apply(this, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        },

        /**
         * Validate email format
         * @param {string} email - Email to validate
         * @returns {boolean} Is valid email
         */
        isValidEmail: function(email) {
            const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return re.test(email);
        },

        /**
         * Validate RFC format (Mexico)
         * @param {string} rfc - RFC to validate
         * @returns {boolean} Is valid RFC
         */
        isValidRFC: function(rfc) {
            const re = /^([A-ZÑ&]{3,4})\d{6}([A-Z\d]{3})$/;
            return re.test(rfc.toUpperCase());
        }
    };

    // Create shortcuts for most used functions
    window.getCsrfToken = window.KitaUtils.getCsrfToken;
    window.escapeHtml = window.KitaUtils.escapeHtml;
    window.copyToClipboard = window.KitaUtils.copyToClipboard;

    console.log('KitaUtils: Loaded successfully');

})();
