/**
 * KITA HERO MICRO-ANIMATIONS
 * Premium subtle animations for landing hero
 *
 * Includes:
 * 1. Fade-in Stagger
 * 2. Number Counter
 * 3. Magnetic Button
 * 4. 3D Card Tilt
 * 5. Icon Pulse
 * 6. Underline Draw
 * 7. Arrow Bounce
 * 8. Button Ripple
 * 9. Live Pulse Dot
 * 10. Hero Reveal
 *
 * @version 1.0 - Brutalist Premium
 */

'use strict';

const KitaHeroAnimations = (function() {

    // ========================================
    // 1. FADE-IN STAGGER
    // ========================================
    function initFadeInStagger() {
        const elements = document.querySelectorAll('.animate-fade-in, .animate-fade-in-up');

        elements.forEach(el => {
            const delay = parseInt(el.dataset.delay) || 0;

            setTimeout(() => {
                el.style.opacity = '0';
                el.style.transform = el.classList.contains('animate-fade-in-up')
                    ? 'translateY(20px)'
                    : 'translateY(0)';
                el.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';

                // Trigger animation
                requestAnimationFrame(() => {
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0)';
                });
            }, delay);
        });
    }

    // ========================================
    // 2. NUMBER COUNTER
    // ========================================
    function animateCounter(element) {
        const target = parseInt(element.dataset.target);
        const duration = parseInt(element.dataset.duration) || 2000;
        const start = 0;
        const increment = target / (duration / 16); // 60fps
        let current = start;

        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                element.textContent = target.toLocaleString('es-MX');
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current).toLocaleString('es-MX');
            }
        }, 16);
    }

    function initNumberCounters() {
        const counters = document.querySelectorAll('.number-counter');

        // Start counters after hero is visible
        setTimeout(() => {
            counters.forEach(counter => {
                animateCounter(counter);
            });
        }, 600); // After fade-in stagger completes
    }

    // ========================================
    // 3. MAGNETIC BUTTON
    // ========================================
    function initMagneticButton() {
        // Only on desktop
        if (window.innerWidth < 1024) return;

        const button = document.querySelector('.btn-magnetic');
        if (!button) return;

        button.addEventListener('mouseenter', () => {
            button.style.transition = 'transform 0.3s cubic-bezier(0.23, 1, 0.32, 1)';
        });

        button.addEventListener('mousemove', (e) => {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            const moveX = x * 0.3; // 30% of distance
            const moveY = y * 0.3;

            button.style.transform = `translate(${moveX}px, ${moveY}px) scale(1.02)`;
        });

        button.addEventListener('mouseleave', () => {
            button.style.transform = 'translate(0, 0) scale(1)';
        });
    }

    // ========================================
    // 4. 3D CARD TILT
    // ========================================
    function init3DCardTilt() {
        // Only on desktop
        if (window.innerWidth < 768) return;

        const card = document.getElementById('heroStatsCard');
        if (!card) return;

        card.addEventListener('mouseenter', () => {
            card.style.transition = 'none';
        });

        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -5; // Max 5 degrees
            const rotateY = ((x - centerX) / centerX) * 5;

            card.style.transform = `
                perspective(1000px)
                rotateX(${rotateX}deg)
                rotateY(${rotateY}deg)
                scale3d(1.02, 1.02, 1.02)
            `;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transition = 'transform 0.5s cubic-bezier(0.23, 1, 0.32, 1)';
            card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1, 1, 1)';
        });
    }

    // ========================================
    // 5. ICON PULSE
    // ========================================
    function initIconPulse() {
        const icons = document.querySelectorAll('.icon-pulse');

        icons.forEach(icon => {
            const delay = parseInt(icon.dataset.pulseDelay) || 0;

            icon.style.animation = `icon-pulse-subtle 3s ease-in-out ${delay}ms infinite`;
        });
    }

    // ========================================
    // 6. UNDERLINE DRAW (CSS handled, no JS needed)
    // ========================================

    // ========================================
    // 7. ARROW BOUNCE
    // ========================================
    function initArrowBounce() {
        const links = document.querySelectorAll('.hero-link-underline');

        links.forEach(link => {
            link.addEventListener('mouseenter', () => {
                const arrow = link.querySelector('.arrow-bounce');
                if (arrow) {
                    arrow.style.animation = 'arrow-bounce 0.6s ease-in-out';
                }
            });

            link.addEventListener('mouseleave', () => {
                const arrow = link.querySelector('.arrow-bounce');
                if (arrow) {
                    arrow.style.animation = '';
                }
            });
        });
    }

    // ========================================
    // 8. BUTTON RIPPLE
    // ========================================
    function initButtonRipple() {
        const buttons = document.querySelectorAll('.btn-ripple');

        buttons.forEach(button => {
            button.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;

                ripple.className = 'ripple-effect';
                ripple.style.cssText = `
                    position: absolute;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    background: rgba(255, 255, 255, 0.4);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: ripple-animation 0.6s ease-out;
                    pointer-events: none;
                `;

                // Ensure button has position relative
                this.style.position = 'relative';
                this.style.overflow = 'hidden';

                this.appendChild(ripple);

                ripple.addEventListener('animationend', () => {
                    ripple.remove();
                });
            });
        });
    }

    // ========================================
    // 9. LIVE PULSE DOT (CSS handled)
    // ========================================

    // ========================================
    // 10. HERO REVEAL (On load)
    // ========================================
    function initHeroReveal() {
        const hero = document.querySelector('.hero-brutalist-premium');
        if (!hero) return;

        hero.style.opacity = '0';
        hero.style.transform = 'translateY(20px)';

        setTimeout(() => {
            hero.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
            hero.style.opacity = '1';
            hero.style.transform = 'translateY(0)';
        }, 100);
    }

    // ========================================
    // INITIALIZE ALL
    // ========================================
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initHeroReveal();
            initFadeInStagger();
            initNumberCounters();
            initMagneticButton();
            init3DCardTilt();
            initIconPulse();
            initArrowBounce();
            initButtonRipple();

            console.log('✨ Hero micro-animations initialized (10/10)');
        } catch (error) {
            console.error('[Hero Animations] Error:', error);
        }
    }

    // Public API
    return {
        init: init
    };
})();

// Auto-initialize
KitaHeroAnimations.init();

// Add CSS animations
if (!document.getElementById('hero-animations-css')) {
    const style = document.createElement('style');
    style.id = 'hero-animations-css';
    style.textContent = `
        /* Icon pulse subtle */
        @keyframes icon-pulse-subtle {
            0%, 100% {
                transform: scale(1);
                opacity: 1;
            }
            50% {
                transform: scale(1.1);
                opacity: 0.85;
            }
        }

        /* Arrow bounce */
        @keyframes arrow-bounce {
            0%, 100% {
                transform: translateX(0);
            }
            50% {
                transform: translateX(6px);
            }
        }

        /* Ripple animation */
        @keyframes ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }

        /* Pulse dot */
        @keyframes pulse-dot {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.4;
                transform: scale(1.3);
            }
        }

        .pulse-dot {
            animation: pulse-dot 2s ease-in-out infinite;
        }
    `;
    document.head.appendChild(style);
}
