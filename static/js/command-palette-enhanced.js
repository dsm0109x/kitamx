/**
 * COMMAND PALETTE ENHANCED - v2.0
 * =================================
 *
 * Mejoras implementadas:
 * ✅ Fix memory leak en event listeners
 * ✅ Focus trap WCAG compliant
 * ✅ ARIA completo para screen readers
 * ✅ Fuzzy search real con scoring
 * ✅ Debounce optimizado
 * ✅ Búsqueda dinámica de links/invoices
 * ✅ Integración con detail panel
 *
 * @version 2.0.0
 * @created 2025-01-13
 */

'use strict';

class CommandPaletteEnhanced {
    constructor() {
        this.palette = null;
        this.input = null;
        this.results = null;
        this.overlay = null;
        this.isOpen = false;
        this.selectedIndex = 0;
        this.currentResults = [];  // ✅ Track current results for proper indexing

        // ✅ Focus trap elements
        this.focusableElements = null;
        this.firstFocusable = null;
        this.lastFocusable = null;

        // ✅ Debounce timers
        this.searchDebounceTimer = null;
        this.dynamicSearchTimer = null;

        // ✅ Search request tracking (to ignore stale results)
        this.searchRequestId = 0;
        this.isSearching = false;

        // ✅ Cache de resultados dinámicos (en memoria)
        this.searchCache = new Map();
        this.cacheTimeout = 60000; // 1 minuto

        // Static commands registry
        this.staticCommands = this.getStaticCommands();

        this.init();
    }

    init() {
        console.log('[CommandPalette] Initializing enhanced version...');

        // Create palette HTML with ARIA
        this.createPalette();

        // Bind keyboard shortcut
        this.bindGlobalShortcuts();

        console.log('[CommandPalette] ✅ Enhanced palette initialized');
    }

