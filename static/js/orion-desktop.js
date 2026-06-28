/**
 * ORION ERP — Desktop JS
 * Sidebar, open-tabs, keyboard shortcuts, density, tooltips
 */
(function () {
  'use strict';

  /* ── Config ──────────────────────────────────────────────── */
  var STORAGE_TABS    = 'orion_open_tabs';
  var STORAGE_DENSITY = 'orion_density';
  var STORAGE_COMPACT = 'orion_sidebar_compact';
  var MAX_TABS = 12;

  /* ── Init ────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initSidebar();
    initOpenTabs();
    initDensity();
    initKeyboardShortcuts();
    initDeleteConfirm();
    initTooltips();
    initFormAutoSave();
    initBottomTabs();
    initMiniTabs();
  });

  /* ═══════════════════════════════════════════════════════════
     SIDEBAR
  ═══════════════════════════════════════════════════════════ */
  function initSidebar() {
    var sidebar  = document.querySelector('.orion-sidebar');
    var main     = document.querySelector('.orion-main');
    var overlay  = document.querySelector('.orion-sidebar-overlay');
    var toggleBtn = document.getElementById('orionSidebarToggle');
    var mobileBtn = document.getElementById('orionMobileMenuBtn');
    var compactBtn= document.getElementById('orionCompactToggle');

    if (!sidebar) return;

    // Sous-menus
    sidebar.querySelectorAll('.orion-sidebar-item.has-children').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var submenu = btn.nextElementSibling;
        if (!submenu || !submenu.classList.contains('orion-sidebar-submenu')) return;

        var isOpen = submenu.classList.contains('show');

        // Ferme tous les autres
        sidebar.querySelectorAll('.orion-sidebar-submenu.show').forEach(function (s) {
          s.classList.remove('show');
        });
        sidebar.querySelectorAll('.orion-sidebar-item.open').forEach(function (b) {
          b.classList.remove('open');
        });

        if (!isOpen) {
          submenu.classList.add('show');
          btn.classList.add('open');
        }
      });
    });

    // Compact desktop
    var isCompact = localStorage.getItem(STORAGE_COMPACT) === '1';
    if (isCompact) applyCompact(true);

    if (compactBtn) {
      compactBtn.addEventListener('click', function () {
        isCompact = !isCompact;
        localStorage.setItem(STORAGE_COMPACT, isCompact ? '1' : '0');
        applyCompact(isCompact);
      });
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        isCompact = !isCompact;
        localStorage.setItem(STORAGE_COMPACT, isCompact ? '1' : '0');
        applyCompact(isCompact);
      });
    }

    // Mobile toggle
    if (mobileBtn) {
      mobileBtn.addEventListener('click', function () {
        sidebar.classList.toggle('mobile-open');
        if (overlay) overlay.classList.toggle('show');
      });
    }

    if (overlay) {
      overlay.addEventListener('click', function () {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('show');
      });
    }

    // Marquer item actif
    markActiveSidebarItem();
  }

  function applyCompact(compact) {
    var sidebar = document.querySelector('.orion-sidebar');
    var main    = document.querySelector('.orion-main');
    if (!sidebar) return;

    if (compact) {
      sidebar.classList.add('compact');
      if (main) main.classList.add('sidebar-collapsed');
    } else {
      sidebar.classList.remove('compact');
      if (main) main.classList.remove('sidebar-collapsed');
    }
  }

  function markActiveSidebarItem() {
    var path = window.location.pathname;
    var links = document.querySelectorAll('.orion-sidebar-sublink, .orion-sidebar-item[href]');

    links.forEach(function (link) {
      var href = link.getAttribute('href');
      if (!href || href === '#') return;

      if (path === href || (href !== '/' && path.startsWith(href))) {
        link.classList.add('active');

        // Ouvre le sous-menu parent
        var submenu = link.closest('.orion-sidebar-submenu');
        if (submenu) {
          submenu.classList.add('show');
          var parentBtn = submenu.previousElementSibling;
          if (parentBtn) parentBtn.classList.add('open', 'active');
        }
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     OPEN TABS (localStorage)
  ═══════════════════════════════════════════════════════════ */
  function initOpenTabs() {
    var tabsBar = document.querySelector('.orion-open-tabs');
    if (!tabsBar) return;

    // Enregistre page actuelle
    var title = document.title.replace(/\s*—.*$/, '').trim();
    var path  = window.location.pathname;
    addTab({ url: path, label: title, icon: getPageIcon() });

    renderTabs(tabsBar);
  }

  function getTabs() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_TABS) || '[]');
    } catch (e) { return []; }
  }

  function saveTabs(tabs) {
    localStorage.setItem(STORAGE_TABS, JSON.stringify(tabs));
  }

  function addTab(tab) {
    var tabs = getTabs();
    var exists = tabs.findIndex(function (t) { return t.url === tab.url; });

    if (exists >= 0) {
      tabs[exists].label = tab.label;
    } else {
      tabs.push(tab);
      if (tabs.length > MAX_TABS) tabs.shift();
    }
    saveTabs(tabs);
  }

  function removeTab(url) {
    var tabs = getTabs().filter(function (t) { return t.url !== url; });
    saveTabs(tabs);
  }

  function renderTabs(container) {
    var tabs    = getTabs();
    var current = window.location.pathname;

    container.innerHTML = '';

    tabs.forEach(function (tab) {
      var el = document.createElement('a');
      el.href = tab.url;
      el.className = 'orion-open-tab' + (tab.url === current ? ' active' : '');

      el.innerHTML =
        '<i class="bi ' + (tab.icon || 'bi-file-earmark') + ' orion-open-tab-icon"></i>' +
        '<span class="orion-open-tab-label">' + escHtml(tab.label) + '</span>' +
        '<button class="orion-open-tab-close" data-url="' + escAttr(tab.url) + '" title="Fermer">×</button>';

      container.appendChild(el);
    });

    // Fermeture onglet
    container.querySelectorAll('.orion-open-tab-close').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var url = btn.dataset.url;
        removeTab(url);

        // Si on ferme l'onglet actif, aller sur le précédent
        if (url === window.location.pathname) {
          var remaining = getTabs();
          if (remaining.length > 0) {
            window.location.href = remaining[remaining.length - 1].url;
          } else {
            window.location.href = '/dashboard/';
          }
        } else {
          renderTabs(container);
        }
      });
    });
  }

  function getPageIcon() {
    var path = window.location.pathname;
    var iconMap = {
      '/dashboard': 'bi-speedometer2',
      '/crm': 'bi-people',
      '/sales': 'bi-receipt',
      '/purchases': 'bi-cart',
      '/inventory': 'bi-boxes',
      '/btp': 'bi-building',
      '/hr': 'bi-person-badge',
      '/accounting': 'bi-calculator',
      '/documents': 'bi-folder',
      '/support': 'bi-headset',
      '/ecommerce': 'bi-shop',
      '/commerce': 'bi-shop-window',
      '/production': 'bi-gear',
      '/audio': 'bi-speaker',
      '/websites': 'bi-globe',
      '/bi': 'bi-bar-chart',
    };
    for (var prefix in iconMap) {
      if (path.startsWith(prefix)) return iconMap[prefix];
    }
    return 'bi-file-earmark';
  }

  /* ═══════════════════════════════════════════════════════════
     DENSITY / INTERFACE
  ═══════════════════════════════════════════════════════════ */
  function initDensity() {
    var saved = localStorage.getItem(STORAGE_DENSITY) || 'standard';
    applyDensity(saved);

    document.querySelectorAll('[data-density]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var d = btn.dataset.density;
        applyDensity(d);
        localStorage.setItem(STORAGE_DENSITY, d);

        // Mise à jour état actif
        document.querySelectorAll('[data-density]').forEach(function (b) {
          b.classList.toggle('active', b.dataset.density === d);
        });
      });
    });
  }

  function applyDensity(density) {
    document.body.classList.remove(
      'orion-density-comfort', 'orion-density-standard',
      'orion-density-compact', 'orion-density-dense'
    );
    document.body.classList.add('orion-density-' + density);
  }

  /* ═══════════════════════════════════════════════════════════
     KEYBOARD SHORTCUTS
  ═══════════════════════════════════════════════════════════ */
  function initKeyboardShortcuts() {
    document.addEventListener('keydown', function (e) {
      var ctrl = e.ctrlKey || e.metaKey;

      // Ctrl+S → soumettre formulaire
      if (ctrl && e.key === 's') {
        e.preventDefault();
        var form = document.getElementById('orion-main-form') ||
                   document.querySelector('form.orion-main-form') ||
                   document.querySelector('.orion-record-page form');
        if (form) {
          var submitBtn = form.querySelector('[type="submit"]');
          if (submitBtn) submitBtn.click();
          else form.submit();
          showToastFeedback('Enregistrement…', 'info');
        }
      }

      // Ctrl+K → recherche globale
      if (ctrl && e.key === 'k') {
        e.preventDefault();
        var modal = document.getElementById('globalSearchModal');
        if (modal && window.bootstrap) {
          var bsModal = bootstrap.Modal.getOrCreateInstance(modal);
          bsModal.show();
        }
      }

      // Echap → annuler / fermer modale
      if (e.key === 'Escape') {
        var modals = document.querySelectorAll('.modal.show');
        if (modals.length === 0) {
          // Annuler édition si pertinent
          var cancelBtn = document.querySelector('.orion-record-page .btn-cancel');
          if (cancelBtn) cancelBtn.click();
        }
      }

      // Ctrl+P → imprimer
      if (ctrl && e.key === 'p') {
        if (document.querySelector('.orion-record-page')) {
          e.preventDefault();
          window.print();
        }
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     CONFIRMATION SUPPRESSION
  ═══════════════════════════════════════════════════════════ */
  function initDeleteConfirm() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-confirm]');
      if (!btn) return;

      var msg = btn.dataset.confirm || 'Confirmer cette action ?';
      if (!confirm(msg)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     TOOLTIPS Bootstrap
  ═══════════════════════════════════════════════════════════ */
  function initTooltips() {
    if (!window.bootstrap || !bootstrap.Tooltip) return;
    document.querySelectorAll('[title]:not([data-bs-toggle])').forEach(function (el) {
      if (el.title) {
        new bootstrap.Tooltip(el, { trigger: 'hover', delay: { show: 400, hide: 0 } });
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     AUTO-SAVE indicator
  ═══════════════════════════════════════════════════════════ */
  function initFormAutoSave() {
    var form = document.querySelector('.orion-record-page form');
    if (!form) return;

    var isDirty = false;
    form.addEventListener('change', function () { isDirty = true; updateDirtyIndicator(true); });
    form.addEventListener('submit', function () { isDirty = false; updateDirtyIndicator(false); });

    window.addEventListener('beforeunload', function (e) {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = 'Des modifications non enregistrées seront perdues.';
      }
    });
  }

  function updateDirtyIndicator(dirty) {
    var indicator = document.getElementById('orionDirtyIndicator');
    if (!indicator) return;
    indicator.style.display = dirty ? 'inline-flex' : 'none';
  }

  /* ═══════════════════════════════════════════════════════════
     BOTTOM TABS
  ═══════════════════════════════════════════════════════════ */
  function initBottomTabs() {
    document.querySelectorAll('.orion-bottom-tabs').forEach(function (container) {
      var tabs     = container.querySelectorAll('.orion-bottom-tab');
      var contents = container.querySelectorAll('.orion-bottom-tab-content');

      tabs.forEach(function (tab) {
        tab.addEventListener('click', function (e) {
          e.preventDefault();
          var target = tab.dataset.tab;

          tabs.forEach(function (t) { t.classList.remove('active'); });
          contents.forEach(function (c) { c.classList.remove('active'); });

          tab.classList.add('active');
          var content = container.querySelector('#' + target);
          if (content) content.classList.add('active');
        });
      });

      // Activer premier par défaut
      if (tabs.length > 0 && !container.querySelector('.orion-bottom-tab.active')) {
        tabs[0].click();
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════
     MINI TABS (internes)
  ═══════════════════════════════════════════════════════════ */
  function initMiniTabs() {
    document.querySelectorAll('.orion-mini-tabs').forEach(function (nav) {
      nav.querySelectorAll('.orion-mini-tab').forEach(function (tab) {
        tab.addEventListener('click', function (e) {
          e.preventDefault();
          var target = tab.dataset.miniTab;
          var wrapper = nav.closest('[data-mini-tabs-wrapper]') || nav.parentElement;

          nav.querySelectorAll('.orion-mini-tab').forEach(function (t) { t.classList.remove('active'); });
          wrapper.querySelectorAll('[data-mini-tab-content]').forEach(function (c) { c.style.display = 'none'; });

          tab.classList.add('active');
          var content = wrapper.querySelector('[data-mini-tab-content="' + target + '"]');
          if (content) content.style.display = '';
        });
      });

      var first = nav.querySelector('.orion-mini-tab');
      if (first && !nav.querySelector('.orion-mini-tab.active')) first.click();
    });
  }

  /* ═══════════════════════════════════════════════════════════
     TOAST FEEDBACK
  ═══════════════════════════════════════════════════════════ */
  function showToastFeedback(msg, type) {
    if (window.orionToast) { orionToast(msg, type); return; }
    if (window.OrionToast) { OrionToast.show(msg, type); return; }
  }

  /* ── Helpers ─────────────────────────────────────────────── */
  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escAttr(s) {
    return String(s).replace(/"/g, '&quot;');
  }

  /* ── API publique ────────────────────────────────────────── */
  window.OrionDesktop = {
    applyCompact: applyCompact,
    applyDensity: applyDensity,
    addTab: addTab,
    removeTab: removeTab,
  };

})();
