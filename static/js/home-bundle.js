/**
 * KITA HOME BUNDLE - All-in-One
 * Combines: hero-animations + comparison-animations + pricing-animations + home-minimal + roi-calculator + video-modal
 *
 * @version 5.5 - OPTIMIZED: Inline JS moved, VideoModal added, Debug cleaned
 * Features: Event delegation, analytics tracking, URL hash persistence, completed states, video modal
 * Loading: TODOS los botones (.btn-hero-primary, .btn-accent, .btn-primary, .btn-outline-secondary)
 * Effects: Magnetic (desktop), NO ripple (eliminado)
 * Security: CSP-compliant (no inline handlers), improved accessibility
 * Debug: Only with ?debug=1 URL parameter (console clean by default)
 * @size ~48KB
 */

'use strict';

// Conditional logger (only with ?debug=1 in URL)
const DEBUG = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('debug') === '1';
const log = DEBUG ? console.log.bind(console) : () => {};
const warn = DEBUG ? console.warn.bind(console) : () => {};
const error = console.error.bind(console); // Always log errors

// ========================================
// 0. NAVBAR STICKY MODULE
// ========================================
const NavbarSticky = (function() {
    function init() {
        const navbar = document.querySelector('.navbar-brutalist');
        if (!navbar) {
            warn('⚠️ Navbar no encontrado');
            return;
        }

        let lastScroll = 0;
        let ticking = false;

        window.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(() => {
                    const currentScroll = window.pageYOffset;

                    if (currentScroll > 50) {  // Reducido de 100 a 50px para que se vea antes
                        navbar.classList.add('navbar-scrolled');
                        log('📍 Navbar scrolled - shadow ON');
                    } else {
                        navbar.classList.remove('navbar-scrolled');
                        log('📍 Navbar top - shadow OFF');
                    }

                    lastScroll = currentScroll;
                    ticking = false;
                });

                ticking = true;
            }
        });
    }

    return { init };
})();

// ========================================
// 1. HERO ANIMATIONS MODULE
// ========================================
const KitaHeroAnimations = (function() {
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

                requestAnimationFrame(() => {
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0)';
                });
            }, delay);
        });
    }

    function initMagneticButton() {
        if (window.innerWidth < 1024) return;

        const buttons = document.querySelectorAll('.btn-magnetic');
        buttons.forEach(button => {
            button.addEventListener('mouseenter', () => {
                button.style.transition = 'transform 0.3s cubic-bezier(0.23, 1, 0.32, 1)';
            });

            button.addEventListener('mousemove', (e) => {
                const rect = button.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                const moveX = x * 0.3;
                const moveY = y * 0.3;
                button.style.transform = `translate(${moveX}px, ${moveY}px) scale(1.02)`;
            });

            button.addEventListener('mouseleave', () => {
                button.style.transform = 'translate(0, 0) scale(1)';
            });
        });
    }

    function initIconPulse() {
        const icons = document.querySelectorAll('.icon-pulse');
        icons.forEach(icon => {
            const delay = parseInt(icon.dataset.pulseDelay) || 0;
            icon.style.animation = `icon-pulse-subtle 3s ease-in-out ${delay}ms infinite`;
        });
    }

    function initArrowBounce() {
        const links = document.querySelectorAll('.hero-link-underline');
        links.forEach(link => {
            link.addEventListener('mouseenter', () => {
                const arrow = link.querySelector('.arrow-bounce');
                if (arrow) arrow.style.animation = 'arrow-bounce 0.6s ease-in-out';
            });

            link.addEventListener('mouseleave', () => {
                const arrow = link.querySelector('.arrow-bounce');
                if (arrow) arrow.style.animation = '';
            });
        });
    }

    // initButtonRipple - ELIMINADO (usuario no quiere efecto ripple)

    function initCTALoadingState() {
        const ctaButtons = document.querySelectorAll('.btn-hero-primary, .btn-accent, .btn-primary, .btn-outline-secondary');

        ctaButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                // No aplicar si es un link interno (anchor)
                if (this.getAttribute('href')?.startsWith('#')) return;

                // Analytics tracking
                const trackingId = this.dataset.tracking;
                if (trackingId) {
                    log(`📊 CTA Click: ${trackingId}`);
                    // Integración con GA4/analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'cta_click', {
                            'event_category': 'engagement',
                            'event_label': trackingId,
                            'value': 1
                        });
                    }
                }

                // Aplicar loading state (robusto - funciona con o sin .btn-text)
                const btnText = this.querySelector('.btn-text');
                let originalContent;

                if (btnText) {
                    // Opción A: Tiene .btn-text wrapper
                    originalContent = btnText.innerHTML;
                    btnText.textContent = 'Cargando';
                } else {
                    // Opción B: Texto directo en botón (fallback)
                    // Preservar icons y estructura
                    const textNodes = Array.from(this.childNodes).filter(
                        node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                    );
                    if (textNodes.length > 0) {
                        originalContent = textNodes[0].textContent;
                        textNodes[0].textContent = 'Cargando';
                    }
                }

                this.classList.add('is-loading');

                // Reset después de 5s (por si la navegación falla)
                setTimeout(() => {
                    this.classList.remove('is-loading');
                    if (btnText && originalContent) {
                        btnText.innerHTML = originalContent;
                    } else if (originalContent) {
                        const textNodes = Array.from(this.childNodes).filter(
                            node => node.nodeType === Node.TEXT_NODE
                        );
                        if (textNodes.length > 0) {
                            textNodes[0].textContent = originalContent;
                        }
                    }
                }, 5000);

                log(`🔄 Loading state applied to: ${trackingId || 'unnamed CTA'}`);
            });
        });

        log(`✅ Loading states initialized on ${ctaButtons.length} buttons`);
    }

    return {
        init: function() {
            initFadeInStagger();
            initMagneticButton();
            initIconPulse();
            initArrowBounce();
            // initButtonRipple(); - ELIMINADO
            initCTALoadingState();
        }
    };
})();

