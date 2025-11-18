/**
 * Kita Dashboard Charts - Chart.js Integration
 * Responsive charts with dark theme for analytics
 */

// Global Chart.js configuration for Kita theme
Chart.defaults.font.family = 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.color = '#f1f5f9';

// Kita Dark Theme Configuration
const kitaChartConfig = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        intersect: false,
        mode: 'index'
    },
    plugins: {
        legend: {
            position: window.innerWidth <= 768 ? 'bottom' : 'right',
            labels: {
                color: '#f1f5f9',
                usePointStyle: true,
                padding: 20,
                font: {
                    size: 11,
                    weight: '500'
                }
            }
        },
        tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            titleColor: '#f1f5f9',
            bodyColor: '#f1f5f9',
            borderColor: 'rgba(71, 85, 105, 0.4)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            displayColors: true
        }
    },
    scales: {
        x: {
            grid: {
                color: 'rgba(241, 245, 249, 0.1)',
                borderColor: 'rgba(241, 245, 249, 0.2)'
            },
            ticks: {
                color: '#94a3b8',
                font: {
                    size: 11
                }
            }
        },
        y: {
            grid: {
                color: 'rgba(241, 245, 249, 0.1)',
                borderColor: 'rgba(241, 245, 249, 0.2)'
            },
            ticks: {
                color: '#94a3b8',
                font: {
                    size: 11
                }
            }
        }
    }
};

// Global variables for chart instances
let revenueChart, successChart, linksChart, invoiceChart;

