/**
 * Home Page Interactions
 *
 * Handles timeline navigation, FAQ accordion, smooth scrolling, and hero image fallback.
 * Uses modern ES6+ patterns with proper error handling and accessibility support.
 *
 * @version 2.0
 * @author Kita Team
 */

'use strict';

const KitaHome = (function() {
    // Configuration constants
    const CONFIG = {
        TIMELINE_OFFSET: 100,
        SCROLL_OFFSET: 80,
        LOADING_ANIMATION_DURATION: 400
    };

    /**
     * Initialize hero image error handling
     * Provides fallback if external image fails to load
     */
    function initHeroImage() {
        const heroImg = document.querySelector('.hero-screenshot');
        if (!heroImg) return;

        heroImg.addEventListener('error', function() {
            console.warn('[Kita Home] Hero image failed to load, using fallback');
            this.src = '/static/images/placeholder-dashboard.jpg';
            this.alt = 'Dashboard preview placeholder';
        });
    }

    /**
     * Handle timeline step click
     * @param {Event} event - Click event
     */
    function handleTimelineClick(event) {
        const step = event.currentTarget;
        const stepNum = step.dataset.step;

        if (!stepNum) {
            console.error('[Kita Home] Timeline step missing data-step attribute');
            return;
        }

        // Show loading state
        if (typeof window.showLoading === 'function') {
            window.showLoading(`Cargando paso ${stepNum}...`);
        }

        // Deactivate all steps
        document.querySelectorAll('.timeline-step').forEach(s => {
            s.classList.remove('active');
            s.setAttribute('aria-selected', 'false');
        });

        document.querySelectorAll('.timeline-number').forEach(n => {
            n.classList.remove('pulse');
        });

        document.querySelectorAll('.timeline-detail').forEach(d => {
            d.classList.remove('active');
        });

        // Activate current step
        step.classList.add('active');
        step.setAttribute('aria-selected', 'true');

        const numberEl = step.querySelector('.timeline-number');
        if (numberEl) {
            numberEl.classList.add('pulse');
        }

        // Show detail panel
        const detailEl = document.getElementById(`detail-${stepNum}`);
        if (detailEl) {
            detailEl.classList.add('active');

            // Smooth scroll to detail
            const elementPosition = detailEl.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - CONFIG.TIMELINE_OFFSET;

            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }

        // Hide loading after animation
        setTimeout(() => {
            if (typeof window.hideLoading === 'function') {
                window.hideLoading();
            }
        }, CONFIG.LOADING_ANIMATION_DURATION);
    }

    /**
     * Initialize timeline interaction
     * Sets up click handlers and activates first step by default
     */
    function initTimeline() {
        const steps = document.querySelectorAll('.timeline-step');
        if (!steps.length) return;

        // Attach event listeners
        steps.forEach(step => {
            step.addEventListener('click', handleTimelineClick);
        });

        // Activate first step visually without scrolling
        const firstStep = steps[0];
        if (firstStep) {
            const stepNum = firstStep.dataset.step;

            // Activate step visually (no scroll)
            firstStep.classList.add('active');
            firstStep.setAttribute('aria-selected', 'true');

            const numberEl = firstStep.querySelector('.timeline-number');
            if (numberEl) {
                numberEl.classList.add('pulse');
            }

            // Show detail panel
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

        if (!faqNum) {
            console.error('[Kita Home] FAQ button missing data-faq-num attribute');
            return;
        }

        const answer = document.getElementById(`faq-${faqNum}`);
        const faqItem = questionButton.closest('.faq-item');

        if (!answer) {
            console.error(`[Kita Home] FAQ answer #faq-${faqNum} not found`);
            return;
        }

        const isExpanded = questionButton.getAttribute('aria-expanded') === 'true';

        // Toggle active state
        questionButton.classList.toggle('active');
        answer.classList.toggle('active');
        questionButton.setAttribute('aria-expanded', String(!isExpanded));

        // Toggle faq-item active state for border color
        if (faqItem) {
            faqItem.classList.toggle('active');
        }
    }

    /**
     * Initialize FAQ interaction
     * Attaches event listeners to all FAQ buttons
     */
    function initFAQ() {
        const faqButtons = document.querySelectorAll('.faq-question');

        faqButtons.forEach((button) => {
            // Extract FAQ number from aria-controls attribute
            const controls = button.getAttribute('aria-controls');
            if (controls) {
                const faqNum = controls.replace('faq-', '');
                button.dataset.faqNum = faqNum;
            }

            // Attach click handler
            button.addEventListener('click', () => toggleFAQ(button));
        });
    }

    /**
     * Initialize smooth scroll for anchor links
     * Handles all internal anchor navigation with offset
     */
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const href = this.getAttribute('href');

                // Ignore empty anchors
                if (href === '#') return;

                e.preventDefault();

                const target = document.querySelector(href);

                if (!target) {
                    console.warn(`[Kita Home] Anchor target not found: ${href}`);
                    return;
                }

                // Calculate position with offset
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - CONFIG.SCROLL_OFFSET;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            });
        });
    }

    /**
     * Initialize navbar scroll effect
     * Adds 'scrolled' class when user scrolls down
     */
    function initNavbarScroll() {
        const navbar = document.querySelector('.navbar.sticky-top');
        if (!navbar) return;

        let lastScroll = 0;

        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;

            if (currentScroll > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }

            lastScroll = currentScroll;
        });
    }

    /**
     * Initialize parallax effect for Mexican pattern sections
     * Creates subtle movement on scroll for depth
     */
    function initParallax() {
        // Check if user prefers reduced motion
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }

        const parallaxSections = document.querySelectorAll('[data-parallax]');
        if (!parallaxSections.length) return;

        let ticking = false;

        function updateParallax() {
            parallaxSections.forEach(section => {
                const rect = section.getBoundingClientRect();
                const scrolled = window.pageYOffset;

                // Only apply parallax if section is in viewport
                if (rect.top < window.innerHeight && rect.bottom > 0) {
                    const sectionTop = section.offsetTop;
                    const parallaxOffset = (scrolled - sectionTop) * 0.05; // 0.05 = ultra subtle (Apple way)

                    // Apply transform to ::before pseudo-element via CSS variable
                    section.style.setProperty('--parallax-offset', `${parallaxOffset}px`);

                    // Stars pattern uses even slower movement
                    if (section.classList.contains('section-pricing-stars')) {
                        const starsOffset = (scrolled - sectionTop) * 0.03; // Almost imperceptible
                        section.style.setProperty('--parallax-offset-stars', `${starsOffset}px`);
                    }
                }
            });

            ticking = false;
        }

        window.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(updateParallax);
                ticking = true;
            }
        });

        // Initial call
        updateParallax();
    }

    /**
     * Initialize staggered entrance animations (Apple-style)
     */
    function initEntranceAnimations() {
        const animatedElements = document.querySelectorAll('.animate-on-scroll');

        if (!animatedElements.length) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-entrance');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        animatedElements.forEach(el => observer.observe(el));
    }

    /**
     * Initialize all home page interactions
     * Main entry point - called on DOM ready
     */
    function init() {
        // Wait for DOM if not ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initHeroImage();
            initTimeline();
            initFAQ();
            initSmoothScroll();
            initNavbarScroll();
            initParallax();
            initEntranceAnimations();

            console.log('[Kita Home] Page initialized successfully with Apple Glass');
        } catch (error) {
            console.error('[Kita Home] Error initializing page:', error);

            // Send to Sentry if available
            if (typeof Sentry !== 'undefined') {
                Sentry.captureException(error);
            }
        }
    }

    // Public API
    return {
        init: init
    };
})();

// Auto-initialize
KitaHome.init();