// ========================================
// 2. TIMELINE MODULE (Enhanced con Lazy Load + Keyboard Nav)
// ========================================
const KitaTimeline = (function() {
    let currentStepIndex = 0;
    const loadedGifs = new Set();

    function loadGifIfNeeded(stepNum) {
        const panel = document.getElementById(`detail-${stepNum}`);
        if (!panel) return;

        const lazyGif = panel.querySelector('.gif-lazy');
        if (!lazyGif) return;  // GIF ya cargado (Detail 1 usa eager)

        const gifKey = `gif-${stepNum}`;

        // FIX: Verificar si ya está marcado como cargado PRIMERO
        if (loadedGifs.has(gifKey)) return;

        // FIX: Verificar si ya tiene src real (evita re-cargas)
        if (lazyGif.src && !lazyGif.src.includes('data:image/svg')) {
            loadedGifs.add(gifKey);
            return;
        }

        // Marcar como cargando INMEDIATAMENTE (previene race condition)
        loadedGifs.add(gifKey);
        lazyGif.classList.add('gif-loading');

        // Cargar GIF real
        const realSrc = lazyGif.dataset.src;
        if (realSrc) {
            lazyGif.src = realSrc;

            lazyGif.addEventListener('load', function() {
                this.classList.remove('gif-loading');
                this.classList.add('gif-loaded');
            }, { once: true });
        }
    }

    function handleTimelineClick(event) {
        const step = event.currentTarget;
        const stepNum = parseInt(step.dataset.step);
        if (!stepNum) return;

        updateProgressBar(stepNum);
        currentStepIndex = stepNum - 1;  // Para keyboard nav

        // Lazy load GIF del panel
        loadGifIfNeeded(stepNum);

        // Marcar steps anteriores como completed
        document.querySelectorAll('.timeline-step').forEach(s => {
            const sNum = parseInt(s.dataset.step);
            s.classList.remove('active');
            s.setAttribute('aria-selected', 'false');

            // Marcar como completed si es anterior al step actual
            if (sNum < stepNum) {
                s.classList.add('completed');
            }
        });

        // Cross-fade: Primero fade out el panel actual
        const currentPanel = document.querySelector('.timeline-detail.active');
        if (currentPanel) {
            currentPanel.style.transition = 'opacity 0.3s ease';
            currentPanel.style.opacity = '0';
            setTimeout(() => {
                currentPanel.classList.remove('active');

                // Luego fade in el nuevo panel
                const detailEl = document.getElementById(`detail-${stepNum}`);
                if (detailEl) {
                    detailEl.classList.add('active', 'animating-in');
                    detailEl.style.transition = 'opacity 0.5s ease';
                    requestAnimationFrame(() => {
                        detailEl.style.opacity = '1';
                    });
                    setTimeout(() => {
                        detailEl.classList.remove('animating-in');
                        staggerExampleFields(detailEl);
                    }, 150);
                }
            }, 300);  // Espera más tiempo para fade out
        } else {
            // Primera carga - sin fade out previo
            const detailEl = document.getElementById(`detail-${stepNum}`);
            if (detailEl) {
                detailEl.classList.add('active', 'animating-in');
                setTimeout(() => {
                    detailEl.classList.remove('animating-in');
                    staggerExampleFields(detailEl);
                }, 100);
            }
        }

        step.classList.add('active');
        step.setAttribute('aria-selected', 'true');

        const numberEl = step.querySelector('.timeline-number');
        if (numberEl) {
            numberEl.style.animation = 'none';
            setTimeout(() => {
                numberEl.style.animation = 'number-rotate 0.4s ease-out';
            }, 10);
        }
    }

    function updateProgressBar(stepNum) {
        const progressBar = document.getElementById('timelineProgressBar');
        const progressText = document.getElementById('currentTimelineStep');

        if (progressBar) {
            const percentage = (stepNum / 3) * 100;
            progressBar.style.width = percentage + '%';
        }

        if (progressText) progressText.textContent = stepNum;
    }

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

    function initKeyboardNavigation() {
        const steps = Array.from(document.querySelectorAll('.timeline-step'));
        if (!steps.length) return;

        document.addEventListener('keydown', (e) => {
            // Solo si un tab tiene focus
            if (!document.activeElement.classList.contains('timeline-step')) {
                return;
            }

            let newIndex = currentStepIndex;

            if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                e.preventDefault();
                newIndex = Math.min(currentStepIndex + 1, steps.length - 1);
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                e.preventDefault();
                newIndex = Math.max(currentStepIndex - 1, 0);
            } else if (e.key === 'Home') {
                e.preventDefault();
                newIndex = 0;
            } else if (e.key === 'End') {
                e.preventDefault();
                newIndex = steps.length - 1;
            } else {
                return;  // Tecla no relevante
            }

            if (newIndex !== currentStepIndex) {
                steps[newIndex].click();
                steps[newIndex].focus();
            }
        });
    }

    function initTimeline() {
        const steps = document.querySelectorAll('.timeline-step');
        if (!steps.length) return;

        steps.forEach((step, index) => {
            step.addEventListener('click', handleTimelineClick);
        });

        // Keyboard navigation
        initKeyboardNavigation();

        const firstStep = steps[0];
        if (firstStep) {
            const stepNum = firstStep.dataset.step;
            firstStep.classList.add('active');
            firstStep.setAttribute('aria-selected', 'true');
            currentStepIndex = 0;

            const detailEl = document.getElementById(`detail-${stepNum}`);
            if (detailEl) detailEl.classList.add('active');
        }
    }

    return { init: initTimeline };
})();

