/**
 * KITA SIDEBAR PREMIUM - INTERACTIONS
 * ====================================
 *
 * Maneja todas las interacciones del sidebar premium:
 * - Desktop: Collapse/expand con persistencia
 * - Tablet: Auto-collapse en scroll
 * - Mobile: Drawer + Bottom nav
 * - Global: Command palette, keyboard shortcuts
 *
 * @version 1.0
 * @created 2025-10-21
 */

'use strict';

(function() {

    // ========================================
    // 1. SIDEBAR MANAGER (Desktop/Tablet)
    // ========================================

    class KitaSidebarPremium {
        constructor() {
            this.sidebar = document.querySelector('.kita-sidebar');
            this.toggle = document.getElementById('sidebarToggleTopbar');
            this.toggleIcon = this.toggle?.querySelector('i');
            this.main = document.querySelector('.dashboard-main');

            if (!this.sidebar) {
                console.warn('[Sidebar] .kita-sidebar not found');
                return;
            }

            // State
            this.isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
            this.isMobile = window.innerWidth < 768;
            this.isTablet = window.innerWidth >= 768 && window.innerWidth < 1200;

            // Scroll detection (tablet)
            this.lastScrollTop = 0;
            this.scrollThreshold = 100;

            this.init();
        }

        init() {
            console.log('[Sidebar] Initializing premium sidebar...');

            // Apply initial state
            this.updateSidebarState();

            // Bind events
            this.bindEvents();

            // Update counts
            this.updateBadgeCounts();

            console.log('[Sidebar] ✅ Premium sidebar initialized');
        }

        bindEvents() {
            // Toggle button click
            if (this.toggle) {
                this.toggle.addEventListener('click', () => this.toggleCollapse());
            }

            // Window resize
            window.addEventListener('resize', () => this.handleResize());

            // ✅ Tablet auto-collapse eliminado (no deseado)

            // Keyboard shortcut (Cmd/Ctrl + B)
            document.addEventListener('keydown', (e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
                    e.preventDefault();
                    this.toggleCollapse();
                }
            });
        }

        toggleCollapse() {
            if (this.isMobile) return;    // No collapse en mobile

            this.isCollapsed = !this.isCollapsed;
            this.updateSidebarState();

            // Persist preference
            localStorage.setItem('sidebar-collapsed', this.isCollapsed);

            // Analytics
            this.trackEvent('sidebar_toggle', { collapsed: this.isCollapsed });
        }

        updateSidebarState() {
            if (this.isMobile) {
                this.sidebar.classList.remove('collapsed');
                document.body.classList.remove('sidebar-collapsed');
                return;
            }

            if (this.isCollapsed) {
                this.sidebar.classList.add('collapsed');
                document.body.classList.add('sidebar-collapsed');
                this.toggle?.setAttribute('aria-expanded', 'false');
            } else {
                this.sidebar.classList.remove('collapsed');
                document.body.classList.remove('sidebar-collapsed');
                this.toggle?.setAttribute('aria-expanded', 'true');
            }
        }

        handleResize() {
            const wasMobile = this.isMobile;
            const wasTablet = this.isTablet;

            this.isMobile = window.innerWidth < 768;
            this.isTablet = window.innerWidth >= 768 && window.innerWidth < 1200;

            // Cambio de breakpoint
            if (wasMobile !== this.isMobile || wasTablet !== this.isTablet) {
                console.log('[Sidebar] Breakpoint changed:', {
                    mobile: this.isMobile,
                    tablet: this.isTablet
                });

                // Reset states
                this.updateSidebarState();
            }
        }

        /* ✅ handleTabletScroll eliminado - auto-collapse removido */

        updateBadgeCounts() {
            // TODO: Agregar endpoint /panel/api/contadores/ en dashboard/urls.py
            // Por ahora, badges se actualizan desde los datos del sidebar
            // Counts are calculated server-side and rendered in template
            console.log('[Sidebar] Badge counts rendered server-side');
        }

        setBadgeCount(id, count) {
            const badge = document.getElementById(id);
            if (!badge) return;

            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'flex';

                // Show dot badge también si existe
                const dotBadge = badge.parentElement?.querySelector('.badge-dot');
                if (dotBadge) dotBadge.style.display = 'block';
            } else {
                badge.style.display = 'none';

                // Hide dot badge también
                const dotBadge = badge.parentElement?.querySelector('.badge-dot');
                if (dotBadge) dotBadge.style.display = 'none';
            }
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'sidebar',
                    ...params
                });
            }
        }
    }

    // ========================================
    // 2. MOBILE DRAWER MANAGER
    // ========================================

    class MobileDrawerManager {
        constructor() {
            this.drawer = document.querySelector('.mobile-sidebar-drawer');
            this.overlay = document.querySelector('.mobile-drawer-overlay');
            this.openTriggers = document.querySelectorAll('[data-mobile-drawer="open"]');
            this.closeTriggers = document.querySelectorAll('[data-mobile-drawer="close"]');

            if (!this.drawer) {
                console.log('[Drawer] Mobile drawer not found (OK if desktop)');
                return;
            }

            this.init();
        }

        init() {
            console.log('[Drawer] Initializing mobile drawer...');

            this.bindEvents();

            console.log('[Drawer] ✅ Mobile drawer initialized');
        }

        bindEvents() {
            // Open triggers
            this.openTriggers.forEach(trigger => {
                trigger.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.open();
                });
            });

            // Close triggers
            this.closeTriggers.forEach(trigger => {
                trigger.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.close();
                });
            });

            // Close en overlay click
            if (this.overlay) {
                this.overlay.addEventListener('click', () => this.close());
            }

            // Close con Esc
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen()) {
                    this.close();
                }
            });

            // Swipe to close (simple implementation)
            this.initSwipeGestures();
        }

        open() {
            if (this.drawer) {
                this.drawer.classList.add('open');
                this.overlay?.classList.add('show');
                document.body.style.overflow = 'hidden';  // Prevent scroll

                // Analytics
                this.trackEvent('drawer_open');
            }
        }

        close() {
            if (this.drawer) {
                this.drawer.classList.remove('open');
                this.overlay?.classList.remove('show');
                document.body.style.overflow = '';

                // Analytics
                this.trackEvent('drawer_close');
            }
        }

        isOpen() {
            return this.drawer?.classList.contains('open');
        }

        initSwipeGestures() {
            if (!this.drawer) return;

            let startX = 0;
            let currentX = 0;
            let isDragging = false;

            this.drawer.addEventListener('touchstart', (e) => {
                startX = e.touches[0].clientX;
                isDragging = true;
            }, { passive: true });

            this.drawer.addEventListener('touchmove', (e) => {
                if (!isDragging) return;

                currentX = e.touches[0].clientX;
                const diff = currentX - startX;

                // Solo permitir swipe hacia izquierda (close)
                if (diff < 0) {
                    const translateX = Math.max(diff, -this.drawer.offsetWidth);
                    this.drawer.style.transform = `translateX(${translateX}px)`;
                }
            }, { passive: true });

            this.drawer.addEventListener('touchend', () => {
                if (!isDragging) return;

                const diff = currentX - startX;

                // Si swipe > 30% del width, cerrar
                if (Math.abs(diff) > this.drawer.offsetWidth * 0.3) {
                    this.close();
                } else {
                    // Volver a posición original
                    this.drawer.style.transform = '';
                }

                isDragging = false;
                this.drawer.style.transition = 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)';

                setTimeout(() => {
                    this.drawer.style.transition = '';
                }, 350);
            });
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'mobile_drawer',
                    ...params
                });
            }
        }
    }

    // ========================================
    // 3. COMMAND PALETTE
    // ========================================

    class CommandPalette {
        constructor() {
            this.palette = null;
            this.input = null;
            this.results = null;
            this.isOpen = false;
            this.selectedIndex = 0;

            // Commands registry
            this.commands = this.getCommands();

            this.init();
        }

        init() {
            console.log('[CommandPalette] Initializing...');

            // Create palette HTML
            this.createPalette();

            // Bind keyboard shortcut
            document.addEventListener('keydown', (e) => {
                // Cmd+K or Ctrl+K
                if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                    e.preventDefault();
                    this.toggle();
                }

                // Esc to close
                if (e.key === 'Escape' && this.isOpen) {
                    this.close();
                }
            });

            console.log('[CommandPalette] ✅ Command palette initialized');
        }

        getCommands() {
            return [
                // Quick Actions
                {
                    id: 'create-link',
                    title: 'Crear Link de Pago',
                    subtitle: 'Genera un nuevo link de cobro',
                    icon: 'iconoir-plus',
                    shortcut: 'Cmd+N',
                    action: () => {
                        if (typeof showCreateLinkModal !== 'undefined') {
                            showCreateLinkModal();
                        }
                    },
                    category: 'Acciones Rápidas'
                },
                {
                    id: 'new-invoice',
                    title: 'Nueva Factura',
                    subtitle: 'Generar CFDI manualmente',
                    icon: 'iconoir-page',
                    action: () => window.location.href = '/facturas/crear/',  // 🇪🇸 Migrado
                    category: 'Acciones Rápidas'
                },

                // Navigation
                {
                    id: 'nav-dashboard',
                    title: 'Ir a Dashboard',
                    subtitle: 'Vista general',
                    icon: 'iconoir-dashboard',
                    shortcut: 'D',
                    action: () => window.location.href = '/panel/',
                    category: 'Navegación'
                },
                {
                    id: 'nav-links',
                    title: 'Ir a Links',
                    subtitle: 'Gestiona tus links de pago',
                    icon: 'iconoir-link',
                    shortcut: 'L',
                    action: () => window.location.href = '/enlaces/',
                    category: 'Navegación'
                },
                {
                    id: 'nav-invoices',
                    title: 'Ir a Facturación',
                    subtitle: 'CFDIs y timbrado',
                    icon: 'iconoir-page',
                    shortcut: 'I',
                    action: () => window.location.href = '/facturas/',
                    category: 'Navegación'
                },
                {
                    id: 'nav-settings',
                    title: 'Ir a Mi Negocio',
                    subtitle: 'Configuración fiscal',
                    icon: 'iconoir-shop',
                    shortcut: 'S',
                    action: () => window.location.href = '/negocio/',
                    category: 'Navegación'
                },

                // Account
                {
                    id: 'edit-profile',
                    title: 'Editar Mi Perfil',
                    subtitle: 'Datos personales',
                    icon: 'iconoir-user',
                    action: () => window.location.href = '/cuenta/',
                    category: 'Cuenta'
                },
                {
                    id: 'subscription',
                    title: 'Ver Suscripción',
                    subtitle: 'Plan y facturación',
                    icon: 'iconoir-credit-card',
                    action: () => window.location.href = '/suscripcion/',  // 🇪🇸 Migrado
                    category: 'Cuenta'
                },

                // Account
                {
                    id: 'logout',
                    title: 'Cerrar Sesión',
                    subtitle: 'Salir de tu cuenta',
                    icon: 'iconoir-log-out',
                    action: () => window.location.href = '/accounts/logout/',
                    category: 'Cuenta'
                }
            ];
        }

        createPalette() {
            const html = `
                <div class="command-palette-overlay" id="commandPaletteOverlay">
                    <div class="command-palette" id="commandPalette">
                        <div class="command-palette-header">
                            <input type="text"
                                   class="command-palette-input"
                                   id="commandPaletteInput"
                                   placeholder="Buscar o escribir comando..."
                                   autocomplete="off"
                                   spellcheck="false">
                        </div>
                        <div class="command-palette-results" id="commandPaletteResults">
                            <!-- Results will be injected here -->
                        </div>
                        <div class="command-palette-footer">
                            <div class="palette-hint">
                                <kbd>↑↓</kbd> Navegar
                                <kbd>Enter</kbd> Ejecutar
                                <kbd>Esc</kbd> Cerrar
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', html);

            this.palette = document.getElementById('commandPalette');
            this.input = document.getElementById('commandPaletteInput');
            this.results = document.getElementById('commandPaletteResults');
            this.overlay = document.getElementById('commandPaletteOverlay');

            // Bind palette events
            this.bindPaletteEvents();
        }

        bindPaletteEvents() {
            // Input search
            this.input.addEventListener('input', (e) => {
                this.search(e.target.value);
            });

            // Keyboard navigation
            this.input.addEventListener('keydown', (e) => {
                switch(e.key) {
                    case 'ArrowDown':
                        e.preventDefault();
                        this.selectNext();
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        this.selectPrevious();
                        break;
                    case 'Enter':
                        e.preventDefault();
                        this.executeSelected();
                        break;
                }
            });

            // Close en overlay click
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) {
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
            this.overlay.classList.add('show');
            this.isOpen = true;
            this.selectedIndex = 0;

            // Render all commands initially
            this.renderResults(this.commands);

            // Focus input
            setTimeout(() => {
                this.input.focus();
            }, 100);

            // Analytics
            this.trackEvent('palette_open');
        }

        close() {
            this.overlay.classList.remove('show');
            this.isOpen = false;
            this.input.value = '';

            // Analytics
            this.trackEvent('palette_close');
        }

        search(query) {
            if (!query.trim()) {
                this.renderResults(this.commands);
                return;
            }

            // Fuzzy search
            const lowerQuery = query.toLowerCase();
            const filtered = this.commands.filter(cmd => {
                return cmd.title.toLowerCase().includes(lowerQuery) ||
                       cmd.subtitle.toLowerCase().includes(lowerQuery) ||
                       (cmd.shortcut && cmd.shortcut.toLowerCase().includes(lowerQuery));
            });

            this.selectedIndex = 0;
            this.renderResults(filtered);

            // Analytics
            this.trackEvent('palette_search', { query: query, results: filtered.length });
        }

        renderResults(commands) {
            if (commands.length === 0) {
                this.results.innerHTML = `
                    <div class="command-empty">
                        <p>No se encontraron comandos</p>
                    </div>
                `;
                return;
            }

            // Group by category
            const grouped = commands.reduce((acc, cmd) => {
                if (!acc[cmd.category]) acc[cmd.category] = [];
                acc[cmd.category].push(cmd);
                return acc;
            }, {});

            let html = '';
            Object.keys(grouped).forEach(category => {
                html += `<div class="command-category">
                    <div class="command-category-title">${category}</div>`;

                grouped[category].forEach((cmd, index) => {
                    const globalIndex = commands.indexOf(cmd);
                    const isSelected = globalIndex === this.selectedIndex;

                    html += `
                        <button class="command-item ${isSelected ? 'selected' : ''}"
                                data-index="${globalIndex}"
                                data-command-id="${cmd.id}">
                            <i class="${cmd.icon} command-icon"></i>
                            <div class="command-content">
                                <div class="command-title">${cmd.title}</div>
                                <div class="command-subtitle">${cmd.subtitle}</div>
                            </div>
                            ${cmd.shortcut ? `<kbd class="command-shortcut">${cmd.shortcut}</kbd>` : ''}
                        </button>
                    `;
                });

                html += `</div>`;
            });

            this.results.innerHTML = html;

            // Bind click events
            this.results.querySelectorAll('.command-item').forEach(item => {
                item.addEventListener('click', () => {
                    const index = parseInt(item.dataset.index);
                    this.selectedIndex = index;
                    this.executeSelected();
                });
            });
        }

        selectNext() {
            const items = this.results.querySelectorAll('.command-item');
            if (items.length === 0) return;

            this.selectedIndex = (this.selectedIndex + 1) % items.length;
            this.updateSelection();
        }

        selectPrevious() {
            const items = this.results.querySelectorAll('.command-item');
            if (items.length === 0) return;

            this.selectedIndex = this.selectedIndex === 0 ? items.length - 1 : this.selectedIndex - 1;
            this.updateSelection();
        }

        updateSelection() {
            const items = this.results.querySelectorAll('.command-item');
            items.forEach((item, index) => {
                if (index === this.selectedIndex) {
                    item.classList.add('selected');
                    item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                } else {
                    item.classList.remove('selected');
                }
            });
        }

        executeSelected() {
            const items = this.results.querySelectorAll('.command-item');
            const selectedItem = items[this.selectedIndex];

            if (!selectedItem) return;

            const commandId = selectedItem.dataset.commandId;
            const command = this.commands.find(cmd => cmd.id === commandId);

            if (command && command.action) {
                this.close();
                command.action();

                // Analytics
                this.trackEvent('command_execute', {
                    command_id: commandId,
                    command_title: command.title
                });
            }
        }

        trackEvent(eventName, params = {}) {
            if (typeof gtag !== 'undefined') {
                gtag('event', eventName, {
                    'event_category': 'command_palette',
                    ...params
                });
            }
        }
    }

    // ========================================
    // 4. KEYBOARD SHORTCUTS (Global)
    // ========================================

    class KeyboardShortcuts {
        constructor() {
            this.shortcuts = {
                'd': () => window.location.href = '/panel/',
                'l': () => window.location.href = '/enlaces/',
                'i': () => window.location.href = '/facturas/',
                's': () => window.location.href = '/negocio/',
            };

            this.init();
        }

        init() {
            document.addEventListener('keydown', (e) => {
                // Ignore si está en input/textarea
                if (e.target.matches('input, textarea, select')) return;

                // Ignore si hay modifiers (excepto Shift para '?')
                if (e.metaKey || e.ctrlKey || e.altKey) return;

                const key = e.key.toLowerCase();

                if (this.shortcuts[key]) {
                    e.preventDefault();
                    this.shortcuts[key]();

                    // Analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'keyboard_shortcut', {
                            'event_category': 'navigation',
                            'event_label': key
                        });
                    }
                }
            });

            console.log('[Shortcuts] ✅ Keyboard shortcuts initialized');
        }
    }

    // ========================================
    // 5. BADGE UPDATER (Real-time)
    // ========================================

    class BadgeUpdater {
        constructor() {
            this.updateInterval = 60000;     // Update every minute
            this.timer = null;

            this.init();
        }

        init() {
            // Update immediately
            this.update();

            // Set interval
            this.timer = setInterval(() => this.update(), this.updateInterval);

            // Update on visibility change
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    this.update();
                }
            });

            console.log('[BadgeUpdater] ✅ Badge auto-updater initialized');
        }

        update() {
            if (window.kitaSidebar && window.kitaSidebar.updateBadgeCounts) {
                window.kitaSidebar.updateBadgeCounts();
            }
        }

        destroy() {
            if (this.timer) {
                clearInterval(this.timer);
            }
        }
    }

    // ========================================
    // 6. INITIALIZATION
    // ========================================

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeSidebar);
    } else {
        initializeSidebar();
    }

    function initializeSidebar() {
        console.log('[SidebarPremium] Starting initialization...');

        // Initialize components
        window.kitaSidebar = new KitaSidebarPremium();
        window.mobileDrawer = new MobileDrawerManager();
        window.commandPalette = new CommandPalette();
        window.keyboardShortcuts = new KeyboardShortcuts();
        window.badgeUpdater = new BadgeUpdater();

        console.log('[SidebarPremium] ✅ All components initialized');
    }

    // ========================================
    // 7. GLOBAL UTILITIES
    // ========================================

    // Toggle mobile drawer (called from HTML)
    window.toggleMobileDrawer = function() {
        if (window.mobileDrawer) {
            if (window.mobileDrawer.isOpen()) {
                window.mobileDrawer.close();
            } else {
                window.mobileDrawer.open();
            }
        }
    };

    // Open command palette (called from HTML)
    window.openCommandPalette = function() {
        if (window.commandPalette) {
            window.commandPalette.open();
        }
    };

    // Update badge counts (called from other scripts)
    window.updateSidebarBadges = function() {
        if (window.kitaSidebar) {
            window.kitaSidebar.updateBadgeCounts();
        }
    };

})();
