/**
 * Onboarding Step 4: Trial Activation
 *
 * Extracted from inline <script> in step4.html
 *
 * Handles:
 * - Trial activation with confirmation modal
 * - Success modal with countdown timer
 * - Confetti celebration animation
 * - Loading states and error handling
 * - Warnings for incomplete setup (MP/CSD)
 *
 * Dependencies:
 * - onboarding-common.js (getCsrfToken, goToDashboard)
 * - Bootstrap 5 (modals)
 * - Toastify (notifications)
 * - loading-progress-system.js (optional)
 * - error-recovery-system.js (optional)
 *
 * @version 1.0
 */

'use strict';

(function() {
    // Inject CSS keyframes for confetti animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fall {
            to {
                transform: translateY(100vh) rotate(720deg);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    /**
     * Show trial confirmation modal
     */
    window.startTrial = function() {
        const modal = new bootstrap.Modal(document.getElementById('confirmTrialModal'));
        modal.show();
    };

    /**
     * Confirm and activate trial
     *
     * AJAX call to backend with loading states, success modal, and confetti
     */
    window.confirmStartTrial = async function() {
        const startBtn = document.getElementById('startTrialBtn');
        const confirmBtn = document.getElementById('confirmTrialBtn');
        const successModal = new bootstrap.Modal(document.getElementById('successModal'));

        // Hide confirm modal
        const confirmModal = bootstrap.Modal.getInstance(document.getElementById('confirmTrialModal'));
        confirmModal.hide();

        // Disable buttons
        if (startBtn) {
            startBtn.querySelector('.btn-content').classList.add('d-none');
            startBtn.querySelector('.btn-loading').classList.remove('d-none');
            startBtn.disabled = true;
        }
        if (confirmBtn) confirmBtn.disabled = true;

        // Use Loading Progress System
        if (typeof loading !== 'undefined' && loading.start) {
            loading.start([
                'Activando tu trial...',
                'Configurando acceso...',
                'Finalizando setup...'
            ]);
        } else {
            const loadingTopbar = document.getElementById('loadingTopbar');
            const loadingMessage = document.getElementById('loadingMessage');
            if (loadingTopbar) loadingTopbar.classList.add('active');
            if (loadingMessage) loadingMessage.classList.add('active');
        }

        const requestData = {
            url: '/incorporacion/api/iniciar-prueba/',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        };

        // Timeout de 10 segundos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        try {
            // Stage 1 → 2
            if (typeof loading !== 'undefined' && loading.next) {
                loading.next();
            }

            const response = await fetch(requestData.url, {
                method: requestData.method,
                headers: requestData.headers,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            // Stage 2 → 3
            if (typeof loading !== 'undefined' && loading.next) {
                loading.next();
            }

            const result = await response.json();

            if (result.success) {
                // Complete loading
                if (typeof loading !== 'undefined' && loading.done) {
                    loading.done();
                }

                // BUG FIX #24: Show warnings if trial activated without MP or CSD
                if (result.warnings && result.warnings.length > 0) {
                    result.warnings.forEach((warning, index) => {
                        setTimeout(() => showToast(`⚠️ ${warning}`, 'warning'), 500 + (index * 100));
                    });
                }

                // Analytics
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'trial_activation_success', {
                        'event_category': 'onboarding',
                        'event_label': 'step4_trial'
                    });
                }

                successModal.show();
                launchConfetti();

                // BUG FIX #21: Implement countdown timer that updates every second
                let countdown = 3;
                const countdownEl = document.getElementById('countdown');
                if (countdownEl) countdownEl.textContent = countdown;

                window.countdownInterval = setInterval(() => {
                    countdown--;
                    if (countdownEl) countdownEl.textContent = countdown;
                    if (countdown <= 0) {
                        clearInterval(window.countdownInterval);
                        window.countdownInterval = null;
                    }
                }, 1000);

                // BUG FIX #22: Store timeout ID so it can be cancelled if user clicks "Comenzar Ahora"
                window.redirectTimeout = setTimeout(() => {
                    window.location.href = '/panel/';
                }, 3000);
            } else {
                throw new Error(result.error || 'Error activando trial');
            }
        } catch (error) {
            clearTimeout(timeoutId);
            console.error('[Trial] Error:', error);

            // Cancel loading
            if (typeof loading !== 'undefined' && loading.cancel) {
                loading.cancel();
            } else {
                const loadingTopbar = document.getElementById('loadingTopbar');
                const loadingMessage = document.getElementById('loadingMessage');
                if (loadingTopbar) loadingTopbar.classList.remove('active');
                if (loadingMessage) loadingMessage.classList.remove('active');
            }

            if (startBtn) {
                startBtn.querySelector('.btn-content').classList.remove('d-none');
                startBtn.querySelector('.btn-loading').classList.add('d-none');
                startBtn.disabled = false;
            }
            if (confirmBtn) confirmBtn.disabled = false;

            // Manejar timeout específicamente
            if (error.name === 'AbortError') {
                showToast('⏱️ Activación interrumpida (timeout 10s). El servidor puede estar lento, intenta de nuevo.', 'error');
            } else if (typeof window.ErrorRecovery !== 'undefined') {
                // Use Error Recovery System
                window.ErrorRecovery.handleError(error, requestData, {
                    context: 'start_trial',
                    autoRetry: true
                });
            } else {
                showToast(error.message || 'Error activando trial', 'error');
            }

            // Analytics
            if (typeof gtag !== 'undefined') {
                gtag('event', 'trial_activation_error', {
                    'event_category': 'errors',
                    'event_label': 'trial_activation',
                    'error_type': window.ErrorRecovery?.getErrorType(error) || 'unknown'
                });
            }
        }
    };

    /**
     * Launch confetti celebration animation
     *
     * Creates 50 colored particles that fall from top of screen
     * Respects prefers-reduced-motion accessibility setting
     */
    function launchConfetti() {
        // Respetar preferencias de accesibilidad
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReducedMotion) {
            return;  // No mostrar confetti si usuario prefiere menos animaciones
        }

        // Get colors from CSS variables for consistency
        const rootStyles = getComputedStyle(document.documentElement);
        const colors = [
            rootStyles.getPropertyValue('--color-accent').trim() || '#0d9488',
            rootStyles.getPropertyValue('--color-success').trim() || '#10b981',
            rootStyles.getPropertyValue('--color-warning').trim() || '#f59e0b',
            rootStyles.getPropertyValue('--color-info').trim() || '#3b82f6'
        ];

        // BUG FIX #13: Guardar referencia para cleanup
        window.activeConfetti = [];

        // BUG FIX #26: Reduce count on mobile devices
        const confettiCount = window.innerWidth < 768 ? 30 : 50;

        for (let i = 0; i < confettiCount; i++) {
            setTimeout(() => {
                const confettiEl = createConfetti(colors[Math.floor(Math.random() * colors.length)]);
                window.activeConfetti.push(confettiEl);
            }, i * 30);
        }

        // BUG FIX #13: Listener para limpiar confetti si navega antes de 5s
        const cleanupConfetti = () => {
            if (window.activeConfetti && window.activeConfetti.length > 0) {
                window.activeConfetti.forEach(el => {
                    if (el && el.parentNode) {
                        el.remove();
                    }
                });
                window.activeConfetti = [];
            }
        };

        window.addEventListener('beforeunload', cleanupConfetti);

        // Limpiar listener después de 5s
        setTimeout(() => {
            window.removeEventListener('beforeunload', cleanupConfetti);
            window.activeConfetti = [];
        }, 5000);
    }

    /**
     * Create a single confetti particle element
     *
     * @param {string} color - CSS color for the particle
     * @returns {HTMLElement} Confetti element
     */
    function createConfetti(color) {
        const confetti = document.createElement('div');
        confetti.style.position = 'fixed';
        confetti.style.left = Math.random() * 100 + '%';
        confetti.style.top = '-10px';
        confetti.style.width = (Math.random() * 10 + 5) + 'px';
        confetti.style.height = confetti.style.width;
        confetti.style.background = color;
        confetti.style.borderRadius = '50%';
        confetti.style.pointerEvents = 'none';
        confetti.style.zIndex = '9999';
        confetti.style.animation = `fall ${Math.random() * 3 + 2}s linear`;

        document.body.appendChild(confetti);

        // Auto-remove after animation completes
        setTimeout(() => {
            if (confetti && confetti.parentNode) {
                confetti.remove();
            }
        }, 5000);

        return confetti; // Return for cleanup tracking
    }

    // Export to window for onclick handlers in template
    window.launchConfetti = launchConfetti;
})();