// ========================================
// 3. FAQ MODULE (Refactored with Event Delegation)
// ========================================
const KitaFAQ = (function() {
    function toggleFAQ(questionButton) {
        const faqId = questionButton.getAttribute('aria-controls');
        if (!faqId) return;

        const answer = document.getElementById(faqId);
        const faqItem = questionButton.closest('.faq-item');
        if (!answer) return;

        const isExpanded = questionButton.getAttribute('aria-expanded') === 'true';

        questionButton.classList.toggle('active');
        answer.classList.toggle('active');
        questionButton.setAttribute('aria-expanded', String(!isExpanded));

        if (faqItem) faqItem.classList.toggle('active');

        // Smooth scroll into view si se expande
        if (!isExpanded) {
            setTimeout(() => {
                questionButton.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 100);
        }
    }

    function toggleAllFAQs(expand) {
        const allButtons = document.querySelectorAll('.faq-question');
        allButtons.forEach(button => {
            const isCurrentlyExpanded = button.getAttribute('aria-expanded') === 'true';
            if (expand && !isCurrentlyExpanded) {
                toggleFAQ(button);
            } else if (!expand && isCurrentlyExpanded) {
                toggleFAQ(button);
            }
        });
    }

    function initToggleAllButton() {
        const toggleBtn = document.getElementById('faqToggleAll');
        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', function() {
            const isExpanded = this.dataset.state === 'expanded';
            const newState = isExpanded ? 'collapsed' : 'expanded';

            // Toggle all FAQs
            toggleAllFAQs(!isExpanded);

            // Update button state
            this.dataset.state = newState;
            this.setAttribute('aria-pressed', String(!isExpanded));

            // Toggle icons and text
            this.querySelector('.btn-icon-expand').hidden = !isExpanded;
            this.querySelector('.btn-icon-collapse').hidden = isExpanded;
            this.querySelector('.btn-text-expand').hidden = !isExpanded;
            this.querySelector('.btn-text-collapse').hidden = isExpanded;

            log(`FAQ Toggle All: ${newState}`);
        });
    }

    function initURLHashHandling() {
        // Auto-expandir FAQ si viene de URL hash
        const hash = window.location.hash;
        if (hash.startsWith('#faq-')) {
            const faqId = hash.substring(1);
            const button = document.querySelector(`[aria-controls="${faqId}"]`);
            if (button) {
                setTimeout(() => {
                    toggleFAQ(button);
                    button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 500);
            }
        }
    }

    function initFAQSearch() {
        const searchInput = document.getElementById('faqSearch');
        const clearBtn = document.getElementById('faqSearchClearBtn');
        const clearSearchBtn = document.getElementById('faqClearSearch');
        const noResults = document.getElementById('faqNoResults');
        const searchTermEl = document.getElementById('searchTerm');

        if (!searchInput) return;

        // Search functionality
        searchInput.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase().trim();
            const faqItems = document.querySelectorAll('.faq-item');
            const categories = document.querySelectorAll('.faq-category');
            let visibleCount = 0;

            // Mostrar/ocultar clear button
            if (clearBtn) {
                clearBtn.hidden = e.target.value === '';
            }

            if (!query) {
                faqItems.forEach(item => {
                    item.style.display = '';
                    item.classList.remove('faq-match-highlight');
                });
                categories.forEach(cat => cat.style.display = '');
                if (noResults) noResults.hidden = true;
                return;
            }

            faqItems.forEach(item => {
                const question = item.querySelector('.faq-question').textContent.toLowerCase();
                const answer = item.querySelector('.faq-answer').textContent.toLowerCase();
                const matches = question.includes(query) || answer.includes(query);

                item.style.display = matches ? '' : 'none';
                if (matches) {
                    visibleCount++;
                    item.classList.add('faq-match-highlight');
                } else {
                    item.classList.remove('faq-match-highlight');
                }
            });

            categories.forEach(cat => {
                const visibleInCat = cat.querySelectorAll('.faq-item:not([style*="display: none"])').length;
                cat.style.display = visibleInCat > 0 ? '' : 'none';
            });

            if (noResults) {
                noResults.hidden = visibleCount > 0;
                if (visibleCount === 0 && searchTermEl) {
                    searchTermEl.textContent = query;
                }
            }
        });

        // Clear search function
        function clearFAQSearch() {
            if (searchInput) {
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
                searchInput.focus();
            }
        }

        // Clear button inline (X)
        if (clearBtn) {
            clearBtn.addEventListener('click', clearFAQSearch);
        }

        // Clear button en no results
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', clearFAQSearch);
        }

        // FAQ Search initialized silently
    }

    function initEventDelegation() {
        const faqContainer = document.getElementById('faqContainer');
        if (!faqContainer) return;

        // Event delegation para todos los FAQ buttons
        faqContainer.addEventListener('click', function(e) {
            const button = e.target.closest('.faq-question');
            if (!button) return;

            e.preventDefault();
            toggleFAQ(button);

            // Actualizar URL hash (opcional - no recarga página)
            const faqSlug = button.dataset.faq;
            if (faqSlug) {
                history.replaceState(null, null, `#faq-${faqSlug}`);
            }
        });

        // FAQ Event Delegation initialized silently
    }

    function initFAQ() {
        initEventDelegation();
        initToggleAllButton();
        initURLHashHandling();
        initFAQSearch();
    }

    return { init: initFAQ };
})();

