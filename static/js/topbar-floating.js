/**
 * TOPBAR FLOATING - INTERACTIONS
 * ================================
 *
 * Maneja todas las interacciones del top bar flotante glass.
 *
 * Features:
 * - ✅ Sidebar toggle conectado
 * - ✅ Scroll detection (glass opacity change)
 * - ✅ Notifications dropdown
 * - ✅ User menu dropdown
 * - ✅ Click outside to close
 * - ✅ Escape key support
 * - ✅ Analytics tracking
 *
 * @version 1.0
 * @created 2025-10-21
 */

'use strict';

(function() {

    // ========================================
    // 1. TOPBAR MANAGER
    // ========================================

    class TopbarFloating {
        constructor() {
            this.topbar = document.querySelector('.topbar-floating');
            this.toggleBtn = document.getElementById('sidebarToggleTopbar');
            this.sidebar = document.querySelector('.kita-sidebar');

            if (!this.topbar) {
                console.warn('[Topbar] .topbar-floating not found');
                return;
            }

            // State
            this.isScrolled = false;
            this.scrollThreshold = 10;

            this.init();
        }

        init() {
            console.log('[Topbar] Initializing topbar floating...');

            // Bind events
            this.bindEvents();

            console.log('[Topbar] ✅ Topbar initialized');
        }

        bindEvents() {
            // Scroll detection
            window.addEventListener('scroll', () => this.handleScroll(), { passive: true });

            // Sidebar toggle
            if (this.toggleBtn) {
                this.toggleBtn.addEventListener('click', () => this.toggleSidebar());
            }
        }

        handleScroll() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

            if (scrollTop > this.scrollThreshold && !this.isScrolled) {
                this.isScrolled = true;
                this.topbar.classList.add('scrolled');
            } else if (scrollTop <= this.scrollThreshold && this.isScrolled) {
                this.isScrolled = false;
                this.topbar.classList.remove('scrolled');
            }
        }

        toggleSidebar() {
            if (!this.sidebar) return;

            // Toggle collapsed class en sidebar
            this.sidebar.classList.toggle('collapsed');

            // Update body class para CSS selectors
            const isCollapsed = this.sidebar.classList.contains('collapsed');
            if (isCollapsed) {
                document.body.classList.add('sidebar-collapsed');     /* ✅ Agregar clase al body */
            } else {
                document.body.classList.remove('sidebar-collapsed');  /* ✅ Quitar clase del body */
            }

            // Update aria-expanded
            this.toggleBtn?.setAttribute('aria-expanded', !isCollapsed);

            // Persist state
            localStorage.setItem('sidebar-collapsed', isCollapsed);

            // Analytics
            this.trackEvent('sidebar_toggle_topbar', { collapsed: isCollapsed });
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'topbar',
                    ...params
                });
            }
        }
    }

    // ========================================
    // 2. NOTIFICATIONS DROPDOWN - DISABLED
    // ========================================
    // Feature removida por no estar funcional
    // TODO: Reimplementar cuando el backend esté listo

    /*
    class NotificationsDropdown {
        constructor() {
            this.btn = document.getElementById('notificationsBtn');
            this.dropdown = document.querySelector('.notifications-dropdown');

            if (!this.btn || !this.dropdown) {
                console.log('[Notifications] Dropdown not found (OK if not implemented)');
                return;
            }

            this.isOpen = false;
            this.init();
        }

        init() {
            console.log('[Notifications] Initializing dropdown...');

            this.bindEvents();

            console.log('[Notifications] ✅ Dropdown initialized');
        }

        bindEvents() {
            // Toggle dropdown
            this.btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggle();
            });

            // Close on click outside
            document.addEventListener('click', (e) => {
                if (this.isOpen &&
                    !this.dropdown.contains(e.target) &&
                    !this.btn.contains(e.target)) {
                    this.close();
                }
            });

            // Close on escape
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) {
                    this.close();
                }
            });

            // Mark as read
            this.dropdown.querySelectorAll('.notification-item').forEach(item => {
                item.addEventListener('click', () => {
                    item.classList.remove('unread');
                    this.updateBadgeCount();
                });
            });
        }

        toggle() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }

        open() {
            // Close other dropdowns first
            if (window.userMenuDropdown && window.userMenuDropdown.isOpen) {
                window.userMenuDropdown.close();
            }

            this.dropdown.classList.add('show');
            this.btn.setAttribute('aria-expanded', 'true');
            this.isOpen = true;

            // Analytics
            this.trackEvent('notifications_open');
        }

        close() {
            this.dropdown.classList.remove('show');
            this.btn.setAttribute('aria-expanded', 'false');
            this.isOpen = false;

            // Analytics
            this.trackEvent('notifications_close');
        }

        updateBadgeCount() {
            const unreadCount = this.dropdown.querySelectorAll('.notification-item.unread').length;
            const badge = document.getElementById('notifCount');

            if (badge) {
                if (unreadCount > 0) {
                    badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'notifications',
                    ...params
                });
            }
        }
    }
    */  // Fin del comentario de NotificationsDropdown

    // ========================================
    // 3. USER MENU DROPDOWN
    // ========================================

    class UserMenuDropdown {
        constructor() {
            this.btn = document.getElementById('userMenuBtn');
            this.dropdown = document.querySelector('.user-menu-dropdown');

            if (!this.btn || !this.dropdown) {
                console.log('[UserMenu] Dropdown not found (OK if not implemented)');
                return;
            }

            this.isOpen = false;
            this.init();
        }

        init() {
            console.log('[UserMenu] Initializing dropdown...');

            this.bindEvents();

            console.log('[UserMenu] ✅ Dropdown initialized');
        }

        bindEvents() {
            // Toggle dropdown
            this.btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggle();
            });

            // Close on click outside
            document.addEventListener('click', (e) => {
                if (this.isOpen &&
                    !this.dropdown.contains(e.target) &&
                    !this.btn.contains(e.target)) {
                    this.close();
                }
            });

            // Close on escape
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) {
                    this.close();
                }
            });
        }

        toggle() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }

        open() {
            // Close other dropdowns first (notifications disabled)
            // if (window.notificationsDropdown && window.notificationsDropdown.isOpen) {
            //     window.notificationsDropdown.close();
            // }

            this.dropdown.classList.add('show');
            this.btn.setAttribute('aria-expanded', 'true');
            this.isOpen = true;

            // Analytics
            this.trackEvent('user_menu_open');
        }

        close() {
            this.dropdown.classList.remove('show');
            this.btn.setAttribute('aria-expanded', 'false');
            this.isOpen = false;

            // Analytics
            this.trackEvent('user_menu_close');
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'user_menu',
                    ...params
                });
            }
        }
    }

    // ========================================
    // 4. TRIAL BADGE INTERACTION
    // ========================================

    class TrialBadgeManager {
        constructor() {
            this.badge = document.querySelector('.trial-badge-topbar');

            if (!this.badge) {
                console.log('[Trial] Badge not found (OK if not in trial)');
                return;
            }

            this.init();
        }

        init() {
            console.log('[Trial] Initializing badge...');

            this.bindEvents();

            console.log('[Trial] ✅ Badge initialized');
        }

        bindEvents() {
            // Click to open upgrade modal
            this.badge.addEventListener('click', () => {
                this.openUpgradeModal();
            });
        }

        openUpgradeModal() {
            // TODO: Implementar modal de upgrade
            console.log('[Trial] Opening upgrade modal...');

            if (typeof showToast !== 'undefined') {
                showToast('Upgrade modal - Coming soon', 'info');
            }

            // Analytics
            this.trackEvent('trial_badge_click');
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'trial',
                    ...params
                });
            }
        }
    }

    // ========================================
    // 5. INITIALIZATION
    // ========================================

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTopbar);
    } else {
        initializeTopbar();
    }

    function initializeTopbar() {
        console.log('[TopbarFloating] Starting initialization...');

        // Initialize components
        window.topbarFloating = new TopbarFloating();
        // window.notificationsDropdown = new NotificationsDropdown();  // DISABLED - Feature removida
        window.userMenuDropdown = new UserMenuDropdown();
        window.trialBadgeManager = new TrialBadgeManager();

        console.log('[TopbarFloating] ✅ All components initialized');
    }

    // ========================================
    // 6. GLOBAL UTILITIES
    // ========================================

    // Open upgrade modal (called from HTML)
    window.openUpgradeModal = function() {
        if (window.trialBadgeManager) {
            window.trialBadgeManager.openUpgradeModal();
        }
    };

})();
