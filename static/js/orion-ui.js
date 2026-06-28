/**
 * orion-ui.js — Main JavaScript for Orion ERP
 * Handles: dark mode, compact mode, toasts, command palette,
 *          keyboard shortcuts, sidebar, search, confirm dialogs,
 *          active nav highlighting, and Django message conversion.
 */

'use strict';

/* ============================================================
   1. DARK MODE
   ============================================================ */
const OrionTheme = {
  STORAGE_KEY: 'orion-theme',

  init() {
    const saved = localStorage.getItem(this.STORAGE_KEY) || 'system';
    this.setTheme(saved);
  },

  toggle() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    this.setTheme(next);
    this._updateToggleIcon(next);
  },

  setTheme(theme) {
    let resolved = theme;
    if (theme === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', resolved);
    document.documentElement.setAttribute('data-bs-theme', resolved);
    localStorage.setItem(this.STORAGE_KEY, theme);
    this._updateToggleIcon(resolved);
  },

  _updateToggleIcon(resolved) {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    const icon = btn.querySelector('i');
    if (!icon) return;
    if (resolved === 'dark') {
      icon.className = icon.className.replace(/bi-\S+/, 'bi-sun');
    } else {
      icon.className = icon.className.replace(/bi-\S+/, 'bi-moon-stars');
    }
  }
};

/* ============================================================
   2. COMPACT MODE
   ============================================================ */
const OrionCompact = {
  STORAGE_KEY: 'orion-compact',

  init() {
    const saved = localStorage.getItem(this.STORAGE_KEY) === 'true';
    if (saved) {
      document.body.classList.add('compact-mode');
      this._syncBadge(true);
    }
  },

  toggle() {
    const isCompact = document.body.classList.toggle('compact-mode');
    localStorage.setItem(this.STORAGE_KEY, isCompact ? 'true' : 'false');
    this._syncBadge(isCompact);
    OrionToast && OrionToast.info(isCompact ? 'Mode compact activé' : 'Mode compact désactivé');
  },

  _syncBadge(isCompact) {
    const badge = document.getElementById('compactBadge');
    if (badge) badge.style.display = isCompact ? 'inline-flex' : 'none';
  }
};

/* ============================================================
   3. TOAST SYSTEM
   ============================================================ */
const OrionToast = {
  _container: null,

  _getContainer() {
    if (!this._container) {
      this._container = document.createElement('div');
      this._container.id = 'orionToastContainer';
      this._container.style.cssText =
        'position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:.5rem;';
      document.body.appendChild(this._container);
    }
    return this._container;
  },

  show(message, type = 'success', duration = 4000) {
    const icons = {
      success: 'bi-check-circle-fill',
      error:   'bi-x-circle-fill',
      warning: 'bi-exclamation-triangle-fill',
      info:    'bi-info-circle-fill'
    };
    const icon = icons[type] || 'bi-info-circle-fill';

    const toast = document.createElement('div');
    toast.className = `orion-toast orion-toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <i class="bi ${icon} orion-toast-icon"></i>
      <span class="orion-toast-message">${message}</span>
      <button class="orion-toast-close" aria-label="Fermer">
        <i class="bi bi-x-lg"></i>
      </button>`;

    const container = this._getContainer();
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => toast.classList.add('orion-toast-show'));

    const remove = () => {
      toast.classList.remove('orion-toast-show');
      toast.classList.add('orion-toast-hide');
      setTimeout(() => toast.remove(), 300);
    };

    const timer = setTimeout(remove, duration);

    toast.querySelector('.orion-toast-close').addEventListener('click', () => {
      clearTimeout(timer);
      remove();
    });
  },

  success(msg)  { this.show(msg, 'success'); },
  error(msg)    { this.show(msg, 'error', 6000); },
  warning(msg)  { this.show(msg, 'warning'); },
  info(msg)     { this.show(msg, 'info'); }
};

window.OrionToast = OrionToast;

/* ============================================================
   4. COMMAND PALETTE (Ctrl+K)
   ============================================================ */