// ========================================
// 4. COMPARISON ANIMATIONS MODULE (Enhanced con barras)
// ========================================
const ComparisonAnimations = (function() {
    function initComparisonBars() {
        const bars = document.querySelectorAll('.comparison-bar-fill');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const bar = entry.target;
                    const targetWidth = parseFloat(bar.dataset.width) || 0;

                    // Delay para efecto stagger
                    const row = bar.closest('tr');
                    const allRows = Array.from(document.querySelectorAll('.comparison-table tbody tr'));
                    const rowIndex = allRows.indexOf(row);
                    const delay = rowIndex * 150;  // 150ms entre cada fila

                    setTimeout(() => {
                        bar.style.width = targetWidth + '%';
                    }, delay);

                    observer.unobserve(bar);
                }
            });
        }, { threshold: 0.3 });

        bars.forEach(bar => observer.observe(bar));
    }

    function initRowsStagger() {
        const rows = document.querySelectorAll('.comparison-table tbody tr');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    rows.forEach((row, index) => {
                        row.style.opacity = '0';
                        row.style.transform = 'translateY(20px)';

                        setTimeout(() => {
                            row.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                            row.style.opacity = '1';
                            row.style.transform = 'translateY(0)';
                        }, index * 120);  // 120ms stagger
                    });

                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        if (rows.length > 0) {
            observer.observe(rows[0].closest('table'));
        }
    }

    function initTimeBars() {
        const bars = document.querySelectorAll('.time-bar-fill, .time-bar-fill-success');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const bar = entry.target;
                    const duration = parseFloat(bar.dataset.duration) || 15;
                    const maxDuration = 15;
                    const widthPercent = (duration / maxDuration) * 100;

                    setTimeout(() => {
                        bar.style.width = widthPercent + '%';
                    }, 300);

                    observer.unobserve(bar);
                }
            });
        }, { threshold: 0.5 });

        bars.forEach(bar => observer.observe(bar));
    }

    function initNumberCounters() {
        const numbers = document.querySelectorAll('.time-number');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const number = entry.target;
                    const targetText = number.textContent;
                    const target = parseFloat(targetText);

                    if (!isNaN(target)) {
                        number.textContent = '0';

                        setTimeout(() => {
                            let current = 0;
                            const duration = 1500;
                            const increment = target / (duration / 16);

                            const timer = setInterval(() => {
                                current += increment;
                                if (current >= target) {
                                    number.textContent = targetText;
                                    clearInterval(timer);
                                } else {
                                    number.textContent = Math.floor(current);
                                }
                            }, 16);
                        }, 200);

                        observer.unobserve(number);
                    }
                }
            });
        }, { threshold: 0.5 });

        numbers.forEach(num => observer.observe(num));
    }

    return {
        init: function() {
            initComparisonBars();
            initRowsStagger();
            initTimeBars();
            initNumberCounters();
        }
    };
})();

