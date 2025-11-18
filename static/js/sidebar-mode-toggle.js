/**
 * SIDEBAR MODE TOGGLE - Switch entre diseños
 * ============================================
 *
 * Permite cambiar entre Ghost Mode, Glass Premium y Hybrid
 * con persistencia en localStorage.
 *
 * Uso:
 * SidebarModeToggle.setMode('ghost')
 * SidebarModeToggle.setMode('glass')
 * SidebarModeToggle.setMode('hybrid')
 *
 * @version 1.0
 * @created 2025-11-10
 */

class SidebarModeToggle {
    static STORAGE_KEY = 'kita_sidebar_mode';
    static MODES = ['ghost', 'glass', 'hybrid'];
    static DEFAULT_MODE = 'ghost';

    /**
     * Inicializa el toggle desde localStorage
     */
    static init() {
        const savedMode = this.getMode();
        this.applyMode(savedMode);

        console.log(`[SidebarToggle] Initialized with mode: ${savedMode}`);

        // Exponer globalmente para console testing
        window.SidebarModeToggle = this;
    }

    /**
     * Obtiene el modo guardado en localStorage
     */
    static getMode() {
        const saved = localStorage.getItem(this.STORAGE_KEY);
        return this.MODES.includes(saved) ? saved : this.DEFAULT_MODE;
    }

    /**
     * Cambia el modo del sidebar
     */
    static setMode(mode) {
        if (!this.MODES.includes(mode)) {
            console.error(`[SidebarToggle] Invalid mode: ${mode}`);
            return false;
        }

        // Guardar en localStorage
        localStorage.setItem(this.STORAGE_KEY, mode);

        // Aplicar
        this.applyMode(mode);

        console.log(`[SidebarToggle] Mode changed to: ${mode}`);
        return true;
    }

    /**
     * Aplica el modo al sidebar
     */
    static applyMode(mode) {
        const sidebar = document.getElementById('kitaSidebar');
        const mobileDrawer = document.getElementById('mobileSidebarDrawer');

        if (sidebar) {
            sidebar.setAttribute('data-sidebar-mode', mode);
        }

        if (mobileDrawer) {
            mobileDrawer.setAttribute('data-sidebar-mode', mode);
        }

        // Dispatch event para otros componentes
        window.dispatchEvent(new CustomEvent('sidebar-mode-changed', {
            detail: { mode }
        }));
    }

    /**
     * Toggle entre modos
     */
    static toggle() {
        const current = this.getMode();
        const currentIndex = this.MODES.indexOf(current);
        const nextIndex = (currentIndex + 1) % this.MODES.length;
        const nextMode = this.MODES[nextIndex];

        this.setMode(nextMode);

        // Show toast
        if (typeof showToast !== 'undefined') {
            const modeNames = {
                ghost: 'Ghost Mode (Transparente)',
                glass: 'Glass Premium (Blur)',
                hybrid: 'Hybrid (Gradiente sutil)'
            };
            showToast(`Sidebar: ${modeNames[nextMode]}`, 'info');
        }

        return nextMode;
    }

    /**
     * Reset al modo por defecto
     */
    static reset() {
        this.setMode(this.DEFAULT_MODE);
    }

    /**
     * Crea un botón toggle en el sidebar (para testing)
     */
    static createToggleButton() {
        const button = document.createElement('button');
        button.className = 'sidebar-mode-toggle-btn';
        button.innerHTML = `
            <i class="iconoir-color-picker"></i>
            <span>Cambiar diseño</span>
        `;
        button.style.cssText = `
            position: fixed;
            bottom: 1rem;
            left: 1rem;
            padding: 0.5rem 1rem;
            background: rgba(17, 24, 39, 0.9);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            transition: all 0.2s ease;
        `;

        button.addEventListener('click', () => {
            this.toggle();
        });

        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 6px 16px rgba(0, 0, 0, 0.3)';
        });

        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.2)';
        });

        document.body.appendChild(button);

        return button;
    }
}

// Auto-init on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        SidebarModeToggle.init();
    });
} else {
    SidebarModeToggle.init();
}

// Keyboard shortcut: Cmd/Ctrl + K + S (Sidebar mode)
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        // Esperar segunda tecla
        const handler = (e2) => {
            if (e2.key === 's') {
                e2.preventDefault();
                SidebarModeToggle.toggle();
            }
            document.removeEventListener('keydown', handler);
        };
        document.addEventListener('keydown', handler);
        setTimeout(() => document.removeEventListener('keydown', handler), 2000);
    }
});

// Console helpers
console.log(`
╔═══════════════════════════════════════════╗
║   KITA SIDEBAR MODE TOGGLE                ║
╠═══════════════════════════════════════════╣
║                                           ║
║  Comandos disponibles en consola:         ║
║                                           ║
║  SidebarModeToggle.setMode('ghost')       ║
║  SidebarModeToggle.setMode('glass')       ║
║  SidebarModeToggle.setMode('hybrid')      ║
║  SidebarModeToggle.toggle()               ║
║  SidebarModeToggle.createToggleButton()   ║
║                                           ║
║  Atajo: Cmd/Ctrl + K → S                  ║
║                                           ║
║  Modo actual: ${SidebarModeToggle.getMode().toUpperCase()}             ║
║                                           ║
╚═══════════════════════════════════════════╝
`);
