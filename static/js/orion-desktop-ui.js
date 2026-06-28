/**
 * Orion ERP — Desktop UI
 * Sidebar, open-tabs, density, keyboard shortcuts, form dirty, bottom tabs
 */
(function () {
  'use strict';

  /* ── Constants ────────────────────────────────────────────── */
  var LS_COMPACT  = 'orion_sidebar_compact';
  var LS_TABS     = 'orion_open_tabs';
  var LS_DENSITY  = 'orion_density';
  var MAX_TABS    = 12;

  /* ══════════════════════════════════════════════════════════
     SIDEBAR
  ══════════════════════════════════════════════════════════ */
  function initSidebar() {
    var sidebar  = document.getElementById('erpSidebar') || document.querySelector('.erp-sidebar, .orion-sidebar');
    var main     = document.getElementById('erpMain')    || document.querySelector('.erp-main, .orion-main');
    var toggle   = document.getElementById('sidebarToggle');
    var closeBtn = document.getElementById('sidebarClose');
    var overlay  = document.getElementById('sidebarOverlay');

    if (!sidebar) return;

    /* Restore compact state */
    if (localStorage.getItem(LS_COMPACT) === '1') {
      sidebar.classList.add('compact');
      if (main) main.classList.add('sidebar-collapsed');
    }

    /* Desktop toggle → compact mode */
    if (toggle) {
      toggle.addEventListener('click', function () {
        var isCompact = sidebar.classList.toggle('compact');
        if (main) main.classList.toggle('sidebar-collapsed', isCompact);
        localStorage.setItem(LS_COMPACT, isCompact ? '1' : '0');
      });
    }

    /* Mobile toggle */
    function openMobile() {
      sidebar.classList.add('mobile-open');
      if (overlay) overlay.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    function closeMobile() {
      sidebar.classList.remove('mobile-open');
      if (overlay) overlay.classList.remove('active');
      document.body.style.overflow = '';
    }

    if (toggle) {
      toggle.addEventListener('click', function () {
        if (window.innerWidth < 768) openMobile();
      });
    }

    if (closeBtn) closeBtn.addEventListener('click', closeMobile);
    if (overlay)  overlay.addEventListener('click', closeMobile);

    /* Mark active link */
    var path = window.location.pathname;
    sidebar.querySelectorAll('.nav-sublink, .nav-link').forEach(function (a) {
      if (a.getAttribute('href') === path) {
        a.classList.add('active');
        var submenu = a.closest('.collapse');
        if (submenu) {
          submenu.classList.add('show');
          var parent = sidebar.querySelector('[href="#' + submenu.id + '"]');
          if (parent) { parent.classList.add('active'); parent.setAttribute('aria-expanded', 'true'); }
        }
      }
    });
  }

  /* ══════════════════════════════════════════════════════════
     OPEN TABS (localStorage-based browser-like tab bar)
  ══════════════════════════════════════════════════════════ */
  function getTabs() {
    try { return JSON.parse(localStorage.getItem(LS_TABS) || '[]'); } catch (e) { return []; }
  }

  function saveTabs(tabs) {
    localStorage.setItem(LS_TABS, JSON.stringify(tabs));
  }

  function renderTabs() {
    var bar = document.getElementById('orionOpenTabs');
    if (!bar) return;

    var tabs    = getTabs();
    var current = window.location.href;
    bar.innerHTML = '';

    tabs.forEach(function (tab, idx) {
      var el = document.createElement('a');
      el.className = 'orion-open-tab' + (tab.url === current ? ' active' : '');
      el.href = tab.url;
      el.title = tab.title;
      el.innerHTML =
        '<span class="orion-open-tab-label">' + escHtml(tab.title) + '</span>' +
        '<span class="orion-open-tab-close" data-idx="' + idx + '" aria-label="Fermer">×</span>';
      bar.appendChild(el);
    });

    /* Close buttons */
    bar.querySelectorAll('.orion-open-tab-close').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var tabs = getTabs();
        var removed = tabs.splice(parseInt(this.dataset.idx), 1)[0];
        saveTabs(tabs);
        renderTabs();
        /* Navigate away if closing current tab */
        if (removed && removed.url === window.location.href) {
          if (tabs.length) window.location.href = tabs[tabs.length - 1].url;
          else window.location.href = '/dashboard/';
        }
      });
    });
  }

  function addCurrentTab() {
    var bar = document.getElementById('orionOpenTabs');
    if (!bar) return;

    var url   = window.location.href;
    var title = document.title.replace(/\s*—.*$/, '').trim() || document.title;
    var tabs  = getTabs();

    /* Deduplicate */
    var exists = tabs.findIndex(function (t) { return t.url === url; });
    if (exists >= 0) { renderTabs(); return; }

    tabs.push({ url: url, title: title });
    if (tabs.length > MAX_TABS) tabs.shift();
    saveTabs(tabs);
    renderTabs();
  }

  function initOpenTabs() {
    if (!document.getElementById('orionOpenTabs')) return;
    addCurrentTab();
  }

  /* ══════════════════════════════════════════════════════════
     BOTTOM TABS (record pages)
  ══════════════════════════════════════════════════════════ */
  function initBottomTabs() {
    document.querySelectorAll('.orion-bottom-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var container = this.closest('.orion-bottom-tabs');
        if (!container) return;
        var targetId  = this.dataset.tab;

        container.querySelectorAll('.orion-bottom-tab').forEach(function (b) { b.classList.remove('active'); });
        container.querySelectorAll('.orion-bottom-tab-content').forEach(function (p) { p.classList.remove('active'); });

        this.classList.add('active');
        var panel = document.getElementById(targetId);
        if (panel) panel.classList.add('active');
      });
    });
  }

  /* Mini tabs */
  function initMiniTabs() {
    document.querySelectorAll('.orion-mini-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var container = this.closest('[data-mini-tabs]') || this.parentElement.parentElement;
        var targetId  = this.dataset.tab;

        this.parentElement.querySelectorAll('.orion-mini-tab').forEach(function (b) { b.classList.remove('active'); });
        if (container) {
          container.querySelectorAll('.orion-mini-tab-content').forEach(function (p) { p.classList.remove('active'); });
        }

        this.classList.add('active');
        var panel = document.getElementById(targetId);
        if (panel) panel.classList.add('active');
      });
    });
  }

  /* ══════════════════════════════════════════════════════════
     DENSITY
  ══════════════════════════════════════════════════════════ */
  var DENSITY_CLASSES = ['orion-density-comfort', 'orion-density-standard', 'orion-density-compact', 'orion-density-dense'];

  function applyDensity(density) {
    DENSITY_CLASSES.forEach(function (c) { document.body.classList.remove(c); });
    if (density) document.body.classList.add('orion-density-' + density);

    var btns = document.querySelectorAll('[data-density]');
    btns.forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.density === density);
    });
  }

  function initDensity() {
    var saved = localStorage.getItem(LS_DENSITY) || 'standard';
    applyDensity(saved);

    document.querySelectorAll('[data-density]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var d = this.dataset.density;
        localStorage.setItem(LS_DENSITY, d);
        applyDensity(d);
      });
    });
  }

  /* ══════════════════════════════════════════════════════════
     KEYBOARD SHORTCUTS
  ══════════════════════════════════════════════════════════ */
  function initKeyboardShortcuts() {
    document.addEventListener('keydown', function (e) {
      /* Ctrl+S → submit focused form */
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        var form = document.querySelector('form.orion-main-form') || document.querySelector('form[id$="-form"]');
        if (form) form.requestSubmit ? form.requestSubmit() : form.submit();
      }

      /* Ctrl+K → search modal */
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        var modal = document.getElementById('globalSearchModal');
        if (modal && window.bootstrap) {
          var bsModal = bootstrap.Modal.getOrCreateInstance(modal);
          bsModal.show();
        }
      }

      /* Escape → close search modal, mobile sidebar */
      if (e.key === 'Escape') {
        var sidebar = document.querySelector('.erp-sidebar, .orion-sidebar');
        var overlay = document.getElementById('sidebarOverlay');
        if (sidebar && sidebar.classList.contains('mobile-open')) {
          sidebar.classList.remove('mobile-open');
          if (overlay) overlay.classList.remove('active');
          document.body.style.overflow = '';
        }
      }
    });
  }

  /* ══════════════════════════════════════════════════════════
     DELETE CONFIRM (data-confirm attribute)
  ══════════════════════════════════════════════════════════ */
  function initDeleteConfirm() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-confirm]');
      if (!btn) return;
      var msg = btn.dataset.confirm || 'Êtes-vous sûr ?';
      if (!window.confirm(msg)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  }

  /* ══════════════════════════════════════════════════════════
     FORM DIRTY TRACKING (warn before leaving unsaved changes)
  ══════════════════════════════════════════════════════════ */
  function initDirtyTracking() {
    var forms = document.querySelectorAll('form.orion-main-form');
    forms.forEach(function (form) {
      var dirty = false;
      form.addEventListener('change', function () { dirty = true; });
      form.addEventListener('submit', function ()  { dirty = false; });

      window.addEventListener('beforeunload', function (e) {
        if (!dirty) return;
        e.preventDefault();
        e.returnValue = 'Des modifications non enregistrées seront perdues.';
      });
    });
  }

  /* ══════════════════════════════════════════════════════════
     TOOLTIPS (Bootstrap)
  ══════════════════════════════════════════════════════════ */
  function initTooltips() {
    if (!window.bootstrap) return;
    document.querySelectorAll('[title]').forEach(function (el) {
      if (el.closest('.dropdown-menu')) return;
      try { new bootstrap.Tooltip(el, { trigger: 'hover', delay: { show: 600, hide: 0 } }); } catch (err) {}
    });
  }

  /* ══════════════════════════════════════════════════════════
     FORM FIELD STYLING (apply orion classes to Django fields)
  ══════════════════════════════════════════════════════════ */
  function styleFormFields() {
    var rows = document.querySelectorAll('.orion-form-row');
    rows.forEach(function (row) {
      row.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea').forEach(function (el) {
        el.classList.add('orion-form-control');
        if (el.tagName === 'SELECT' && !el.multiple) el.classList.add('orion-select');
        if (el.tagName === 'TEXTAREA') el.classList.add('orion-form-textarea');
      });
    });
  }

  /* ══════════════════════════════════════════════════════════
     UTILITY
  ══════════════════════════════════════════════════════════ */
  function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ══════════════════════════════════════════════════════════
     PUBLIC API
  ══════════════════════════════════════════════════════════ */
  window.OrionDesktopUI = {
    openTab: addCurrentTab,
    renderTabs: renderTabs,
    applyDensity: applyDensity,
    getTabs: getTabs,
    clearTabs: function () { saveTabs([]); renderTabs(); }
  };

  /* ══════════════════════════════════════════════════════════
     BOOT
  ══════════════════════════════════════════════════════════ */
  document.addEventListener('DOMContentLoaded', function () {
    initSidebar();
    initOpenTabs();
    initBottomTabs();
    initMiniTabs();
    initDensity();
    initKeyboardShortcuts();
    initDeleteConfirm();
    initDirtyTracking();
    styleFormFields();
    /* Tooltips after a tick so Bootstrap is initialised */
    setTimeout(initTooltips, 50);
  });

})();