// ========================================
// 5. PRICING ANIMATIONS MODULE
// ========================================
const PricingAnimations = (function() {
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

    return {
        init: function() {
            initPriceCounter();
            initFeaturesStagger();
        }
    };
})();

// ========================================
// 6. ROI CALCULATOR MODULE (v2.0 - 50/50 Layout)
// ========================================
const KitaROICalculator = (function() {
    function init() {
        const slider = document.getElementById('salesSlider');
        const salesValueEl = document.getElementById('salesValue');
        const minutesWithoutEl = document.getElementById('minutesWithout');
        const minutesWithEl = document.getElementById('minutesWith');
        const minutesSavedEl = document.getElementById('minutesSaved');
        const hoursSavedEl = document.getElementById('hoursSaved');
        const hoursSavedDisplayEl = document.getElementById('hoursSavedDisplay');
        const barProblemEl = document.getElementById('barProblem');
        const barSolutionEl = document.getElementById('barSolution');
        const calcWithoutEl = document.getElementById('calcWithout');
        const calcWithEl = document.getElementById('calcWith');

        if (!slider) return;

        const MINUTES_WITHOUT_KITA = 15;
        const SECONDS_WITH_KITA = 30;

        function updateCalculations(sales) {
            const minutesWithout = sales * MINUTES_WITHOUT_KITA;
            const minutesWith = sales * (SECONDS_WITH_KITA / 60);
            const minutesSaved = minutesWithout - minutesWith;
            const hoursSaved = (minutesSaved / 60).toFixed(1);

            // Update sales value
            if (salesValueEl) salesValueEl.textContent = sales;

            // Update minutes without Kita
            if (minutesWithoutEl) minutesWithoutEl.textContent = Math.round(minutesWithout);

            // Update minutes with Kita
            if (minutesWithEl) minutesWithEl.textContent = Math.round(minutesWith);

            // Update minutes saved
            if (minutesSavedEl) minutesSavedEl.textContent = Math.round(minutesSaved);

            // Update hours saved
            if (hoursSavedEl) hoursSavedEl.textContent = hoursSaved + ' horas';
            if (hoursSavedDisplayEl) hoursSavedDisplayEl.textContent = hoursSaved;

            // Update bars (width as percentage)
            const maxMinutes = 1500; // 100 ventas × 15min
            const percentProblem = (minutesWithout / maxMinutes) * 100;
            const percentSolution = (minutesWith / maxMinutes) * 100;

            if (barProblemEl) barProblemEl.style.width = Math.min(percentProblem, 100) + '%';
            if (barSolutionEl) barSolutionEl.style.width = Math.max(percentSolution, 3) + '%';

            // Update calculations
            if (calcWithoutEl) calcWithoutEl.textContent = `${sales} × 15min cada venta`;
            if (calcWithEl) calcWithEl.textContent = `${sales} × 30seg cada venta`;

            // Update slider fill (Opción B - Fill progresivo)
            const sliderFillPercent = ((sales - 10) / (100 - 10)) * 100;
            if (slider) slider.style.setProperty('--slider-fill', sliderFillPercent + '%');

            // NUEVO: Animar GIF según valor del slider
            animateGrowthGIF(sales);
        }

        function animateGrowthGIF(sales) {
            const gif = document.querySelector('.roi-gif-growth');
            if (!gif) return;

            // Remover todas las clases de escala
            gif.classList.remove('scale-small', 'scale-medium', 'scale-large', 'scale-xlarge');

            // Aplicar escala según rango de ventas
            if (sales <= 25) {
                gif.classList.add('scale-small');    // 10-25: scale(0.85)
            } else if (sales <= 50) {
                gif.classList.add('scale-medium');   // 26-50: scale(0.95)
            } else if (sales <= 75) {
                gif.classList.add('scale-large');    // 51-75: scale(1)
            } else {
                gif.classList.add('scale-xlarge');   // 76-100: scale(1.08)
            }
        }

        // Inicializar con valor por defecto
        const initialValue = parseInt(slider.value);
        updateCalculations(initialValue);

        // Actualizar en cada cambio
        slider.addEventListener('input', function() {
            updateCalculations(parseInt(this.value));
        });

        // ROI Calculator initialized silently
    }

    return { init };
})();

