/**
 * ERROR RECOVERY SYSTEM - ENHANCED
 * ==================================
 *
 * Sistema global de manejo de errores con recovery automático.
 *
 * Features:
 * - ✅ Detección de offline/online
 * - ✅ Auto-retry con exponential backoff
 * - ✅ Queue de requests fallidos
 * - ✅ Visual feedback claro
 * - ✅ Recovery actions contextuales
 * - ✅ Analytics tracking
 *
 * @version 1.0
 * @created 2025-10-20
 */

'use strict';

(function() {
    // Debug mode (only with ?debug=1 in URL)
    const DEBUG = new URLSearchParams(window.location.search).get('debug') === '1';
    const log = DEBUG ? console.log.bind(console) : () => {};

    // ========================================
    // 1. CONNECTION MONITOR
    // ========================================

    class ConnectionMonitor {
        constructor() {
            this.isOnline = navigator.onLine;
            this.listeners = [];
            this.init();
        }

        init() {
            // Listen to online/offline events
            window.addEventListener('online', () => this.handleOnline());
            window.addEventListener('offline', () => this.handleOffline());

            log(`🌐 Connection Monitor initialized. Status: ${this.isOnline ? 'ONLINE' : 'OFFLINE'}`);
        }

        handleOnline() {
            log('✅ Connection restored');
            this.isOnline = true;

            // Show toast
            if (typeof showToast !== 'undefined') {
                showToast('Conexión restaurada', 'success');
            }

            // Notify listeners
            this.listeners.forEach(callback => callback('online'));

            // Try to retry failed requests
            if (window.requestQueue) {
                window.requestQueue.retryAll();
            }

            // Analytics
            this._trackEvent('connection_restored');
        }

        handleOffline() {
            log('❌ Connection lost');
            this.isOnline = false;

            // Show toast with action
            if (typeof showToast !== 'undefined') {
                showToast('Sin conexión a internet', 'warning');
            }

            // Hide any loading states
            if (typeof hideLoading !== 'undefined') {
                hideLoading();
            }

            // Notify listeners
            this.listeners.forEach(callback => callback('offline'));

            // Analytics
            this._trackEvent('connection_lost');
        }

        onStatusChange(callback) {
            this.listeners.push(callback);
        }

        _trackEvent(eventName) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'connection',
                    'event_label': 'network_status',
                });
            }
        }
    }

    // ========================================
    // 2. REQUEST QUEUE (Para retry)
    // ========================================

    class RequestQueue {
        constructor() {
            this.queue = [];
            this.maxRetries = 3;
            this.retryDelay = 1000; // 1 segundo inicial
        }

        add(requestData) {
            /**
             * Agregar request fallido a la queue
             *
             * @param {Object} requestData - Datos del request
             *   - url: string
             *   - method: string
             *   - body: FormData|Object
             *   - headers: Object
             *   - onSuccess: Function
             *   - onError: Function
             *   - context: string (para logging)
             */
            const queueItem = {
                ...requestData,
                retryCount: 0,
                addedAt: Date.now(),
                id: this._generateId(),
            };

            this.queue.push(queueItem);
            log(`📥 Request added to queue: ${queueItem.context || queueItem.url}`);

            return queueItem.id;
        }

        async retry(itemId) {
            const item = this.queue.find(i => i.id === itemId);
            if (!item) {
                console.warn(`⚠️ Request ${itemId} not found in queue`);
                return false;
            }

            item.retryCount++;

            log(`🔄 Retrying request (${item.retryCount}/${this.maxRetries}): ${item.context || item.url}`);

            // Show loading
            if (typeof showLoading !== 'undefined') {
                showLoading(`Reintentando... (${item.retryCount}/${this.maxRetries})`);
            }

            try {
                const response = await fetch(item.url, {
                    method: item.method,
                    body: item.body,
                    headers: item.headers,
                });

                if (response.ok) {
                    log(`✅ Retry successful: ${item.context || item.url}`);

                    // Remove from queue
                    this.queue = this.queue.filter(i => i.id !== itemId);

                    // Hide loading
                    if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    // Show success toast
                    if (typeof showToast !== 'undefined') {
                        showToast('Operación completada exitosamente', 'success');
                    }

                    // Call success callback
                    if (item.onSuccess) {
                        const data = await response.json();
                        item.onSuccess(data);
                    }

                    // Analytics
                    this._trackRetry(item, 'success');

                    return true;
                } else {
                    throw new Error(`HTTP ${response.status}`);
                }

            } catch (error) {
                console.error(`❌ Retry failed (${item.retryCount}/${this.maxRetries}):`, error);

                if (item.retryCount >= this.maxRetries) {
                    // Max retries reached
                    console.error(`🚫 Max retries reached for: ${item.context || item.url}`);

                    // Remove from queue
                    this.queue = this.queue.filter(i => i.id !== itemId);

                    // Hide loading
                    if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    // Show error toast
                    if (typeof showToast !== 'undefined') {
                        showToast('No se pudo completar la operación. Intenta más tarde.', 'error');
                    }

                    // Call error callback
                    if (item.onError) {
                        item.onError(error);
                    }

                    // Analytics
                    this._trackRetry(item, 'failed');

                    return false;
                } else {
                    // Schedule next retry with exponential backoff
                    const delay = this.retryDelay * Math.pow(2, item.retryCount - 1);
                    log(`⏱️ Scheduling retry in ${delay}ms`);

                    if (typeof hideLoading !== 'undefined') {
                        hideLoading();
                    }

                    if (typeof showToast !== 'undefined') {
                        showToast(`Reintentando en ${Math.round(delay / 1000)} segundos...`, 'info');
                    }

                    setTimeout(() => this.retry(itemId), delay);

                    return false;
                }
            }
        }

        async retryAll() {
            log(`🔄 Retrying all queued requests (${this.queue.length})`);

            // Copy queue to avoid modification during iteration
            const itemsToRetry = [...this.queue];

            for (const item of itemsToRetry) {
                await this.retry(item.id);
                // Small delay between retries
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        remove(itemId) {
            this.queue = this.queue.filter(i => i.id !== itemId);
            log(`🗑️ Request removed from queue: ${itemId}`);
        }

        clear() {
            this.queue = [];
            log('🗑️ Queue cleared');
        }

        getStatus() {
            return {
                count: this.queue.length,
                items: this.queue.map(i => ({
                    id: i.id,
                    context: i.context,
                    url: i.url,
                    retryCount: i.retryCount,
                    addedAt: i.addedAt,
                }))
            };
        }

        _generateId() {
            return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }

        _trackRetry(item, status) {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'request_retry', {
                    'event_category': 'error_recovery',
                    'event_label': item.context || 'unknown',
                    'retry_count': item.retryCount,
                    'status': status,
                });
            }
        }
    }

    // ========================================
    // 3. ERROR HANDLER (Helper functions)
    // ========================================

    window.ErrorRecovery = {
        /**
         * Handle fetch error with automatic recovery
         *
         * @param {Error} error - Error object
         * @param {Object} requestData - Original request data
         * @param {Object} options - Options
         *   - showToast: boolean (default true)
         *   - autoRetry: boolean (default true)
         *   - context: string (for logging)
         */
        handleError(error, requestData = null, options = {}) {
            const {
                showToast: shouldShowToast = true,
                autoRetry = true,
                context = 'unknown'
            } = options;

            console.error(`❌ Error in ${context}:`, error);

            // Determine error type
            const errorType = this.getErrorType(error);

            // BUG FIX #82: Use error.message if available (server-provided message is more specific)
            let errorMessage = error.message || this.getErrorMessage(errorType);

            // If error message is too generic, enhance with type-specific fallback
            if (errorMessage === error.constructor.name || errorMessage === 'Error') {
                errorMessage = this.getErrorMessage(errorType);
            }

            // Hide loading if active
            if (typeof hideLoading !== 'undefined') {
                hideLoading();
            }

            // Show toast if enabled
            if (shouldShowToast && typeof showToast !== 'undefined') {
                showToast(errorMessage, 'error');
            }

            // Handle specific error types
            if (errorType === 'network' && !window.connectionMonitor.isOnline) {
                // Offline - add to queue for retry when online
                if (autoRetry && requestData) {
                    window.requestQueue.add({
                        ...requestData,
                        context,
                    });

                    if (typeof showToast !== 'undefined') {
                        showToast('Se reintentará cuando recuperes la conexión', 'info');
                    }
                }
            } else if (errorType === 'timeout') {
                // Timeout - offer manual retry
                if (requestData) {
                    this.showRetryButton(requestData, context);
                }
            }

            // Analytics
            this.trackError(errorType, context);

            return {
                errorType,
                errorMessage,
                handled: true,
            };
        },

        /**
         * Get error type from error object
         */
        getErrorType(error) {
            const errorString = error.toString().toLowerCase();

            if (!navigator.onLine || errorString.includes('network') || errorString.includes('failed to fetch')) {
                return 'network';
            } else if (errorString.includes('timeout')) {
                return 'timeout';
            } else if (errorString.includes('abort')) {
                return 'aborted';
            } else if (errorString.includes('json') || errorString.includes('parse')) {
                return 'parse_error';
            } else {
                return 'unknown';
            }
        },

        /**
         * Get user-friendly error message
         */
        getErrorMessage(errorType) {
            const messages = {
                'network': 'Error de conexión. Verifica tu internet.',
                'timeout': 'La conexión está lenta. ¿Reintentar?',
                'aborted': 'Operación cancelada',
                'parse_error': 'Error procesando la respuesta del servidor',
                'unknown': 'Error inesperado. Por favor intenta de nuevo.',
            };

            return messages[errorType] || messages.unknown;
        },

        /**
         * Show retry button in UI
         */
        showRetryButton(requestData, context) {
            // Create retry button element
            const retryBtn = document.createElement('button');
            retryBtn.className = 'btn btn-outline-primary btn-sm mt-3';
            retryBtn.innerHTML = `
                <span class="iconoir-refresh me-2"></span>
                Reintentar
            `;

            retryBtn.onclick = async () => {
                retryBtn.disabled = true;
                retryBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Reintentando...';

                const itemId = window.requestQueue.add({
                    ...requestData,
                    context,
                });

                const success = await window.requestQueue.retry(itemId);

                if (!success) {
                    retryBtn.disabled = false;
                    retryBtn.innerHTML = `
                        <span class="iconoir-refresh me-2"></span>
                        Reintentar
                    `;
                } else {
                    retryBtn.remove();
                }
            };

            // Find form or container to insert button
            const form = document.querySelector('.auth-form') || document.querySelector('form');
            if (form) {
                // Remove existing retry button if any
                const existing = form.querySelector('.error-retry-btn');
                if (existing) existing.remove();

                retryBtn.classList.add('error-retry-btn', 'w-100');
                form.appendChild(retryBtn);
            }
        },

        /**
         * Track error for analytics
         */
        trackError(errorType, context) {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'error_occurred', {
                    'event_category': 'errors',
                    'event_label': context,
                    'error_type': errorType,
                });
            }
        }
    };

    // ========================================
    // 4. INITIALIZE
    // ========================================

    // Initialize when DOM is ready
    function init() {
        log('🚀 Error Recovery System initializing...');

        // Create global instances
        window.connectionMonitor = new ConnectionMonitor();
        window.requestQueue = new RequestQueue();

        // Show connection status on load if offline
        if (!navigator.onLine) {
            console.warn('⚠️ Starting in OFFLINE mode');
            if (typeof showToast !== 'undefined') {
                showToast('Sin conexión a internet', 'warning');
            }
        }

        log('✅ Error Recovery System ready');
    }

    // Auto-initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