const OrionCommandPalette = {
  _selectedIndex: 0,
  _filteredCommands: [],

  commands: [
    { label: 'Nouveau client',   icon: 'bi-person-plus',       url: '/crm/clients/nouveau/',    shortcut: 'N C', group: 'Créer' },
    { label: 'Nouveau devis',    icon: 'bi-file-earmark-plus', url: '/sales/devis/nouveau/',    shortcut: 'N D', group: 'Créer' },
    { label: 'Nouvelle facture', icon: 'bi-receipt',           url: '/sales/factures/nouvelle/', shortcut: 'N F', group: 'Créer' },
    { label: 'Nouveau chantier', icon: 'bi-building-gear',     url: '/btp/chantiers/nouveau/',              group: 'Créer' },
    { label: 'Nouveau produit',  icon: 'bi-box',               url: '/inventory/',                           group: 'Créer' },
    { label: 'Tableau de bord',  icon: 'bi-speedometer2',      url: '/dashboard/',              shortcut: 'G D', group: 'Navigation' },
    { label: 'Clients',          icon: 'bi-people',            url: '/crm/clients/',            shortcut: 'G C', group: 'Navigation' },
    { label: 'Factures',         icon: 'bi-receipt',           url: '/sales/factures/',         shortcut: 'G F', group: 'Navigation' },
    { label: 'Chantiers',        icon: 'bi-building-gear',     url: '/btp/chantiers/',          shortcut: 'G P', group: 'Navigation' },
    { label: 'Documents',        icon: 'bi-folder',            url: '/documents/',                           group: 'Navigation' },
    { label: 'Reporting',        icon: 'bi-bar-chart',         url: '/bi/',                                  group: 'Navigation' },
    { label: 'Recherche globale',icon: 'bi-search',            url: '/dashboard/search/',                    group: 'Outils' },
  ],

  open() {
    const palette = document.getElementById('orionCommandPalette');
    if (!palette) return;
    palette.style.display = 'flex';
    const input = document.getElementById('ocpInput');
    if (input) {
      input.value = '';
      input.focus();
    }
    this.filter('');
    document.body.style.overflow = 'hidden';
  },

  close() {
    const palette = document.getElementById('orionCommandPalette');
    if (!palette) return;
    palette.style.display = 'none';
    document.body.style.overflow = '';
  },

  filter(query) {
    const q = query.trim().toLowerCase();
    this._filteredCommands = q
      ? this.commands.filter(c =>
          c.label.toLowerCase().includes(q) ||
          (c.group && c.group.toLowerCase().includes(q))
        )
      : [...this.commands];

    this._selectedIndex = 0;
    this._render();
  },

  _render() {
    const results = document.getElementById('ocpResults');
    if (!results) return;

    if (this._filteredCommands.length === 0) {
      results.innerHTML = '<div class="ocp-empty">Aucun résultat</div>';
      return;
    }

    // Group commands
    const groups = {};
    this._filteredCommands.forEach((cmd, idx) => {
      const g = cmd.group || 'Autres';
      if (!groups[g]) groups[g] = [];
      groups[g].push({ ...cmd, _idx: idx });
    });

    let html = '';
    for (const [groupName, cmds] of Object.entries(groups)) {
      html += `<div class="ocp-group-label">${groupName}</div>`;
      cmds.forEach(cmd => {
        const isActive = cmd._idx === this._selectedIndex ? ' ocp-item-active' : '';
        const shortcut = cmd.shortcut
          ? `<kbd class="ocp-shortcut">${cmd.shortcut}</kbd>`
          : '';
        html += `
          <div class="ocp-item${isActive}" data-idx="${cmd._idx}" data-url="${cmd.url}">
            <i class="bi ${cmd.icon} ocp-item-icon"></i>
            <span class="ocp-item-label">${cmd.label}</span>
            ${shortcut}
          </div>`;
      });
    }

    results.innerHTML = html;

    // Bind click events
    results.querySelectorAll('.ocp-item').forEach(el => {
      el.addEventListener('click', () => {
        this.navigate(el.dataset.url);
      });
      el.addEventListener('mouseenter', () => {
        this._selectedIndex = parseInt(el.dataset.idx, 10);
        this._highlightActive();
      });
    });
  },

  _highlightActive() {
    const results = document.getElementById('ocpResults');
    if (!results) return;
    results.querySelectorAll('.ocp-item').forEach(el => {
      el.classList.toggle('ocp-item-active', parseInt(el.dataset.idx, 10) === this._selectedIndex);
    });
    const active = results.querySelector('.ocp-item-active');
    if (active) active.scrollIntoView({ block: 'nearest' });
  },

  _moveSelection(delta) {
    const max = this._filteredCommands.length - 1;
    this._selectedIndex = Math.max(0, Math.min(max, this._selectedIndex + delta));
    this._highlightActive();
  },

  _confirmSelection() {
    const cmd = this._filteredCommands[this._selectedIndex];
    if (cmd) this.navigate(cmd.url);
  },

  navigate(url) {
    this.close();
    window.location.href = url;
  },

  init() {
    if (document.getElementById('orionCommandPalette')) return;

    const el = document.createElement('div');
    el.id = 'orionCommandPalette';
    el.className = 'orion-command-palette';
    el.style.display = 'none';
    el.innerHTML = `
      <div class="ocp-backdrop"></div>
      <div class="ocp-modal" role="dialog" aria-modal="true" aria-label="Palette de commandes">
        <div class="ocp-search">
          <i class="bi bi-search ocp-icon"></i>
          <input type="text" id="ocpInput" placeholder="Rechercher ou taper une commande..." autocomplete="off">
          <kbd>Esc</kbd>
        </div>
        <div id="ocpResults" class="ocp-results"></div>
      </div>`;
    document.body.appendChild(el);

    // Backdrop click closes
    el.querySelector('.ocp-backdrop').addEventListener('click', () => this.close());

    // Input events
    const input = el.querySelector('#ocpInput');
    input.addEventListener('input', e => this.filter(e.target.value));
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); this._moveSelection(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); this._moveSelection(-1); }
      else if (e.key === 'Enter')  { e.preventDefault(); this._confirmSelection(); }
      else if (e.key === 'Escape') { this.close(); }
    });
  }
};