// ========================================
// 7. CSS ANIMATIONS (Injected)
// ========================================
function injectAnimationStyles() {
    if (document.getElementById('kita-home-animations-css')) return;

    const style = document.createElement('style');
    style.id = 'kita-home-animations-css';
    style.textContent = `
        /* Icon pulse subtle */
        @keyframes icon-pulse-subtle {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.85; }
        }

        /* Arrow bounce */
        @keyframes arrow-bounce {
            0%, 100% { transform: translateX(0); }
            50% { transform: translateX(6px); }
        }

        /* Ripple animation - ELIMINADO */

        /* Number rotate */
        @keyframes number-rotate {
            from { transform: rotateY(90deg) scale(1.1); opacity: 0; }
            to { transform: rotateY(0) scale(1.1); opacity: 1; }
        }

        /* Magic pulse */
        @keyframes magic-pulse {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(5deg); }
        }
    `;
    document.head.appendChild(style);
}

// ========================================
// 8. MOBILE NAVBAR AUTO-CLOSE
// ========================================
const MobileNavbar = (function() {
    function init() {
        const internalLinks = document.querySelectorAll('.navbar-nav a[href^="#"]');
        const navbarToggler = document.querySelector('.navbar-toggler');
        const navbarCollapse = document.querySelector('.navbar-collapse');

        if (!navbarToggler || !navbarCollapse) return;

        internalLinks.forEach(link => {
            link.addEventListener('click', () => {
                // Solo en mobile
                if (window.innerWidth < 992 && navbarCollapse.classList.contains('show')) {
                    navbarToggler.click();
                }
            });
        });
    }

    return { init };
})();

