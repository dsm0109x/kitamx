/**
 * KITA COMMAND CENTER - JavaScript
 * Dashboard action-oriented functionality
 * Version: 1.0.0
 */

(function() {
    'use strict';

    // ============================================
    // AUTO-REFRESH CONFIGURATION
    // ============================================

    const REFRESH_INTERVALS = {
        pendingTasks: 120000,  // 2 minutes
        quickStats: 60000,      // 1 minute
        activityStream: 180000  // 3 minutes
    };

    let refreshTimers = {
        pendingTasks: null,
        quickStats: null,
        activityStream: null
    };

    // ============================================
    // INITIALIZATION
    // ============================================

    document.addEventListener('DOMContentLoaded', function() {
        console.log('Command Center: Initialized');

        // Start auto-refresh timers
        startAutoRefresh();

        // Initialize event listeners
        initializeEventListeners();

        // Check for pending tasks notification
        checkPendingTasksNotification();
    });

    // ============================================
    // AUTO-REFRESH FUNCTIONS
    // ============================================

    function startAutoRefresh() {
        // Refresh pending tasks
        refreshTimers.pendingTasks = setInterval(refreshPendingTasks, REFRESH_INTERVALS.pendingTasks);

        // Refresh quick stats
        refreshTimers.quickStats = setInterval(refreshQuickStats, REFRESH_INTERVALS.quickStats);

        // Refresh activity stream
        refreshTimers.activityStream = setInterval(refreshActivityStream, REFRESH_INTERVALS.activityStream);

        console.log('Command Center: Auto-refresh timers started');
    }

    function stopAutoRefresh() {
        Object.keys(refreshTimers).forEach(key => {
            if (refreshTimers[key]) {
                clearInterval(refreshTimers[key]);
                refreshTimers[key] = null;
            }
        });

        console.log('Command Center: Auto-refresh timers stopped');
    }

    function refreshPendingTasks() {
        const currentTaskCount = document.querySelectorAll('.task-item').length;

        fetch('/panel/ajax/tareas-pendientes/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // If task count changed, reload page for full update
                    if (data.count !== currentTaskCount) {
                        console.log('Command Center: Pending tasks changed, reloading...');
                        location.reload();
                    }
                }
            })
            .catch(error => {
                console.error('Command Center: Error refreshing pending tasks:', error);
            });
    }

    function refreshQuickStats() {
        fetch('/panel/ajax/estadisticas-rapidas/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateQuickStats(data.stats);
                }
            })
            .catch(error => {
                console.error('Command Center: Error refreshing quick stats:', error);
            });
    }

    function updateQuickStats(stats) {
        // Update DOM elements
        const elements = {
            'quick-stat-links': stats.active_links_count,
            'quick-stat-invoices': stats.pending_invoices_count,
            'quick-stat-payments': stats.payments_today
        };

        Object.keys(elements).forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                const newValue = elements[id];
                const oldValue = parseInt(element.textContent);

                // Animate if value changed
                if (newValue !== oldValue) {
                    animateNumberChange(element, oldValue, newValue);
                }
            }
        });
    }

    function animateNumberChange(element, oldValue, newValue) {
        element.classList.add('stat-updating');

        // Simple counter animation
        const duration = 500;
        const steps = 20;
        const increment = (newValue - oldValue) / steps;
        let current = oldValue;
        let step = 0;

        const timer = setInterval(() => {
            step++;
            current += increment;

            if (step >= steps) {
                element.textContent = newValue;
                clearInterval(timer);
                element.classList.remove('stat-updating');
            } else {
                element.textContent = Math.round(current);
            }
        }, duration / steps);
    }

    function refreshActivityStream() {
        fetch('/panel/ajax/actividad/?limit=10')  // 🇪🇸 Migrado
            .then(response => response.json())
            .then(data => {
                if (data.success && data.activities.length > 0) {
                    updateActivityStream(data.activities);
                }
            })
            .catch(error => {
                console.error('Command Center: Error refreshing activity stream:', error);
            });
    }

    function updateActivityStream(activities) {
        const streamContainer = document.getElementById('activity-stream');
        if (!streamContainer) return;

        // Check if we have new activities
        const currentFirstActivity = streamContainer.querySelector('.activity-item');
        if (!currentFirstActivity) return;

        const currentFirstTimestamp = currentFirstActivity.dataset.timestamp;
        const newFirstTimestamp = activities[0].timestamp;

        if (newFirstTimestamp !== currentFirstTimestamp) {
            // New activity detected - reload for fresh data
            console.log('Command Center: New activity detected, reloading...');
            location.reload();
        }
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================

    function initializeEventListeners() {
        // Stop refresh when user leaves page
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                stopAutoRefresh();
                console.log('Command Center: User left page, stopped auto-refresh');
            } else {
                startAutoRefresh();
                console.log('Command Center: User returned, restarted auto-refresh');
            }
        });

        // Listen for page unload
        window.addEventListener('beforeunload', function() {
            stopAutoRefresh();
        });
    }

    // ============================================
    // NOTIFICATIONS
    // ============================================

    function checkPendingTasksNotification() {
        const taskCount = document.querySelectorAll('.task-item').length;

        if (taskCount > 0) {
            // Update page title with count
            document.title = `(${taskCount}) Dashboard - Kita`;

            // Show browser notification (if permitted)
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('Kita - Tareas Pendientes', {
                    body: `Tienes ${taskCount} tarea${taskCount > 1 ? 's' : ''} que requiere${taskCount > 1 ? 'n' : ''} atención`,
                    icon: '/static/images/kita-icon.png',
                    badge: '/static/images/kita-badge.png',
                    tag: 'kita-pending-tasks'
                });
            }
        }
    }

    // ============================================
    // UTILITY FUNCTIONS
    // ============================================

    function formatRelativeTime(isoTimestamp) {
        const date = new Date(isoTimestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'hace un momento';
        if (diffMins < 60) return `hace ${diffMins} min`;
        if (diffHours < 24) return `hace ${diffHours} hora${diffHours > 1 ? 's' : ''}`;
        return `hace ${diffDays} día${diffDays > 1 ? 's' : ''}`;
    }

    // ============================================
    // GLOBAL EXPORTS (for inline onclick handlers)
    // ============================================

    window.KitaCommandCenter = {
        refresh: {
            pendingTasks: refreshPendingTasks,
            quickStats: refreshQuickStats,
            activityStream: refreshActivityStream,
            all: function() {
                refreshPendingTasks();
                refreshQuickStats();
                refreshActivityStream();
            }
        },
        stop: stopAutoRefresh,
        start: startAutoRefresh
    };

    console.log('Command Center: Ready');

})();