/* ============================================================
   5. KEYBOARD SHORTCUTS
   ============================================================ */
const OrionKeyboard = {
  _pendingKey: null,
  _pendingTimer: null,

  _clearPending() {
    this._pendingKey = null;
    if (this._pendingTimer) {
      clearTimeout(this._pendingTimer);
      this._pendingTimer = null;
    }
  },

  init() {
    document.addEventListener('keydown', e => {
      const tag = document.activeElement ? document.activeElement.tagName : '';
      const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) ||
                      document.activeElement.isContentEditable;

      // Ctrl+K — command palette (always)
      if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        OrionCommandPalette.open();
        this._clearPending();
        return;
      }

      // Ctrl+S — submit active form
      if (e.ctrlKey && e.key === 's') {
        const form = document.activeElement
          ? document.activeElement.closest('form')
          : null;
        if (form) {
          e.preventDefault();
          form.requestSubmit ? form.requestSubmit() : form.submit();
        }
        return;
      }

      // Escape — close palette / modals
      if (e.key === 'Escape') {
        const palette = document.getElementById('orionCommandPalette');
        if (palette && palette.style.display !== 'none') {
          OrionCommandPalette.close();
          return;
        }
        // Close any open Bootstrap modal
        const modal = document.querySelector('.modal.show');
        if (modal && window.bootstrap) {
          const bsModal = bootstrap.Modal.getInstance(modal);
          if (bsModal) bsModal.hide();
        }
        return;
      }

      // Skip remaining shortcuts when inside an input
      if (isInput) return;

      // / — focus page search
      if (e.key === '/') {
        const searchInput = document.getElementById('globalSearch') ||
                            document.querySelector('input[type="search"]');
        if (searchInput) {
          e.preventDefault();
          searchInput.focus();
          searchInput.select();
        }
        return;
      }

      // Sequential shortcuts: G then D/C/F/P (1 second window)
      if (e.key === 'g' || e.key === 'G') {
        this._clearPending();
        this._pendingKey = 'g';
        this._pendingTimer = setTimeout(() => this._clearPending(), 1000);
        return;
      }

      if (this._pendingKey === 'g') {
        const navMap = {
          d: '/dashboard/',
          c: '/crm/clients/',
          f: '/sales/factures/',
          p: '/btp/chantiers/'
        };
        const dest = navMap[e.key.toLowerCase()];
        if (dest) {
          e.preventDefault();
          this._clearPending();
          window.location.href = dest;
        }
        return;
      }
    });
  }
};

/* ============================================================
   6. SIDEBAR BEHAVIOR
   ============================================================ */
