/**
 * Orion ERP — Sidebar v2
 * Gestion : ouverture mobile, réduction desktop, état persisté
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'orion-sidebar-collapsed';
  var shell = document.getElementById('orionShell');
  var sidebar = document.getElementById('orionSidebar');
  var toggleBtn = document.getElementById('orionSidebarToggleDesktop');
  var mobileBtn = document.getElementById('orionMobileMenuBtn');
  var overlay = document.getElementById('orionSidebarOverlay');

  if (!shell || !sidebar) return;

  /* ── Réduction desktop ─────────────────────────────────────── */
  function isCollapsed() {
    return localStorage.getItem(STORAGE_KEY) === '1';
  }

  function setCollapsed(v) {
    if (v) {
      shell.classList.add('sidebar-collapsed');
      sidebar.classList.add('collapsed');
      localStorage.setItem(STORAGE_KEY, '1');
    } else {
      shell.classList.remove('sidebar-collapsed');
      sidebar.classList.remove('collapsed');
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  /* Restaurer l'état au chargement */
  if (isCollapsed()) setCollapsed(true);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      setCollapsed(!isCollapsed());
    });
  }

  /* ── Mobile ────────────────────────────────────────────────── */
  function openMobile() {
    document.body.classList.add('orion-sidebar-open');
    if (mobileBtn) mobileBtn.setAttribute('aria-expanded', 'true');
  }

  function closeMobile() {
    document.body.classList.remove('orion-sidebar-open');
    if (mobileBtn) mobileBtn.setAttribute('aria-expanded', 'false');
  }

  if (mobileBtn) {
    mobileBtn.addEventListener('click', function () {
      document.body.classList.contains('orion-sidebar-open') ? closeMobile() : openMobile();
    });
  }

  if (overlay) {
    overlay.addEventListener('click', closeMobile);
  }

  /* Fermer avec Échap */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMobile();
  });

  /* Fermer au changement de taille */
  var mq = window.matchMedia('(min-width: 1101px)');
  function onResize() {
    if (mq.matches) closeMobile();
  }
  if (mq.addEventListener) mq.addEventListener('change', onResize);
  else mq.addListener(onResize);

})();
