/**
 * Onboarding Common Utilities
 *
 * BUG FIX #25: Shared utilities for all onboarding steps to avoid duplication
 *
 * Functions exported to window object for global access
 *
 * @version 1.0
 */

'use strict';

(function() {
    /**
     * Get CSRF token from DOM or cookie
     *
     * Priority order:
     * 1. Input hidden field [name=csrfmiddlewaretoken]
     * 2. Cookie csrftoken
     *
     * @returns {string} CSRF token value
     */
    function getCsrfToken() {
        // Priority 1: Input hidden field (from {% csrf_token %})
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput && csrfInput.value) {
            return csrfInput.value;
        }

        // Priority 2: Cookie (Django's CSRF_COOKIE_NAME)
        const csrfCookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));

        if (csrfCookie) {
            return csrfCookie.split('=')[1];
        }

        // Fallback: empty string (will fail CSRF check)
        console.warn('⚠️ CSRF token not found in DOM or cookies');
        return '';
    }

    /**
     * Navigate to dashboard with proper cleanup
     *
     * Clears any pending timers and intervals before navigation
     */
    function goToDashboard() {
        // Clear any pending timers
        if (window.redirectTimeout) {
            clearTimeout(window.redirectTimeout);
            window.redirectTimeout = null;
        }
        if (window.countdownInterval) {
            clearInterval(window.countdownInterval);
            window.countdownInterval = null;
        }

        window.location.href = '/panel/';
    }

    // Export to window object for global access
    window.getCsrfToken = getCsrfToken;
    window.goToDashboard = goToDashboard;

    // Also export as object for namespaced access
    window.OnboardingCommon = {
        getCsrfToken,
        goToDashboard
    };
})();
