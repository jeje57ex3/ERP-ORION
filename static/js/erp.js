/**
 * ERP BTP Starter — JavaScript global
 * Sidebar, recherche, notifications, raccourcis clavier
 */

document.addEventListener('DOMContentLoaded', function () {

  // ── Sidebar toggle ─────────────────────────────────────────
  const sidebar = document.getElementById('erpSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarClose = document.getElementById('sidebarClose');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  function openSidebar() {
    sidebar?.classList.add('sidebar-open');
    sidebarOverlay?.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebar?.classList.remove('sidebar-open');
    sidebarOverlay?.classList.remove('show');
    document.body.style.overflow = '';
  }

  sidebarToggle?.addEventListener('click', function () {
    if (sidebar?.classList.contains('sidebar-open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  sidebarClose?.addEventListener('click', closeSidebar);
  sidebarOverlay?.addEventListener('click', closeSidebar);

  // Fermer sur ESC
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeSidebar();
      document.getElementById('globalSearch')?.blur();
    }
  });

  // ── Raccourci Ctrl+K (recherche) ───────────────────────────
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const search = document.getElementById('globalSearch');
      if (search) {
        search.focus();
        search.select();
      }
    }
  });

  // ── Auto-dismiss des alertes ───────────────────────────────
  const alerts = document.querySelectorAll('.erp-alert[data-auto-dismiss]');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });

  // ── Auto-dismiss par défaut (succès) ──────────────────────
  document.querySelectorAll('.alert-success:not([data-no-dismiss])').forEach(function (el) {
    setTimeout(function () {
      try { new bootstrap.Alert(el).close(); } catch (e) {}
    }, 4000);
  });

  // ── Notifications : marquer comme lu ──────────────────────
  document.querySelectorAll('.notification-item').forEach(function (item) {
    item.addEventListener('click', function (e) {
      const href = item.getAttribute('href');
      if (href && href.includes('/read/')) {
        fetch(href, { method: 'GET', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then(function (res) { return res.json(); })
          .catch(function () {});
      }
    });
  });

  // ── Confirmation avant suppression ────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      const message = el.getAttribute('data-confirm') || 'Confirmer cette action ?';
      if (!confirm(message)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  });

  // ── Tooltips Bootstrap ─────────────────────────────────────
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (el) {
    return new bootstrap.Tooltip(el, { trigger: 'hover' });
  });

  // ── Active nav selon URL ───────────────────────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link, .nav-sublink').forEach(function (link) {
    const href = link.getAttribute('href');
    if (href && href !== '/' && href !== '#' && currentPath.startsWith(href)) {
      link.classList.add('active');
    }
  });

  // ── Tableaux : tri client ──────────────────────────────────
  document.querySelectorAll('th[data-sortable]').forEach(function (th) {
    th.style.cursor = 'pointer';
    th.addEventListener('click', function () {
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const colIndex = Array.from(th.parentElement.children).indexOf(th);
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const asc = th.dataset.sortDir !== 'asc';
      th.dataset.sortDir = asc ? 'asc' : 'desc';

      rows.sort(function (a, b) {
        const aVal = a.children[colIndex]?.textContent.trim() || '';
        const bVal = b.children[colIndex]?.textContent.trim() || '';
        return asc ? aVal.localeCompare(bVal, 'fr') : bVal.localeCompare(aVal, 'fr');
      });

      rows.forEach(function (row) { tbody.appendChild(row); });

      // Icône tri
      table.querySelectorAll('th[data-sortable]').forEach(function (h) {
        h.querySelector('.sort-icon')?.remove();
      });
      const icon = document.createElement('i');
      icon.className = 'bi bi-arrow-' + (asc ? 'up' : 'down') + ' ms-1 sort-icon';
      th.appendChild(icon);
    });
  });

  // ── Recherche dans tableau ─────────────────────────────────
  document.querySelectorAll('[data-table-search]').forEach(function (input) {
    const tableId = input.getAttribute('data-table-search');
    const table = document.getElementById(tableId);
    if (!table) return;

    input.addEventListener('input', function () {
      const query = input.value.toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (row) {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  });

  // ── Changement d'entreprise via URL ───────────────────────
  document.querySelectorAll('.company-item:not(.active)').forEach(function (item) {
    item.addEventListener('click', function (e) {
      // Déjà géré par le href
    });
  });

  // ── Sidebar mobile : fermer sur navigation ─────────────────
  if (window.innerWidth < 992) {
    document.querySelectorAll('.sidebar-nav .nav-link:not([data-bs-toggle])').forEach(function (link) {
      link.addEventListener('click', function () {
        closeSidebar();
      });
    });
  }

  console.log('%c ERP BTP Starter v1.0 ', 'background: #2563EB; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;');
});
