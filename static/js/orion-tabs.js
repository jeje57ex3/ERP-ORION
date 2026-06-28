/**
 * Orion ERP — Tabs v2
 * Onglets simples sans dépendance Bootstrap
 */
(function () {
  'use strict';

  /* Tab panels JS (optionnel — si les onglets sont en JS pur sans reload) */
  document.querySelectorAll('[data-orion-tabs]').forEach(function (tabGroup) {
    var tabs   = tabGroup.querySelectorAll('[data-tab]');
    var panels = document.querySelectorAll('[data-tab-panel]');

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        var target = tab.getAttribute('data-tab');

        /* Désactiver tous */
        tabs.forEach(function (t) { t.classList.remove('active'); });
        panels.forEach(function (p) { p.style.display = 'none'; });

        /* Activer le sélectionné */
        tab.classList.add('active');
        var panel = document.querySelector('[data-tab-panel="' + target + '"]');
        if (panel) panel.style.display = '';

        /* Persister dans l'URL */
        if (history.pushState) {
          var url = new URL(window.location);
          url.searchParams.set('tab', target);
          history.pushState({}, '', url);
        }
      });
    });

    /* Restaurer depuis l'URL */
    var urlTab = new URLSearchParams(window.location.search).get('tab');
    if (urlTab) {
      var activeTab = tabGroup.querySelector('[data-tab="' + urlTab + '"]');
      if (activeTab) activeTab.click();
    }
  });

  /* Mode compact toggle */
  var compactToggle = document.getElementById('orionCompactToggle');
  if (compactToggle) {
    var isCompact = localStorage.getItem('orion-compact') === '1';
    if (isCompact) document.body.classList.add('orion-compact');

    compactToggle.addEventListener('click', function () {
      var c = document.body.classList.toggle('orion-compact');
      localStorage.setItem('orion-compact', c ? '1' : '0');
      compactToggle.textContent = c ? 'Mode confortable' : 'Mode compact';
    });
  }

})();