// Chart initialization class
class KitaDashboardCharts {
    constructor() {
        this.currentDateRange = this.getCurrentDateRange();
        this.charts = {};
        this.isLoading = false;
        this.observer = null;
        this.debounceTimer = null;

        this.init();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initLazyLoading());
        } else {
            this.initLazyLoading();
        }

        // Bind filter events
        this.bindFilterEvents();

        // Handle responsive changes
        window.addEventListener('resize', () => this.handleResize());
    }

    // Lazy loading with Intersection Observer
    initLazyLoading() {
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const chartId = entry.target.id;
                    this.loadChart(chartId);
                    this.observer.unobserve(entry.target);
                }
            });
        }, {
            rootMargin: '50px'
        });

        // Observe all chart canvases
        const canvases = ['revenueChart', 'successChart', 'linksChart', 'invoiceChart'];
        canvases.forEach(id => {
            const canvas = document.getElementById(id);
            if (canvas) {
                this.observer.observe(canvas);
            }
        });
    }

    // Load individual chart
    async loadChart(chartId) {
        switch(chartId) {
            case 'revenueChart':
                await this.initRevenueChart();
                break;
            case 'successChart':
                await this.initSuccessChart();
                break;
            case 'linksChart':
                await this.initLinksChart();
                break;
            case 'invoiceChart':
                await this.initInvoiceChart();
                break;
        }
    }

    getCurrentDateRange() {
        const startInput = document.querySelector('input[name="start_date"]');
        const endInput = document.querySelector('input[name="end_date"]');

        return {
            start_date: startInput ? startInput.value : '',
            end_date: endInput ? endInput.value : ''
        };
    }

    bindFilterEvents() {
        // Listen for date filter form submission
        const filterForm = document.querySelector('form[method="get"]');
        if (filterForm) {
            filterForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.currentDateRange = this.getCurrentDateRange();
                this.updateAllCharts();
            });
        }
    }

    handleResize() {
        // Update legend position based on screen size
        const isMobile = window.innerWidth <= 768;

        Object.values(this.charts).forEach(chart => {
            if (chart && chart.options && chart.options.plugins && chart.options.plugins.legend) {
                chart.options.plugins.legend.position = isMobile ? 'bottom' : 'right';
                chart.update('none');
            }
        });
    }

    async initCharts() {
        try {
            await this.initRevenueChart();
            await this.initSuccessChart();
            await this.initLinksChart();
            await this.initInvoiceChart();
        } catch (error) {
            console.error('Error initializing charts:', error);
        }
    }

    async initRevenueChart() {
        const ctx = document.getElementById('revenueChart');
        if (!ctx) return;

        this.showLoading('revenueLoading');

        try {
            const data = await this.fetchChartData('revenue-trends');
            this.hideLoading('revenueLoading');

            if (!data.success) {
                this.showError('revenueChart', 'Error cargando datos de ingresos');
                return;
            }

            this.charts.revenue = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: data.datasets
                },
                options: {
                    ...kitaChartConfig,
                    plugins: {
                        ...kitaChartConfig.plugins,
                        tooltip: {
                            ...kitaChartConfig.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: $${context.parsed.y.toFixed(2)} MXN`;
                                }
                            }
                        }
                    },
                    scales: {
                        ...kitaChartConfig.scales,
                        y: {
                            ...kitaChartConfig.scales.y,
                            beginAtZero: true,
                            ticks: {
                                ...kitaChartConfig.scales.y.ticks,
                                callback: function(value) {
                                    return '$' + value.toLocaleString('es-MX');
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            this.hideLoading('revenueLoading');
            this.showError('revenueChart', 'Error cargando gráfica de ingresos');
        }
    }

    async initSuccessChart() {
        const ctx = document.getElementById('successChart');
        if (!ctx) return;

        this.showLoading('successLoading');

        try {
            const data = await this.fetchChartData('payment-success');
            this.hideLoading('successLoading');

            if (!data.success) {
                this.showError('successChart', 'Error cargando datos de éxito');
                return;
            }

            this.charts.success = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.data,
                        backgroundColor: data.colors,
                        borderWidth: 2,
                        borderColor: '#1e293b'
                    }]
                },
                options: {
                    ...kitaChartConfig,
                    plugins: {
                        ...kitaChartConfig.plugins,
                        tooltip: {
                            ...kitaChartConfig.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    const total = data.total;
                                    const value = context.parsed;
                                    const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                    return `${context.label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            this.hideLoading('successLoading');
            this.showError('successChart', 'Error cargando gráfica de éxito');
        }
    }

    async initLinksChart() {
        const ctx = document.getElementById('linksChart');
        if (!ctx) return;

        this.showLoading('linksLoading');

        try {
            const data = await this.fetchChartData('links-performance');
            this.hideLoading('linksLoading');

            if (!data.success) {
                this.showError('linksChart', 'Error cargando datos de links');
                return;
            }

            this.charts.links = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.data,
                        backgroundColor: data.colors,
                        borderRadius: 6,
                        borderSkipped: false
                    }]
                },
                options: {
                    ...kitaChartConfig,
                    indexAxis: 'y',
                    plugins: {
                        ...kitaChartConfig.plugins,
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            ...kitaChartConfig.scales.x,
                            beginAtZero: true
                        },
                        y: {
                            ...kitaChartConfig.scales.y
                        }
                    }
                }
            });
        } catch (error) {
            this.hideLoading('linksLoading');
            this.showError('linksChart', 'Error cargando gráfica de links');
        }
    }

    async initInvoiceChart() {
        const ctx = document.getElementById('invoiceChart');
        if (!ctx) return;

        this.showLoading('invoiceLoading');

        try {
            const data = await this.fetchChartData('invoice-flow');
            this.hideLoading('invoiceLoading');

            if (!data.success) {
                this.showError('invoiceChart', 'Error cargando datos de facturas');
                return;
            }

            this.charts.invoice = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.data,
                        backgroundColor: data.colors,
                        borderRadius: 6,
                        borderSkipped: false
                    }]
                },
                options: {
                    ...kitaChartConfig,
                    plugins: {
                        ...kitaChartConfig.plugins,
                        legend: {
                            display: false
                        },
                        tooltip: {
                            ...kitaChartConfig.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    const value = context.parsed.y;
                                    const percentage = data.percentages[context.dataIndex];
                                    return `${context.label}: ${value} (${percentage.toFixed(1)}%)`;
                                }
                            }
                        }
                    },
                    scales: {
                        ...kitaChartConfig.scales,
                        y: {
                            ...kitaChartConfig.scales.y,
                            beginAtZero: true
                        }
                    }
                }
            });
        } catch (error) {
            this.hideLoading('invoiceLoading');
            this.showError('invoiceChart', 'Error cargando gráfica de facturas');
        }
    }

    async fetchChartData(endpoint) {
        const params = new URLSearchParams(this.currentDateRange);
        const response = await fetch(`/panel/api/${endpoint}/?${params}`);
        return await response.json();
    }

    // Debounced update function
    updateAllCharts() {
        // Clear existing debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Debounce updates by 300ms
        this.debounceTimer = setTimeout(() => {
            this.performChartUpdates();
        }, 300);
    }

    async performChartUpdates() {
        if (this.isLoading) return;

        this.isLoading = true;

        try {
            // Destroy existing charts for memory cleanup
            this.destroyCharts();

            await Promise.all([
                this.updateChart('revenue', 'revenue-trends', 'revenueLoading'),
                this.updateChart('success', 'payment-success', 'successLoading'),
                this.updateChart('links', 'links-performance', 'linksLoading'),
                this.updateChart('invoice', 'invoice-flow', 'invoiceLoading')
            ]);
        } catch (error) {
            console.error('Error updating charts:', error);
        } finally {
            this.isLoading = false;
        }
    }

    // Memory cleanup - destroy charts before recreating
    destroyCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }

    async updateChart(chartKey, endpoint, loadingId) {
        // For updates, re-initialize the chart completely
        const canvasId = `${chartKey}Chart`;
        this.loadChart(canvasId);
    }

    showLoading(loadingId) {
        const loading = document.getElementById(loadingId);
        if (loading) {
            loading.style.display = 'flex';
        }
    }

    hideLoading(loadingId) {
        const loading = document.getElementById(loadingId);
        if (loading) {
            loading.style.display = 'none';
        }
    }

    showError(canvasId, message) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const container = canvas.parentElement;
        container.innerHTML = `
            <div class="chart-error fade-in">
                <i class="iconoir-warning-triangle"></i>
                <h6 class="mt-2">Oops, algo salió mal</h6>
                <span>${message}</span>
                <button class="btn btn-outline-light btn-sm mt-2" onclick="window.kitaCharts.performChartUpdates()">
                    <i class="iconoir-refresh me-1"></i>Reintentar
                </button>
            </div>
        `;
    }

    showEmpty(canvasId, message) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const container = canvas.parentElement;
        container.innerHTML = `
            <div class="chart-empty fade-in">
                <i class="iconoir-stats-up"></i>
                <h6 class="mt-2">Aún no hay datos</h6>
                <span>Crea tu primer link de pago para ver analytics</span>
                <button class="btn btn-outline-light btn-sm mt-2" onclick="showCreateLinkModal()">
                    <i class="iconoir-plus me-1"></i>Crear Link
                </button>
            </div>
        `;
    }
}

// Initialize charts when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we're on the dashboard page
    if (document.getElementById('revenueChart')) {
        window.kitaCharts = new KitaDashboardCharts();
    }
});

// Export for global access
window.KitaDashboardCharts = KitaDashboardCharts;