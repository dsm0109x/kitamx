/**
 * ROI Calculator - Interactive Time Savings
 *
 * Calculates and displays real-time ROI based on monthly sales volume
 * Features smooth number animations and responsive feedback
 *
 * @version 1.0
 */

'use strict';

const KitaROICalculator = (function() {
    // Constants for calculations
    const MINUTES_PER_SALE_WITHOUT = 15;
    const MINUTES_PER_SALE_WITH = 0.5; // 30 seconds
    const HOURLY_RATE_MXN = 250;
    const KITA_MONTHLY_COST = 299;

    // DOM elements (cached)
    let slider, salesValue, salesBefore, salesAfter;
    let hoursBefore, hoursAfter, savedHours;
    let savedMoney, roiMultiplier;

    /**
     * Animate number change with counting effect
     */
    function animateNumber(element, newValue, decimals = 0) {
        if (!element) return;

        const currentValue = parseFloat(element.textContent) || 0;
        const difference = newValue - currentValue;
        const steps = 20;
        const stepValue = difference / steps;
        const duration = 300; // ms
        const stepDuration = duration / steps;

        let current = currentValue;
        let step = 0;

        // Add updating class for animation
        element.classList.add('updating');

        const timer = setInterval(() => {
            step++;
            current += stepValue;

            if (step >= steps) {
                current = newValue;
                clearInterval(timer);
                element.classList.remove('updating');
            }

            element.textContent = current.toFixed(decimals);
        }, stepDuration);
    }

    /**
     * Calculate all metrics based on sales volume
     */
    function calculateMetrics(sales) {
        // Time without Kita (hours per month)
        const minutesWithout = sales * MINUTES_PER_SALE_WITHOUT;
        const hoursWithoutKita = minutesWithout / 60;

        // Time with Kita (hours per month)
        const minutesWith = sales * MINUTES_PER_SALE_WITH;
        const hoursWithKita = minutesWith / 60;

        // Savings
        const hoursSaved = hoursWithoutKita - hoursWithKita;
        const moneySaved = hoursSaved * HOURLY_RATE_MXN;

        // ROI (money saved / cost)
        const roi = moneySaved / KITA_MONTHLY_COST;

        return {
            sales,
            hoursWithoutKita: hoursWithoutKita.toFixed(1),
            hoursWithKita: hoursWithKita.toFixed(1),
            hoursSaved: hoursSaved.toFixed(1),
            moneySaved: Math.round(moneySaved),
            roi: roi.toFixed(1)
        };
    }

    /**
     * Update all display values
     */
    function updateDisplay(metrics) {
        // Update sales numbers
        animateNumber(salesValue, metrics.sales, 0);
        animateNumber(salesBefore, metrics.sales, 0);
        animateNumber(salesAfter, metrics.sales, 0);

        // Update hours
        animateNumber(hoursBefore, parseFloat(metrics.hoursWithoutKita), 1);
        animateNumber(hoursAfter, parseFloat(metrics.hoursWithKita), 1);
        animateNumber(savedHours, parseFloat(metrics.hoursSaved), 1);

        // Update money
        animateNumber(savedMoney, metrics.moneySaved, 0);

        // Update ROI
        animateNumber(roiMultiplier, parseFloat(metrics.roi), 1);

        // Update slider progress fill
        updateSliderProgress(metrics.sales);
    }

    /**
     * Update slider visual progress
     */
    function updateSliderProgress(value) {
        if (!slider) return;

        const percentage = (value / slider.max) * 100;

        // Gradient based on value (low = orange, high = green)
        let color1, color2;
        if (value < 20) {
            color1 = '#f97316'; // orange
            color2 = '#fb923c';
        } else if (value < 50) {
            color1 = '#eab308'; // yellow
            color2 = '#fbbf24';
        } else {
            color1 = '#10b981'; // green
            color2 = '#34d399';
        }

        slider.style.background = `linear-gradient(to right, ${color1} 0%, ${color2} ${percentage}%, #e5e7eb ${percentage}%, #e5e7eb 100%)`;
    }

    /**
     * Handle slider input
     */
    function handleSliderChange(event) {
        const sales = parseInt(event.target.value, 10);
        const metrics = calculateMetrics(sales);
        updateDisplay(metrics);
    }

    /**
     * Cache DOM elements
     */
    function cacheElements() {
        slider = document.getElementById('salesSlider');
        salesValue = document.getElementById('salesValue');
        salesBefore = document.getElementById('salesBefore');
        salesAfter = document.getElementById('salesAfter');
        hoursBefore = document.getElementById('hoursBefore');
        hoursAfter = document.getElementById('hoursAfter');
        savedHours = document.getElementById('savedHours');
        savedMoney = document.getElementById('savedMoney');
        roiMultiplier = document.getElementById('roiMultiplier');
    }

    /**
     * Initialize calculator
     */
    function init() {
        // Wait for DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            cacheElements();

            if (!slider) {
                console.warn('[ROI Calculator] Slider not found, calculator not initialized');
                return;
            }

            // Attach slider listener
            slider.addEventListener('input', handleSliderChange);

            // Initial calculation with default value
            const initialSales = parseInt(slider.value, 10);
            const initialMetrics = calculateMetrics(initialSales);
            updateDisplay(initialMetrics);

            console.log('[ROI Calculator] Initialized successfully');
        } catch (error) {
            console.error('[ROI Calculator] Error initializing:', error);

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
KitaROICalculator.init();