    getStaticCommands() {
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
                    } else {
                        console.warn('showCreateLinkModal no disponible');
                    }
                },
                category: 'Acciones Rápidas',
                keywords: ['crear', 'nuevo', 'link', 'pago', 'cobro']
            },
            {
                id: 'new-invoice',
                title: 'Nueva Factura',
                subtitle: 'Generar CFDI manualmente',
                icon: 'iconoir-page',
                action: () => window.location.href = '/facturas/crear/',  // 🇪🇸 Migrado
                category: 'Acciones Rápidas',
                keywords: ['nueva', 'factura', 'cfdi', 'crear']
            },

            // Navigation
            {
                id: 'nav-dashboard',
                title: 'Ir a Dashboard',
                subtitle: 'Vista general',
                icon: 'iconoir-dashboard',
                shortcut: 'D',
                action: () => window.location.href = '/panel/',
                category: 'Navegación',
                keywords: ['dashboard', 'inicio', 'home', 'vista']
            },
            {
                id: 'nav-links',
                title: 'Ir a Links',
                subtitle: 'Gestiona tus links de pago',
                icon: 'iconoir-link',
                shortcut: 'L',
                action: () => window.location.href = '/enlaces/',
                category: 'Navegación',
                keywords: ['links', 'pagos', 'cobros']
            },
            {
                id: 'nav-invoices',
                title: 'Ir a Facturación',
                subtitle: 'CFDIs y timbrado',
                icon: 'iconoir-page',
                shortcut: 'I',
                action: () => window.location.href = '/facturas/',
                category: 'Navegación',
                keywords: ['facturas', 'cfdi', 'timbrado']
            },
            {
                id: 'nav-ia',
                title: 'Ir a IA',
                subtitle: 'Asistente inteligente',
                icon: 'iconoir-brain',
                action: () => window.location.href = '/ia/',
                category: 'Navegación',
                keywords: ['ia', 'asistente', 'inteligencia', 'artificial']
            },
            {
                id: 'nav-settings',
                title: 'Ir a Mi Negocio',
                subtitle: 'Configuración fiscal',
                icon: 'iconoir-shop',
                shortcut: 'S',
                action: () => window.location.href = '/negocio/',
                category: 'Navegación',
                keywords: ['negocio', 'configuracion', 'fiscal', 'ajustes', 'preferencias']
            },

            // Account
            {
                id: 'edit-profile',
                title: 'Editar Mi Perfil',
                subtitle: 'Datos personales',
                icon: 'iconoir-user',
                action: () => window.location.href = '/cuenta/',
                category: 'Cuenta',
                keywords: ['perfil', 'usuario', 'datos', 'personales']
            },
            {
                id: 'subscription',
                title: 'Ver Suscripción',
                subtitle: 'Plan y facturación',
                icon: 'iconoir-credit-card',
                action: () => window.location.href = '/suscripcion/',  // 🇪🇸 Migrado
                category: 'Cuenta',
                keywords: ['suscripcion', 'plan', 'pago', 'facturacion']
            },

            // Account
            {
                id: 'logout',
                title: 'Cerrar Sesión',
                subtitle: 'Salir de tu cuenta',
                icon: 'iconoir-log-out',
                action: () => window.location.href = '/accounts/logout/',
                category: 'Cuenta',
                keywords: ['cerrar', 'salir', 'logout']
            }
        ];
    }

    createPalette() {
        // ✅ ARIA completo para accesibilidad
        const html = `
            <div class="command-palette-overlay"
                 id="commandPaletteOverlay"
                 role="dialog"
                 aria-modal="true"
                 aria-labelledby="commandPaletteTitle">
                <div class="command-palette"
                     id="commandPalette"
                     role="presentation">
                    <div class="command-palette-header">
                        <h2 id="commandPaletteTitle" class="visually-hidden">
                            Búsqueda Rápida de Comandos y Contenido
                        </h2>
                        <input type="text"
                               class="command-palette-input"
                               id="commandPaletteInput"
                               role="combobox"
                               aria-expanded="true"
                               aria-controls="commandPaletteResults"
                               aria-autocomplete="list"
                               aria-activedescendant=""
                               placeholder="Buscar comandos, links, facturas..."
                               autocomplete="off"
                               spellcheck="false">
                    </div>
                    <div class="command-palette-results"
                         id="commandPaletteResults"
                         role="listbox"
                         aria-live="polite"
                         aria-atomic="false">
                        <!-- Results will be injected here -->
                    </div>
                    <div class="command-palette-footer">
                        <div class="palette-hint" role="status" aria-live="off">
                            <kbd aria-label="Flecha arriba o abajo">↑↓</kbd> Navegar
                            <kbd aria-label="Enter">Enter</kbd> Ejecutar
                            <kbd aria-label="Escape">Esc</kbd> Cerrar
                        </div>
                        <div class="palette-results-count" id="paletteResultsCount" role="status" aria-live="polite">
                            <!-- Result count will be updated here -->
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
        this.resultsCount = document.getElementById('paletteResultsCount');

        // Bind palette events
        this.bindPaletteEvents();
    }

    bindGlobalShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Cmd+K or Ctrl+K
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }

            // Esc to close (solo si está abierto)
            if (e.key === 'Escape' && this.isOpen) {
                e.preventDefault();
                this.close();
            }
        });
    }

    bindPaletteEvents() {
        // ✅ Input search con debounce
        this.input.addEventListener('input', (e) => {
            const query = e.target.value;
            this.searchDebounced(query);
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
                case 'Tab':
                    // ✅ Focus trap handling
                    this.handleTabKey(e);
                    break;
            }
        });

        // ✅ Event delegation para clicks (NO memory leak)
        this.results.addEventListener('click', (e) => {
            const item = e.target.closest('.command-item');
            if (item) {
                const index = parseInt(item.dataset.index);
                if (!isNaN(index)) {
                    this.selectedIndex = index;
                    this.executeSelected();
                }
            }
        });

        // Close en overlay click
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });
    }

    // ✅ Debounced search
    searchDebounced(query) {
        clearTimeout(this.searchDebounceTimer);

        this.searchDebounceTimer = setTimeout(() => {
            this.search(query);
        }, 300);  // 300ms debounce
    }

    async search(query) {
        const trimmedQuery = query.trim();

        // Empty query: show all static commands
        if (!trimmedQuery) {
            this.isSearching = false;
            this.currentResults = this.staticCommands;
            this.selectedIndex = 0;
            this.renderResults(this.currentResults);
            return;
        }

        // ✅ Fuzzy search en comandos estáticos
        const staticResults = this.searchStaticCommands(trimmedQuery);

        // ✅ Búsqueda dinámica si query >= 2 chars
        if (trimmedQuery.length >= 2) {
            // Show loading state immediately
            this.isSearching = true;
            this.currentResults = staticResults;
            this.renderResults(this.currentResults, true); // Show loading
            this.updateFooter(); // Update to "Buscando..."

            try {
                const dynamicResults = await this.searchDynamicContent(trimmedQuery);
                this.isSearching = false;
                this.currentResults = [...staticResults, ...dynamicResults];
            } catch (error) {
                console.error('[CommandPalette] Dynamic search error:', error);
                this.isSearching = false;
                this.currentResults = staticResults;
                // Show error toast if available
                if (typeof showToast === 'function') {
                    showToast('Error en búsqueda. Intenta nuevamente.', 'error');
                }
            }
        } else {
            this.isSearching = false;
            this.currentResults = staticResults;
        }

        // ✅ Mantener selectedIndex válido
        if (this.selectedIndex >= this.currentResults.length) {
            this.selectedIndex = Math.max(0, this.currentResults.length - 1);
        }

        // Render final results (after search completes)
        this.renderResults(this.currentResults);
        this.updateFooter(); // Update result count

        // Analytics
        this.trackEvent('palette_search', {
            query: trimmedQuery,
            results: this.currentResults.length
        });
    }

    // ✅ Fuzzy search real con scoring
    searchStaticCommands(query) {
        const lowerQuery = query.toLowerCase();

        const scored = this.staticCommands.map(cmd => {
            const score = this.fuzzyScore(lowerQuery, cmd);
            return { ...cmd, score };
        }).filter(cmd => cmd.score > 0);

        // Ordenar por score descendente
        scored.sort((a, b) => b.score - a.score);

        return scored;
    }

    fuzzyScore(query, command) {
        const lowerTitle = command.title.toLowerCase();
        const lowerSubtitle = command.subtitle.toLowerCase();
        const keywords = command.keywords || [];

        let score = 0;

        // Exact match en title: máximo score
        if (lowerTitle === query) {
            score += 1000;
        }

        // Starts with en title: muy alto score
        if (lowerTitle.startsWith(query)) {
            score += 500;
        }

        // Contains en title: alto score
        if (lowerTitle.includes(query)) {
            score += 200;
        }

        // Fuzzy match en title
        if (this.fuzzyMatch(query, lowerTitle)) {
            score += 100;
        }

        // Contains en subtitle: medio score
        if (lowerSubtitle.includes(query)) {
            score += 50;
        }

        // Match en keywords
        for (const keyword of keywords) {
            if (keyword.includes(query)) {
                score += 30;
            }
        }

        // Bonus por posición temprana
        const position = lowerTitle.indexOf(query);
        if (position >= 0) {
            score += Math.max(0, 50 - position * 2);
        }

        return score;
    }

    fuzzyMatch(query, text) {
        // Convert query to regex pattern: "crlink" -> "c.*r.*l.*i.*n.*k"
        const pattern = query.split('').join('.*');
        const regex = new RegExp(pattern, 'i');
        return regex.test(text);
    }

    // ✅ Búsqueda dinámica con cache
    async searchDynamicContent(query) {
        // Check cache first
        const cacheKey = query.toLowerCase();
        if (this.searchCache.has(cacheKey)) {
            const cached = this.searchCache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                console.log('[CommandPalette] Using cached results for:', query);
                return cached.results;
            } else {
                this.searchCache.delete(cacheKey);
            }
        }

        // Increment request ID to track this specific request
        this.searchRequestId++;
        const currentRequestId = this.searchRequestId;

        try {
            const response = await fetch(
                `/panel/api/buscar/?q=${encodeURIComponent(query)}`  // 🇪🇸 Migrado
            );

            // Check if this request is still the latest
            if (currentRequestId !== this.searchRequestId) {
                console.log('[CommandPalette] Ignoring stale search results for:', query);
                return []; // Ignore stale results
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Search failed');
            }

            // Transform API results to command format
            const results = [
                ...this.transformLinks(data.links || []),
                ...this.transformInvoices(data.invoices || [])
            ];

            // Cache results
            this.searchCache.set(cacheKey, {
                results,
                timestamp: Date.now()
            });

            return results;

        } catch (error) {
            console.error('[CommandPalette] Search error:', error);
            return [];
        }
    }

    transformLinks(links) {
        return links.map(link => ({
            id: `link-${link.id}`,
            title: link.title,
            subtitle: this.formatLinkSubtitle(link),
            subtitleHtml: this.formatLinkSubtitleWithBadge(link),  // ✅ NEW: HTML con badge
            icon: 'iconoir-link',
            category: 'Links de Pago',
            action: () => this.openLinkDetail(link.id),
            meta: {
                type: 'link',
                status: link.status,
                amount: link.amount,
                created_at: link.created_at
            }
        }));
    }

    transformInvoices(invoices) {
        return invoices.map(invoice => {
            // IMPORTANT: Always use ID (PK) for detail panel
            // The endpoint /panel/detalle/invoice/{id}/ expects the PK, not UUID
            const invoiceId = invoice.id;

            return {
                id: `invoice-${invoiceId}`,
                title: `Factura ${invoice.serie_folio}`,
                subtitle: this.formatInvoiceSubtitle(invoice),
                subtitleHtml: this.formatInvoiceSubtitleWithBadge(invoice),  // ✅ NEW: HTML con badge
                icon: 'iconoir-page',
                category: 'Facturas',
                action: () => this.openInvoiceDetail(invoiceId),
                meta: {
                    type: 'invoice',
                    status: invoice.status,
                    total: invoice.total,
                    uuid: invoice.uuid,
                    pk_id: invoice.id,
                    stamped_at: invoice.stamped_at
                }
            };
        });
    }

    formatLinkSubtitle(link) {
        const parts = [];

        if (link.customer_name) {
            parts.push(link.customer_name);
        } else if (link.customer_email) {
            parts.push(link.customer_email);
        } else {
            parts.push('Sin cliente');
        }

        parts.push(`$${parseFloat(link.amount).toFixed(2)} MXN`);

        if (link.status) {
            const statusLabels = {
                'active': '🟢 Activo',
                'paid': '✅ Pagado',
                'expired': '⏱️ Expirado',
                'cancelled': '❌ Cancelado'
            };
            parts.push(statusLabels[link.status] || link.status);
        }

        return parts.join(' • ');
    }

    // ✅ NEW: Format con badges HTML y más metadata
    formatLinkSubtitleWithBadge(link) {
        const parts = [];

        // Customer
        if (link.customer_name) {
            parts.push(link.customer_name);
        } else if (link.customer_email) {
            parts.push(link.customer_email);
        } else {
            parts.push('<span style="color: #9ca3af;">Sin cliente</span>');
        }

        // Amount
        parts.push(`<strong>$${parseFloat(link.amount).toFixed(2)} MXN</strong>`);

        // Date (relative time)
        if (link.created_at) {
            const timeAgo = this.getRelativeTime(link.created_at);
            parts.push(`<span style="color: #9ca3af;">${timeAgo}</span>`);
        }

        const subtitle = parts.join(' • ');

        // Status badge
        if (link.status) {
            const badges = {
                'active': '<span class="command-badge badge-success">Activo</span>',
                'paid': '<span class="command-badge badge-info">Pagado</span>',
                'expired': '<span class="command-badge badge-warning">Expirado</span>',
                'cancelled': '<span class="command-badge badge-danger">Cancelado</span>'
            };
            const badge = badges[link.status] || `<span class="command-badge">${link.status}</span>`;
            return subtitle + ' ' + badge;
        }

        return subtitle;
    }

    formatInvoiceSubtitle(invoice) {
        const parts = [];

        if (invoice.customer_name) {
            parts.push(invoice.customer_name);
        }

        if (invoice.total) {
            parts.push(`$${parseFloat(invoice.total).toFixed(2)} MXN`);
        }

        if (invoice.status) {
            const statusLabels = {
                'draft': '📝 Borrador',
                'stamped': '✅ Timbrada',
                'cancelled': '❌ Cancelada'
            };
            parts.push(statusLabels[invoice.status] || invoice.status);
        }

        return parts.join(' • ');
    }

    // ✅ NEW: Format con badges HTML y más metadata
    formatInvoiceSubtitleWithBadge(invoice) {
        const parts = [];

        // Customer name
        if (invoice.customer_name) {
            parts.push(invoice.customer_name);
        }

        // Customer RFC
        if (invoice.customer_rfc) {
            parts.push(`<span style="font-family: 'SF Mono', monospace; color: #6b7280;">${invoice.customer_rfc}</span>`);
        }

        // Amount
        if (invoice.total) {
            parts.push(`<strong>$${parseFloat(invoice.total).toFixed(2)} MXN</strong>`);
        }

        // Date (relative time)
        if (invoice.stamped_at) {
            const timeAgo = this.getRelativeTime(invoice.stamped_at);
            parts.push(`<span style="color: #9ca3af;">Timbrada ${timeAgo}</span>`);
        }

        const subtitle = parts.join(' • ');

        // Status badge
        if (invoice.status) {
            const badges = {
                'draft': '<span class="command-badge badge-secondary">Borrador</span>',
                'stamped': '<span class="command-badge badge-success">Timbrada</span>',
                'sent': '<span class="command-badge badge-info">Enviada</span>',
                'cancelled': '<span class="command-badge badge-danger">Cancelada</span>',
                'error': '<span class="command-badge badge-warning">Error</span>'
            };
            const badge = badges[invoice.status] || `<span class="command-badge">${invoice.status}</span>`;
            return subtitle + ' ' + badge;
        }

        return subtitle;
    }

    // ✅ NEW: Relative time helper
    getRelativeTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'ahora';
        if (diffMins < 60) return `hace ${diffMins}min`;
        if (diffHours < 24) return `hace ${diffHours}h`;
        if (diffDays < 7) return `hace ${diffDays}d`;
        if (diffDays < 30) return `hace ${Math.floor(diffDays / 7)}sem`;
        return date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short' });
    }

    openLinkDetail(linkId) {
        console.log('[CommandPalette] Opening link detail:', linkId);
        this.close();

        // Usar función global del dashboard
        if (typeof showDetailPanel === 'function') {
            showDetailPanel('link', linkId);
        } else {
            // Fallback: navegar a la página de links
            window.location.href = `/enlaces/?highlight=${linkId}`;
        }
    }

    openInvoiceDetail(invoiceId) {
        console.log('[CommandPalette] Opening invoice detail panel:', invoiceId);

        if (!invoiceId) {
            console.error('[CommandPalette] Invalid invoice ID');
            if (typeof showToast === 'function') {
                showToast('Error: ID de factura inválido', 'error');
            }
            return;
        }

        this.close();

        // Abrir detail panel lateral (igual que links)
        if (typeof showDetailPanel === 'function') {
            showDetailPanel('invoice', invoiceId);
        } else {
            // Fallback: navegar a la página de facturas
            console.warn('[CommandPalette] showDetailPanel not available, navigating to invoices page');
            window.location.href = `/facturas/?highlight=${invoiceId}`;  // 🇪🇸 Migrado
        }
    }

    renderResults(commands, showLoading = false) {
        // Clear previous results
        this.results.innerHTML = '';

        // Show loading indicator (while searching)
        if (showLoading && this.isSearching) {
            this.results.innerHTML = `
                <div class="command-loading" role="status" aria-live="polite">
                    <div class="loading-spinner"></div>
                    <p>Buscando links y facturas...</p>
                </div>
            `;
            return; // Don't render results yet
        }

        if (commands.length === 0 && !this.isSearching) {
            const query = this.input.value.trim();
            let message = 'No se encontraron resultados';
            let hint = '';

            if (!query) {
                message = 'Escribe para buscar';
                hint = 'Comandos, links, facturas...';
            } else if (query.length < 2) {
                message = 'Sigue escribiendo';
                hint = 'Mínimo 2 caracteres para buscar';
            } else {
                message = 'Sin resultados';
                hint = `No se encontró nada para "${query}"`;
            }

            this.results.innerHTML = `
                <div class="command-empty" role="status">
                    <i class="iconoir-search" aria-hidden="true"></i>
                    <p class="empty-title">${this.escapeHtml(message)}</p>
                    <p class="empty-hint">${this.escapeHtml(hint)}</p>
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
        let globalIndex = 0;

        Object.keys(grouped).forEach(category => {
            html += `
                <div class="command-category">
                    <div class="command-category-title">${this.escapeHtml(category)}</div>
            `;

            grouped[category].forEach((cmd) => {
                const isSelected = globalIndex === this.selectedIndex;
                const optionId = `command-option-${globalIndex}`;

                // ✅ Highlight query in title
                const titleHtml = this.highlightQuery(cmd.title, this.input.value);

                // ✅ Use subtitleHtml if available (with badges and highlight)
                let subtitleContent;
                if (cmd.subtitleHtml) {
                    // Apply highlight to HTML subtitle too
                    subtitleContent = this.highlightQueryInHtml(cmd.subtitleHtml, this.input.value);
                } else {
                    subtitleContent = this.highlightQuery(cmd.subtitle, this.input.value);
                }

                html += `
                    <button class="command-item ${isSelected ? 'selected' : ''}"
                            data-index="${globalIndex}"
                            data-command-id="${cmd.id}"
                            id="${optionId}"
                            role="option"
                            aria-selected="${isSelected}">
                        <i class="${cmd.icon} command-icon" aria-hidden="true"></i>
                        <div class="command-content">
                            <div class="command-title">${titleHtml}</div>
                            <div class="command-subtitle">${subtitleContent}</div>
                        </div>
                        ${cmd.shortcut ? `<kbd class="command-shortcut" aria-label="Atajo: ${cmd.shortcut}">${this.escapeHtml(cmd.shortcut)}</kbd>` : ''}
                    </button>
                `;

                globalIndex++;
            });

            html += `</div>`;
        });

        this.results.innerHTML = html;

        // ✅ Update ARIA activedescendant
        this.updateActiveDescendant();
    }

    // ✅ Update ARIA activedescendant para screen readers
    updateActiveDescendant() {
        const selectedItem = this.results.querySelector('.command-item.selected');
        if (selectedItem) {
            this.input.setAttribute('aria-activedescendant', selectedItem.id);
        } else {
            this.input.setAttribute('aria-activedescendant', '');
        }
    }

    selectNext() {
        if (this.currentResults.length === 0) return;

        this.selectedIndex = (this.selectedIndex + 1) % this.currentResults.length;
        this.updateSelection();
    }

    selectPrevious() {
        if (this.currentResults.length === 0) return;

        this.selectedIndex = this.selectedIndex === 0
            ? this.currentResults.length - 1
            : this.selectedIndex - 1;
        this.updateSelection();
    }

    updateSelection() {
        const items = this.results.querySelectorAll('.command-item');

        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
                item.setAttribute('aria-selected', 'true');
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('selected');
                item.setAttribute('aria-selected', 'false');
            }
        });

        // ✅ Update ARIA activedescendant
        this.updateActiveDescendant();
    }

    executeSelected() {
        if (this.currentResults.length === 0) return;

        const command = this.currentResults[this.selectedIndex];

        if (command && command.action) {
            this.close();

            // Execute action
            try {
                command.action();
            } catch (error) {
                console.error('[CommandPalette] Error executing command:', error);
                if (typeof showToast === 'function') {
                    showToast('Error ejecutando comando', 'error');
                }
            }

            // Analytics
            this.trackEvent('command_execute', {
                command_id: command.id,
                command_title: command.title,
                command_type: command.meta?.type || 'static'
            });
        }
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

        // Show all static commands initially
        this.currentResults = this.staticCommands;
        this.renderResults(this.currentResults);

        // ✅ Setup focus trap
        this.setupFocusTrap();

        // Focus input
        setTimeout(() => {
            this.input.focus();
        }, 100);

        // Prevent body scroll
        document.body.style.overflow = 'hidden';

        // Analytics
        this.trackEvent('palette_open');
    }

    close() {
        this.overlay.classList.remove('show');
        this.isOpen = false;
        this.input.value = '';
        this.selectedIndex = 0;
        this.currentResults = [];

        // Invalidate any pending search requests
        this.searchRequestId++;

        // Clear debounce timers
        clearTimeout(this.searchDebounceTimer);
        clearTimeout(this.dynamicSearchTimer);

        // Restore body scroll
        document.body.style.overflow = '';

        // Remove focus trap
        this.removeFocusTrap();

        // Analytics
        this.trackEvent('palette_close');
    }

    // ✅ Focus trap implementation
    setupFocusTrap() {
        this.focusableElements = this.palette.querySelectorAll(
            'button, input, [tabindex]:not([tabindex="-1"])'
        );

        if (this.focusableElements.length > 0) {
            this.firstFocusable = this.focusableElements[0];
            this.lastFocusable = this.focusableElements[this.focusableElements.length - 1];
        }
    }

    removeFocusTrap() {
        this.focusableElements = null;
        this.firstFocusable = null;
        this.lastFocusable = null;
    }

    handleTabKey(e) {
        if (!this.focusableElements || this.focusableElements.length === 0) return;

        if (e.shiftKey) {
            // Shift + Tab
            if (document.activeElement === this.firstFocusable) {
                e.preventDefault();
                this.lastFocusable.focus();
            }
        } else {
            // Tab
            if (document.activeElement === this.lastFocusable) {
                e.preventDefault();
                this.firstFocusable.focus();
            }
        }
    }

    // ✅ Update footer with result count
    updateFooter() {
        if (!this.resultsCount) return;

        const count = this.currentResults.length;
        const query = this.input.value.trim();

        if (!query) {
            this.resultsCount.textContent = '';
        } else if (this.isSearching) {
            this.resultsCount.textContent = 'Buscando...';
            this.resultsCount.className = 'palette-results-count searching';
        } else if (count === 0) {
            this.resultsCount.textContent = 'Sin resultados';
            this.resultsCount.className = 'palette-results-count empty';
        } else {
            this.resultsCount.textContent = `${count} resultado${count !== 1 ? 's' : ''}`;
            this.resultsCount.className = 'palette-results-count';
        }
    }

    // ✅ Highlight query in text (Google-style)
    highlightQuery(text, query) {
        if (!query || !query.trim() || !text) {
            return this.escapeHtml(text || '');
        }

        const escapedText = this.escapeHtml(text);
        const trimmedQuery = query.trim();

        // Create regex for case-insensitive match
        // Escape special regex characters in query
        const escapedQuery = trimmedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedQuery})`, 'gi');

        // Replace matches with highlighted version
        return escapedText.replace(regex, '<mark class="query-highlight">$1</mark>');
    }

    // ✅ Highlight query in HTML content (preserving existing tags)
    highlightQueryInHtml(html, query) {
        if (!query || !query.trim() || !html) {
            return html;
        }

        const trimmedQuery = query.trim();
        const escapedQuery = trimmedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedQuery})`, 'gi');

        // Apply highlight to text nodes only (preserve HTML tags)
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        const highlightTextNodes = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent;
                if (regex.test(text)) {
                    const span = document.createElement('span');
                    span.innerHTML = text.replace(regex, '<mark class="query-highlight">$1</mark>');
                    node.replaceWith(span);
                }
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                // Don't highlight inside badges, marks, or code
                if (!node.matches('.command-badge, mark, code, kbd')) {
                    Array.from(node.childNodes).forEach(child => highlightTextNodes(child));
                }
            }
        };

        highlightTextNodes(tempDiv);
        return tempDiv.innerHTML;
    }

    // ✅ XSS prevention
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
// INITIALIZATION
// ========================================

// Initialize enhanced command palette
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.commandPaletteEnhanced = new CommandPaletteEnhanced();
    });
} else {
    window.commandPaletteEnhanced = new CommandPaletteEnhanced();
}

// ========================================
// GLOBAL UTILITIES
// ========================================

// Open command palette (called from HTML)
window.openCommandPalette = function() {
    if (window.commandPaletteEnhanced) {
        window.commandPaletteEnhanced.open();
    }
};

// Toggle command palette
window.toggleCommandPalette = function() {
    if (window.commandPaletteEnhanced) {
        window.commandPaletteEnhanced.toggle();
    }
};