const OrionSidebar = {
  STORAGE_KEY: 'orion-sidebar-compact',

  init() {
    const sidebar  = document.getElementById('erpSidebar');
    const overlay  = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggle');
    const closeBtn  = document.getElementById('sidebarClose');

    if (!sidebar) return;

    // Restore compact state on desktop
    if (localStorage.getItem(this.STORAGE_KEY) === 'true') {
      sidebar.classList.add('sidebar-compact');
    }

    const openMobile = () => {
      sidebar.classList.add('sidebar-open');
      if (overlay) overlay.classList.add('show');
      document.body.classList.add('sidebar-mobile-open');
    };

    const closeMobile = () => {
      sidebar.classList.remove('sidebar-open');
      if (overlay) overlay.classList.remove('show');
      document.body.classList.remove('sidebar-mobile-open');
    };

    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        if (window.innerWidth < 768) {
          openMobile();
        } else {
          this.toggleCompact();
        }
      });
    }

    if (closeBtn)  closeBtn.addEventListener('click', closeMobile);
    if (overlay)   overlay.addEventListener('click', closeMobile);

    // Close mobile sidebar on window resize to desktop
    window.addEventListener('resize', () => {
      if (window.innerWidth >= 768) closeMobile();
    });
  },

  toggleCompact() {
    const sidebar = document.getElementById('erpSidebar');
    if (!sidebar) return;
    const isCompact = sidebar.classList.toggle('sidebar-compact');
    localStorage.setItem(this.STORAGE_KEY, isCompact ? 'true' : 'false');
  }
};

/* ============================================================
   7. GLOBAL SEARCH INPUT
   ============================================================ */
const OrionSearch = {
  init() {
    const input = document.getElementById('globalSearch');
    if (!input) return;

    // Typing in global search opens command palette with the query
    input.addEventListener('input', e => {
      const val = e.target.value;
      if (val.length > 0) {
        OrionCommandPalette.open();
        const ocpInput = document.getElementById('ocpInput');
        if (ocpInput) {
          ocpInput.value = val;
          OrionCommandPalette.filter(val);
        }
        input.value = '';
      }
    });

    // Prevent form submit opening command palette if already handled
    const form = input.closest('form');
    if (form) {
      form.addEventListener('submit', e => {
        if (input.value.trim() === '') e.preventDefault();
      });
    }
  }
};

/* ============================================================
   8. CONVERT DJANGO MESSAGES TO TOASTS
   ============================================================ */
function convertDjangoMessages() {
  const typeMap = {
    success: 'success',
    error:   'error',
    danger:  'error',
    warning: 'warning',
    info:    'info',
    debug:   'info'
  };

  document.querySelectorAll('.erp-alert, .alert').forEach(el => {
    const text = el.textContent.trim();
    if (!text) { el.remove(); return; }

    let type = 'info';
    for (const [cls, toastType] of Object.entries(typeMap)) {
      if (el.classList.contains(`alert-${cls}`) || el.classList.contains(`erp-alert-${cls}`)) {
        type = toastType;
        break;
      }
    }

    OrionToast.show(text, type);
    el.remove();
  });
}

/* ============================================================
   9. CONFIRM DIALOGS
   ============================================================ */
