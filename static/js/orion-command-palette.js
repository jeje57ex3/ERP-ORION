/**
 * Orion ERP — Command Palette
 * Ctrl+K : ouvre la palette, navigation clavier, recherche AJAX
 */
(function () {
  'use strict';

  var palette = document.getElementById('orionCommandPalette');
  var input   = document.getElementById('orionCmdInput');
  var results = document.getElementById('orionCmdResults');
  if (!palette || !input) return;

  var isOpen = false;
  var focusIndex = -1;

  /* ── Ouverture / fermeture ────────────────────────────────── */
  function open() {
    palette.style.display = 'flex';
    input.value = '';
    focusIndex = -1;
    isOpen = true;
    input.focus();
    showDefaults();
    document.body.style.overflow = 'hidden';
  }

  function close() {
    palette.style.display = 'none';
    isOpen = false;
    document.body.style.overflow = '';
  }

  function showDefaults() {
    results.querySelectorAll('[data-default]').forEach(function (s) {
      s.style.display = '';
    });
  }

  function hideDefaults() {
    results.querySelectorAll('[data-default]').forEach(function (s) {
      s.style.display = 'none';
    });
  }

  /* ── Ctrl+K ───────────────────────────────────────────────── */
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      isOpen ? close() : open();
      return;
    }
    if (!isOpen) return;

    if (e.key === 'Escape') { e.preventDefault(); close(); return; }

    var items = getItems();
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusIndex = Math.min(focusIndex + 1, items.length - 1);
      highlight(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusIndex = Math.max(focusIndex - 1, 0);
      highlight(items);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (focusIndex >= 0 && items[focusIndex]) {
        items[focusIndex].click();
      }
    }
  });

  /* ── Click backdrop ───────────────────────────────────────── */
  palette.addEventListener('click', function (e) {
    if (e.target === palette) close();
  });

  /* ── Navigation clavier ───────────────────────────────────── */
  function getItems() {
    return Array.from(results.querySelectorAll('.orion-cmd-item:not([style*="display: none"])'));
  }

  function highlight(items) {
    items.forEach(function (item, i) {
      item.classList.toggle('focused', i === focusIndex);
      if (i === focusIndex) item.scrollIntoView({ block: 'nearest' });
    });
  }

  /* ── Recherche AJAX ───────────────────────────────────────── */
  var timer;
  var dynSection;

  input.addEventListener('input', function () {
    clearTimeout(timer);
    var q = this.value.trim();

    if (q.length < 2) {
      if (dynSection) { dynSection.remove(); dynSection = null; }
      showDefaults();
      focusIndex = -1;
      return;
    }

    hideDefaults();
    timer = setTimeout(function () { doSearch(q); }, 240);
  });

  function doSearch(q) {
    if (dynSection) { dynSection.remove(); dynSection = null; }

    dynSection = document.createElement('div');
    dynSection.innerHTML = '<div style="padding:16px;text-align:center;color:var(--orion-muted);font-size:13px"><i class="bi bi-hourglass-split me-1"></i>Recherche…</div>';
    results.appendChild(dynSection);

    fetch('/search/?q=' + encodeURIComponent(q) + '&format=json', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!dynSection) return;
        dynSection.innerHTML = '';
        if (!data || !data.results || !data.results.length) {
          dynSection.innerHTML = '<div style="padding:24px;text-align:center;color:var(--orion-muted);font-size:13px"><i class="bi bi-search d-block mb-2" style="font-size:22px;opacity:.3"></i>Aucun résultat pour « ' + q + ' »</div>';
          return;
        }
        var byType = {};
        data.results.forEach(function (r) {
          if (!byType[r.label]) byType[r.label] = [];
          byType[r.label].push(r);
        });
        Object.entries(byType).forEach(function (entry) {
          var label = entry[0], items = entry[1];
          var sectionEl = document.createElement('div');
          sectionEl.innerHTML = '<div style="padding:8px 10px 4px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--orion-muted)">' + label + '</div>';
          items.forEach(function (item) {
            var a = document.createElement('a');
            a.href = item.url;
            a.className = 'orion-cmd-item';
            a.innerHTML =
              '<span class="orion-cmd-icon"><i class="bi ' + (item.icon || 'bi-dot') + '"></i></span>' +
              '<span>' + item.title + (item.subtitle ? '<span style="display:block;font-size:11.5px;color:var(--orion-muted)">' + item.subtitle + '</span>' : '') + '</span>';
            sectionEl.appendChild(a);
          });
          dynSection.appendChild(sectionEl);
        });
        focusIndex = -1;
      })
      .catch(function () {
        if (dynSection) {
          dynSection.innerHTML = '<div style="padding:16px;text-align:center;color:var(--orion-muted);font-size:13px"><i class="bi bi-wifi-off me-1"></i>Erreur réseau</div>';
        }
      });
  }

})();