// ========================================
// 9. VIDEO MODAL SYSTEM
// ========================================
const VideoModal = (function() {
    function createVideoModal(videoSrc) {
        const modal = document.createElement('div');
        modal.className = 'video-modal';
        modal.innerHTML = `
            <div class="video-modal-backdrop"></div>
            <div class="video-modal-content">
                <button class="video-modal-close" aria-label="Cerrar video">
                    <span class="iconoir-xmark"></span>
                </button>
                <div class="video-modal-wrapper">
                    <video
                        class="video-modal-player"
                        controls
                        preload="auto"
                        playsinline>
                        <source src="${videoSrc}" type="video/mp4">
                        Tu navegador no soporta video HTML5.
                    </video>
                </div>
            </div>
        `;

        const closeBtn = modal.querySelector('.video-modal-close');
        const backdrop = modal.querySelector('.video-modal-backdrop');
        const video = modal.querySelector('.video-modal-player');

        function closeModal() {
            modal.classList.remove('active');
            video.pause();
            document.body.classList.remove('video-modal-open');

            setTimeout(() => {
                modal.remove();
            }, 300);
        }

        closeBtn.addEventListener('click', closeModal);
        backdrop.addEventListener('click', closeModal);

        // Cerrar con ESC
        function escHandler(e) {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escHandler);
            }
        }
        document.addEventListener('keydown', escHandler);

        return { modal, video };
    }

    function init() {
        const playBtn = document.getElementById('videoPlayBtn');
        if (!playBtn) return;

        playBtn.addEventListener('click', function() {
            const videoSrc = playBtn.dataset.videoSrc || '/static/videos/kita-demo-hero.mp4';

            // Crear y agregar modal
            const { modal, video } = createVideoModal(videoSrc);
            document.body.appendChild(modal);

            // Prevenir scroll del body
            document.body.classList.add('video-modal-open');

            // Mostrar modal con animación
            requestAnimationFrame(() => {
                modal.classList.add('active');

                // Reproducir video
                video.play().catch(err => {
                    error('Error playing video:', err);
                });

                // Trackear evento en analytics
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'video_play', {
                        'event_category': 'engagement',
                        'event_label': 'hero_video',
                        'value': 1
                    });
                }
            });
        });

        // Video Modal initialized silently
    }

    return { init };
})();

// ========================================
// 10. COOKIE CONSENT BUTTON
// ========================================
const CookieConsentButton = (function() {
    function init() {
        const cookieBtn = document.getElementById('cookieConsentBtn');
        if (!cookieBtn) return;

        cookieBtn.addEventListener('click', function() {
            if (typeof resetCookieConsent === 'function') {
                resetCookieConsent();
                // Cookie consent panel opened
            } else {
                error('resetCookieConsent function not found');
            }
        });

        // Cookie Consent Button initialized silently
    }

    return { init };
})();

// ========================================
// MAIN INITIALIZATION
// ========================================
function initKitaHome() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initKitaHome);
        return;
    }

    try {
        // Inject CSS animations
        injectAnimationStyles();

        // Initialize all modules
        NavbarSticky.init();
        MobileNavbar.init();
        KitaHeroAnimations.init();
        KitaTimeline.init();
        KitaFAQ.init();
        ComparisonAnimations.init();
        PricingAnimations.init();
        KitaROICalculator.init();
        VideoModal.init();
        CookieConsentButton.init();

        // Kita Home Bundle initialized silently (use ?debug=1 to see logs)
    } catch (err) {
        error('[Kita Home] Initialization error:', err);
    }
}

// Auto-initialize
initKitaHome();
