/**
 * COMPARISON SECTION ANIMATIONS
 * Barras de tiempo, counters, highlights
 */

'use strict';

const ComparisonAnimations = (function() {

    // ========================================
    // TIME BARS ANIMATION
    // ========================================
    function initTimeBars() {
        const bars = document.querySelectorAll('.time-bar-fill, .time-bar-fill-success');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const bar = entry.target;
                    const duration = parseFloat(bar.dataset.duration) || 15;

                    // Calculate width percentage (15 min = 100%, 0.5 min = 3%)
                    const maxDuration = 15;
                    const widthPercent = (duration / maxDuration) * 100;

                    setTimeout(() => {
                        bar.style.width = widthPercent + '%';
                    }, 300);

                    observer.unobserve(bar);
                }
            });
        }, {
            threshold: 0.5
        });

        bars.forEach(bar => observer.observe(bar));
    }

    // ========================================
    // NUMBER COUNT UP
    // ========================================
    function animateNumber(element, targetText) {
        const target = parseFloat(targetText);
        if (isNaN(target)) return;

        const duration = 1500;
        const start = 0;
        const increment = target / (duration / 16);
        let current = start;

        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                element.textContent = targetText;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current);
            }
        }, 16);
    }

    function initNumberCounters() {
        const numbers = document.querySelectorAll('.time-number');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const number = entry.target;
                    const targetText = number.textContent;

                    number.textContent = '0';

                    setTimeout(() => {
                        animateNumber(number, targetText);
                    }, 200);

                    observer.unobserve(number);
                }
            });
        }, {
            threshold: 0.5
        });

        numbers.forEach(num => observer.observe(num));
    }

    // ========================================
    // CARD STAGGER REVEAL
    // ========================================
    function initCardStagger() {
        const problemCard = document.querySelector('.comparison-card-problem');
        const divider = document.querySelector('.comparison-divider');
        const solutionCard = document.querySelector('.comparison-card-solution');

        const elements = [problemCard, divider, solutionCard].filter(el => el);

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const index = elements.indexOf(entry.target);

                    entry.target.style.opacity = '0';
                    entry.target.style.transform = 'translateY(20px)';

                    setTimeout(() => {
                        entry.target.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * 200);

                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.2
        });

        elements.forEach(el => observer.observe(el));
    }

    // ========================================
    // MAGIC CARD PULSE
    // ========================================
    function initMagicPulse() {
        const magicIcon = document.querySelector('.magic-card .iconoir-magic-wand');

        if (magicIcon) {
            magicIcon.style.animation = 'magic-pulse 3s ease-in-out infinite';
        }
    }

    // ========================================
    // INITIALIZE
    // ========================================
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initTimeBars();
            initNumberCounters();
            initCardStagger();
            initMagicPulse();

            console.log('✨ Comparison animations initialized');
        } catch (error) {
            console.error('[Comparison Animations] Error:', error);
        }
    }

    return { init };
})();

// Auto-initialize
ComparisonAnimations.init();

// Add CSS animations
if (!document.getElementById('comparison-animations-css')) {
    const style = document.createElement('style');
    style.id = 'comparison-animations-css';
    style.textContent = `
        @keyframes magic-pulse {
            0%, 100% {
                transform: scale(1) rotate(0deg);
            }
            50% {
                transform: scale(1.1) rotate(5deg);
            }
        }
    `;
    document.head.appendChild(style);
}