const OrionConfirm = {
  _modalId: 'orionConfirmModal',

  show(message, onConfirm, options = {}) {
    const title       = options.title       || 'Confirmer';
    const confirmText = options.confirmText || 'Confirmer';
    const cancelText  = options.cancelText  || 'Annuler';
    const danger      = options.danger !== false;

    let modal = document.getElementById(this._modalId);
    if (!modal) {
      modal = document.createElement('div');
      modal.id = this._modalId;
      modal.className = 'modal fade';
      modal.setAttribute('tabindex', '-1');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('role', 'dialog');
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fermer"></button>
          </div>
          <div class="modal-body">
            <p>${message}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>
            <button type="button" class="btn btn-${danger ? 'danger' : 'primary'}" id="orionConfirmOk">${confirmText}</button>
          </div>
        </div>
      </div>`;

    const bsModal = window.bootstrap ? new bootstrap.Modal(modal) : null;
    if (bsModal) bsModal.show();

    const okBtn = modal.querySelector('#orionConfirmOk');
    okBtn.addEventListener('click', () => {
      if (bsModal) bsModal.hide();
      if (typeof onConfirm === 'function') onConfirm();
    });
  }
};

// Intercept data-confirm on links and forms
function initDataConfirm() {
  document.addEventListener('click', e => {
    const link = e.target.closest('a[data-confirm]');
    if (link) {
      e.preventDefault();
      const msg  = link.dataset.confirm;
      const href = link.href;
      OrionConfirm.show(msg, () => { window.location.href = href; }, { danger: true });
    }
  });

  document.addEventListener('submit', e => {
    const form = e.target.closest('form[data-confirm]');
    if (form && !form._confirmed) {
      e.preventDefault();
      const msg = form.dataset.confirm;
      OrionConfirm.show(msg, () => {
        form._confirmed = true;
        form.requestSubmit ? form.requestSubmit() : form.submit();
      }, { danger: true });
    }
  });
}

/* ============================================================
   10. ACTIVE NAV HIGHLIGHTING
   ============================================================ */
function highlightActiveNav() {
  const path = window.location.pathname;

  document.querySelectorAll('.nav-link, .sidebar-link, [data-nav-link]').forEach(link => {
    const href = link.getAttribute('href');
    if (!href || href === '#') return;

    // Exact match or path starts with href (prefix match, href must end with /)
    const isActive = path === href ||
                     (href.length > 1 && href.endsWith('/') && path.startsWith(href));

    if (isActive) {
      link.classList.add('active');
      // Expand parent collapse if inside one
      const collapse = link.closest('.collapse');
      if (collapse && window.bootstrap) {
        const bsCollapse = bootstrap.Collapse.getOrCreateInstance(collapse, { toggle: false });
        bsCollapse.show();
      }
      // Also mark parent nav-item
      const parentItem = link.closest('.nav-item');
      if (parentItem) parentItem.classList.add('active');
    }
  });
}

/* ============================================================
   10b. DRAWER PANEL
   ============================================================ */
const OrionDrawer = {
  open(id) {
    const drawer  = document.getElementById(id);
    const overlay = document.getElementById(id + 'Overlay');
    if (!drawer) return;
    drawer.classList.add('is-open');
    if (overlay) overlay.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    drawer.focus && drawer.focus();
  },

  close(id) {
    const drawer  = document.getElementById(id);
    const overlay = document.getElementById(id + 'Overlay');
    if (!drawer) return;
    drawer.classList.remove('is-open');
    if (overlay) overlay.classList.remove('is-open');
    document.body.style.overflow = '';
  },

  closeAll() {
    document.querySelectorAll('.orion-drawer.is-open').forEach(d => this.close(d.id));
  },

  /** Load remote content into the drawer body via fetch */
  async load(id, url, title) {
    if (title) {
      const titleEl = document.getElementById(id + 'Title');
      if (titleEl) titleEl.textContent = title;
    }
    const body = document.getElementById(id + 'Body');
    if (body) {
      body.innerHTML = `<div class="d-flex justify-content-center py-5"><div class="spinner-border text-secondary" role="status"></div></div>`;
    }
    this.open(id);
    try {
      const res  = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const html = await res.text();
      if (body) body.innerHTML = html;
    } catch (e) {
      if (body) body.innerHTML = `<div class="alert alert-danger m-3">Impossible de charger le contenu.</div>`;
    }
  },

  init() {
    // data-drawer-open="drawerId" on any element opens the drawer
    document.addEventListener('click', (e) => {
      const trigger = e.target.closest('[data-drawer-open]');
      if (trigger) {
        e.preventDefault();
        const id  = trigger.dataset.drawerOpen;
        const url = trigger.dataset.drawerUrl;
        const lbl = trigger.dataset.drawerTitle;
        url ? this.load(id, url, lbl) : this.open(id);
      }
    });
    // Close drawer on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.closeAll();
    });
  }
};
window.OrionDrawer = OrionDrawer;

/* ============================================================
   11. INIT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  OrionTheme.init();
  OrionCompact.init();
  OrionSidebar.init();
  OrionCommandPalette.init();
  OrionKeyboard.init();
  OrionSearch.init();
  OrionDrawer.init();
  initDataConfirm();
  highlightActiveNav();
  convertDjangoMessages();

  // Bind theme toggle button if present
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => OrionTheme.toggle());
  }

  // Bind compact toggle button if present
  const compactToggle = document.getElementById('compactToggle');
  if (compactToggle) {
    compactToggle.addEventListener('click', () => OrionCompact.toggle());
  }
});
