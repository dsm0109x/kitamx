/**
 * PRICING ANIMATIONS
 * Price counter, badge pulse, features stagger
 */

'use strict';

const PricingAnimations = (function() {

    // ========================================
    // PRICE COUNTER
    // ========================================
    function initPriceCounter() {
        const priceEl = document.querySelector('.price-number-huge');
        if (!priceEl) return;

        const target = parseInt(priceEl.dataset.price) || 299;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    let current = 0;
                    const duration = 2000;
                    const increment = target / (duration / 16);

                    const timer = setInterval(() => {
                        current += increment;
                        if (current >= target) {
                            priceEl.textContent = target;
                            clearInterval(timer);
                        } else {
                            priceEl.textContent = Math.floor(current);
                        }
                    }, 16);

                    observer.unobserve(priceEl);
                }
            });
        }, { threshold: 0.5 });

        observer.observe(priceEl);
    }

    // ========================================
    // FEATURES STAGGER
    // ========================================
    function initFeaturesStagger() {
        const features = document.querySelectorAll('.feature-item');
        if (!features.length) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    features.forEach((feature, index) => {
                        const delay = parseInt(feature.dataset.delay) || 0;

                        feature.style.opacity = '0';
                        feature.style.transform = 'translateX(-10px)';

                        setTimeout(() => {
                            feature.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
                            feature.style.opacity = '1';
                            feature.style.transform = 'translateX(0)';
                        }, delay);
                    });

                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.3 });

        if (features.length > 0) {
            observer.observe(features[0].parentElement);
        }
    }

    // ========================================
    // CARD SCALE IN
    // ========================================
    function initCardScaleIn() {
        const card = document.querySelector('.pricing-card-single');
        if (!card) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.95)';

                    setTimeout(() => {
                        card.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
                        card.style.opacity = '1';
                        card.style.transform = 'scale(1)';
                    }, 100);

                    observer.unobserve(card);
                }
            });
        }, { threshold: 0.2 });

        observer.observe(card);
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
            initPriceCounter();
            initFeaturesStagger();
            initCardScaleIn();

            console.log('✨ Pricing animations initialized');
        } catch (error) {
            console.error('[Pricing Animations] Error:', error);
        }
    }

    return { init };
})();

// Auto-initialize
PricingAnimations.init();
