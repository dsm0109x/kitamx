/**
 * LOADING PROGRESS SYSTEM - ENHANCED
 * ====================================
 *
 * Sistema de loading mejorado con estados de progreso y feedback visual.
 *
 * Features:
 * - ✅ Progress states con mensajes específicos
 * - ✅ Progress bar con percentage visual
 * - ✅ Auto-timeout configurable
 * - ✅ Smooth transitions
 * - ✅ Multiple loading contexts simultáneos
 *
 * @version 2.0
 * @created 2025-10-20
 */

'use strict';

(function() {
    // ========================================
    // LOADING PROGRESS CLASS
    // ========================================

    class LoadingProgress {
        constructor() {
            this.stages = [];
            this.currentStage = 0;
            this.isActive = false;
            this.timeout = null;
            this.maxTimeout = 30000; // 30 seconds default
        }

        /**
         * Start loading con stages de progreso
         *
         * @param {Array|String} stages - Array de mensajes o string único
         * @param {Object} options - Opciones
         *   - timeout: number (milliseconds)
         *   - onTimeout: function
         *   - onComplete: function
         *
         * @example
         * loading.start([
         *   'Validando datos...',
         *   'Enviando formulario...',
         *   'Procesando respuesta...'
         * ]);
         */
        start(stages, options = {}) {
            const {
                timeout = this.maxTimeout,
                onTimeout = null,
                onComplete = null
            } = options;

            // Convertir string a array
            if (typeof stages === 'string') {
                stages = [stages];
            }

            this.stages = stages;
            this.currentStage = 0;
            this.isActive = true;
            this.onComplete = onComplete;

            // Show visual elements
            this._show();
            this._updateMessage(this.stages[0]);
            this._updateProgress();

            // Set timeout
            if (this.timeout) {
                clearTimeout(this.timeout);
            }

            this.timeout = setTimeout(() => {
                this._handleTimeout(onTimeout);
            }, timeout);

            console.log(`⏳ Loading started: ${this.stages.length} stage(s)`);
        }

        /**
         * Avanzar al siguiente stage
         */
        nextStage() {
            if (!this.isActive) {
                console.warn('⚠️ Loading not active, ignoring nextStage()');
                return;
            }

            this.currentStage++;

            if (this.currentStage < this.stages.length) {
                this._updateMessage(this.stages[this.currentStage]);
                this._updateProgress();
                console.log(`➡️ Stage ${this.currentStage + 1}/${this.stages.length}: ${this.stages[this.currentStage]}`);
            } else {
                // All stages complete
                this.complete();
            }
        }

        /**
         * Completar loading exitosamente
         */
        complete() {
            if (!this.isActive) return;

            console.log('✅ Loading complete');

            // Clear timeout
            if (this.timeout) {
                clearTimeout(this.timeout);
                this.timeout = null;
            }

            // Hide visual elements
            this._hide();

            // Reset state
            this.isActive = false;
            this.currentStage = 0;

            // Call onComplete callback
            if (this.onComplete) {
                this.onComplete();
            }
        }

        /**
         * Cancelar loading
         */
        cancel() {
            if (!this.isActive) return;

            console.log('⏹️ Loading cancelled');

            // Clear timeout
            if (this.timeout) {
                clearTimeout(this.timeout);
                this.timeout = null;
            }

            // Hide visual elements
            this._hide();

            // Reset state
            this.isActive = false;
            this.currentStage = 0;
        }

        /**
         * Update message (mantener stage actual)
         */
        updateMessage(message) {
            if (!this.isActive) return;

            this._updateMessage(message);
            console.log(`📝 Message updated: ${message}`);
        }

        // ========================================
        // PRIVATE METHODS
        // ========================================

        _show() {
            const topbar = document.getElementById('loadingTopbar');
            const card = document.getElementById('loadingMessage');

            if (topbar) topbar.classList.add('active');
            if (card) card.classList.add('active');
        }

        _hide() {
            const topbar = document.getElementById('loadingTopbar');
            const card = document.getElementById('loadingMessage');

            if (topbar) topbar.classList.remove('active');
            if (card) card.classList.remove('active');
        }

        _updateMessage(message) {
            const textEl = document.getElementById('loadingText');
            if (!textEl) return;

            // Calculate progress percentage
            const progress = this.stages.length > 1
                ? Math.round(((this.currentStage + 1) / this.stages.length) * 100)
                : 0;

            // Update text with progress if multiple stages
            if (this.stages.length > 1) {
                textEl.textContent = `${message} (${progress}%)`;
            } else {
                textEl.textContent = message;
            }
        }

        _updateProgress() {
            const progressBar = document.querySelector('.loading-topbar-progress');
            if (!progressBar) return;

            // Calculate width percentage
            const widthPercent = this.stages.length > 1
                ? ((this.currentStage + 1) / this.stages.length) * 100
                : 100; // Full width if single stage

            progressBar.style.width = `${widthPercent}%`;
        }

        _handleTimeout(onTimeout) {
            console.warn('⏱️ Loading timeout reached');

            this._hide();
            this.isActive = false;

            if (onTimeout) {
                onTimeout();
            } else {
                // Default timeout behavior
                if (typeof showToast !== 'undefined') {
                    showToast('La operación está tardando más de lo esperado', 'warning');
                }
            }
        }
    }

    // ========================================
    // GLOBAL API (Backward compatible)
    // ========================================

    // Create global instance
    window.loadingProgress = new LoadingProgress();

    // Simple API (backward compatible)
    window.showLoading = function(message = 'Cargando...', timeout = 30000) {
        window.loadingProgress.start([message], { timeout });
    };

    window.hideLoading = function() {
        window.loadingProgress.complete();
    };

    // Advanced API
    window.loading = {
        /**
         * Start multi-stage loading
         *
         * @param {Array} stages - Array de mensajes
         * @param {Object} options - Opciones
         */
        start(stages, options = {}) {
            window.loadingProgress.start(stages, options);
        },

        /**
         * Advance to next stage
         */
        next() {
            window.loadingProgress.nextStage();
        },

        /**
         * Complete loading
         */
        done() {
            window.loadingProgress.complete();
        },

        /**
         * Cancel loading
         */
        cancel() {
            window.loadingProgress.cancel();
        },

        /**
         * Update current message
         */
        update(message) {
            window.loadingProgress.updateMessage(message);
        },

        /**
         * Check if loading is active
         */
        isActive() {
            return window.loadingProgress.isActive;
        }
    };

    // Loading Progress System initialized silently

})();
