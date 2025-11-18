/**
 * ROI Calculator - SIMPLIFIED VERSION
 * Solo horas ahorradas, sin dinero ni ROI
 */

'use strict';

document.addEventListener('DOMContentLoaded', function() {
    const slider = document.getElementById('salesSlider');
    const salesValueEl = document.getElementById('salesValue');
    const hoursSavedEl = document.getElementById('hoursSaved');

    if (!slider) return;

    // Constants
    const MINUTES_WITHOUT_KITA = 15;
    const SECONDS_WITH_KITA = 30;

    function updateCalculations(sales) {
        const hoursWithout = (sales * MINUTES_WITHOUT_KITA) / 60;
        const hoursWith = (sales * (SECONDS_WITH_KITA / 60)) / 60;
        const hoursSaved = hoursWithout - hoursWith;

        if (salesValueEl) salesValueEl.textContent = sales;
        if (hoursSavedEl) hoursSavedEl.textContent = hoursSaved.toFixed(1);
    }

    updateCalculations(parseInt(slider.value));

    slider.addEventListener('input', function() {
        updateCalculations(parseInt(this.value));
    });

    console.log('✨ ROI Calculator (simple) initialized');
});
