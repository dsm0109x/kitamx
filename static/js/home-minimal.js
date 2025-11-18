/**
 * Home Page Interactions - BRUTALIST MINIMAL
 * Solo funcionalidad esencial, sin efectos decorativos
 *
 * Incluye:
 * - Timeline navigation (funcional)
 * - FAQ accordion (funcional)
 *
 * NO incluye:
 * - Parallax (eliminado)
 * - Animate-on-scroll (eliminado)
 * - Navbar scroll effects (eliminado)
 * - Pulse animations (eliminado)
 * - Smooth scroll (eliminado - usar nativo del navegador)
 *
 * @version 3.0 - Brutalist Minimal
 */

'use strict';

const KitaHome = (function() {

    /**
     * Handle timeline step click with animations
     * @param {Event} event - Click event
     */
    function handleTimelineClick(event) {
        const step = event.currentTarget;
        const stepNum = parseInt(step.dataset.step);

        if (!stepNum) return;

        // Update progress bar
        updateProgressBar(stepNum);

        // Deactivate all steps with fade
        document.querySelectorAll('.timeline-step').forEach(s => {
            s.classList.remove('active');
            s.setAttribute('aria-selected', 'false');
        });

        // Hide current panel (sin delay para evitar saltos)
        const currentPanel = document.querySelector('.timeline-detail.active');
        if (currentPanel) {
            currentPanel.classList.remove('active');
        }

        // Activate current step
        step.classList.add('active');
        step.setAttribute('aria-selected', 'true');

        const numberEl = step.querySelector('.timeline-number');
        if (numberEl) {
            numberEl.style.animation = 'none';
            setTimeout(() => {
                numberEl.style.animation = 'number-rotate 0.4s ease-out';
            }, 10);
        }

        // Show detail panel immediately
        const detailEl = document.getElementById(`detail-${stepNum}`);
        if (detailEl) {
            detailEl.classList.add('active');
            // Stagger example fields
            setTimeout(() => {
                staggerExampleFields(detailEl);
            }, 100);
        }
    }

    /**
     * Update progress bar
     */
    function updateProgressBar(stepNum) {
        const progressBar = document.getElementById('timelineProgressBar');
        const progressText = document.getElementById('currentTimelineStep');

        if (progressBar) {
            const percentage = (stepNum / 3) * 100;
            progressBar.style.width = percentage + '%';
        }

        if (progressText) {
            progressText.textContent = stepNum;
        }
    }

    /**
     * Stagger animation for example fields
     */
    function staggerExampleFields(panel) {
        const fields = panel.querySelectorAll('.example-field');

        fields.forEach((field, index) => {
            field.style.opacity = '0';
            field.style.transform = 'translateY(10px)';

            setTimeout(() => {
                field.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                field.style.opacity = '1';
                field.style.transform = 'translateY(0)';
            }, index * 80);
        });
    }

    /**
     * Initialize timeline interaction
     */
    function initTimeline() {
        const steps = document.querySelectorAll('.timeline-step');
        if (!steps.length) return;

        // Attach event listeners
        steps.forEach(step => {
            step.addEventListener('click', handleTimelineClick);
        });

        // Activate first step by default
        const firstStep = steps[0];
        if (firstStep) {
            const stepNum = firstStep.dataset.step;
            firstStep.classList.add('active');
            firstStep.setAttribute('aria-selected', 'true');

            const detailEl = document.getElementById(`detail-${stepNum}`);
            if (detailEl) {
                detailEl.classList.add('active');
            }
        }
    }

    /**
     * Toggle FAQ item
     * @param {HTMLElement} questionButton - The FAQ question button
     */
    function toggleFAQ(questionButton) {
        const faqNum = questionButton.dataset.faqNum;
        if (!faqNum) return;

        const answer = document.getElementById(`faq-${faqNum}`);
        const faqItem = questionButton.closest('.faq-item');
        if (!answer) return;

        const isExpanded = questionButton.getAttribute('aria-expanded') === 'true';

        // Toggle active state
        questionButton.classList.toggle('active');
        answer.classList.toggle('active');
        questionButton.setAttribute('aria-expanded', String(!isExpanded));

        if (faqItem) {
            faqItem.classList.toggle('active');
        }
    }

    /**
     * Initialize FAQ interaction
     */
    function initFAQ() {
        const faqButtons = document.querySelectorAll('.faq-question');

        faqButtons.forEach((button) => {
            const controls = button.getAttribute('aria-controls');
            if (controls) {
                const faqNum = controls.replace('faq-', '');
                button.dataset.faqNum = faqNum;
            }

            button.addEventListener('click', () => toggleFAQ(button));
        });
    }

    /**
     * Initialize all home page interactions
     * BRUTALIST VERSION - Only essentials
     */
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initTimeline();
            initFAQ();

            console.log('[Kita Home] Brutalist minimal initialized');
        } catch (error) {
            console.error('[Kita Home] Error:', error);
        }
    }

    // Public API
    return {
        init: init
    };
})();

// Auto-initialize
KitaHome.init();
