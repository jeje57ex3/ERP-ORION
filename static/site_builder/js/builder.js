/* builder.js — Visual Site Builder main controller */
const Builder = (() => {

  let pageId = null;
  let csrf = null;
  let selectedId = null;
  let settingsTimer = null;
  let currentSettings = {};

  /* ── Init ──────────────────────────────────────────────────────────── */
  function init() {
    pageId = document.getElementById('page-id')?.value;
    csrf   = document.getElementById('csrf-token')?.value;
    if (!pageId) return;

    // Sidebar tab switching
    document.querySelectorAll('.sb-tab').forEach(tab => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Module palette click to add
    document.querySelectorAll('.sb-module-item').forEach(item => {
      item.addEventListener('click', () => addSection(item.dataset.moduleType));
    });

    // Canvas click delegation
    document.getElementById('sb-canvas')?.addEventListener('click', onCanvasClick);

    // Layers click delegation
    document.getElementById('sb-layers-list')?.addEventListener('click', e => {
      const layer = e.target.closest('.sb-layer-item');
      if (layer) selectSection(layer.dataset.sectionId);
    });

    // Publish
    document.getElementById('sb-publish-btn')?.addEventListener('click', publishPage);

    // Device toggles
    document.querySelectorAll('.sb-device-btn').forEach(btn => {
      btn.addEventListener('click', () => setDevice(btn.dataset.device));
    });

    // Select first section if exists
    const first = document.querySelector('.sb-section-wrapper');
    if (first) selectSection(first.dataset.sectionId);
  }

  /* ── Tab switching ─────────────────────────────────────────────────── */
  function switchTab(name) {
    document.querySelectorAll('.sb-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.sb-tab-content').forEach(c =>
      c.classList.toggle('active', c.dataset.tabContent === name));
  }

  /* ── Canvas click handler ──────────────────────────────────────────── */
  function onCanvasClick(e) {
    const deleteBtn = e.target.closest('[data-action="delete"]');
    if (deleteBtn) {
      e.stopPropagation();
      const w = deleteBtn.closest('.sb-section-wrapper');
      if (w) deleteSection(w.dataset.sectionId, w);
      return;
    }
    const moveUp = e.target.closest('[data-action="move-up"]');
    if (moveUp) {
      e.stopPropagation();
      moveSection(moveUp.closest('.sb-section-wrapper'), 'up');
      return;
    }
    const moveDown = e.target.closest('[data-action="move-down"]');
    if (moveDown) {
      e.stopPropagation();
      moveSection(moveDown.closest('.sb-section-wrapper'), 'down');
      return;
    }
    const wrapper = e.target.closest('.sb-section-wrapper');
    if (wrapper) selectSection(wrapper.dataset.sectionId);
  }

  /* ── Section selection ─────────────────────────────────────────────── */
  function selectSection(sectionId) {
    if (!sectionId) return;
    selectedId = sectionId;

    document.querySelectorAll('.sb-section-wrapper').forEach(w =>
      w.classList.toggle('selected', w.dataset.sectionId === sectionId));
    document.querySelectorAll('.sb-layer-item').forEach(l =>
      l.classList.toggle('active', l.dataset.sectionId === sectionId));

    switchTab('settings');

    const wrapper = document.querySelector(`.sb-section-wrapper[data-section-id="${sectionId}"]`);
    if (!wrapper) return;

    const moduleType = wrapper.dataset.moduleType;
    try {
      currentSettings = JSON.parse(wrapper.dataset.settings || '{}');
    } catch (_) {
      currentSettings = {};
    }

    ModuleSettings.renderForm(moduleType, currentSettings, sectionId, onSettingsChange);
  }

  function onSettingsChange(sectionId, settings) {
    currentSettings = settings;
    clearTimeout(settingsTimer);
    settingsTimer = setTimeout(() => updateSection(sectionId, settings), 650);
  }

  /* ── Add section ───────────────────────────────────────────────────── */
  async function addSection(moduleType) {
    const item = document.querySelector(`.sb-module-item[data-module-type="${moduleType}"]`);
    if (item) item.classList.add('loading');

    try {
      const resp = await post(`/erp/site-builder/pages/${pageId}/sections/add/`, { module_type: moduleType });
      if (!resp.success) { toast(resp.error || 'Erreur', 'error'); return; }

      const canvas = document.getElementById('sb-canvas');
      const empty  = document.getElementById('sb-canvas-empty');
      if (empty) empty.remove();

      const dropZone = document.getElementById('sb-drop-zone');
      const div = document.createElement('div');
      div.innerHTML = resp.wrapper_html.trim();
      const newWrapper = div.firstElementChild;
      canvas.insertBefore(newWrapper, dropZone);

      addLayerItem(resp.section_id, resp.module_type, resp.module_label, resp.module_icon);
      selectSection(String(resp.section_id));
      toast(`${resp.module_label} ajouté`, 'success');
    } catch (_) {
      toast('Erreur réseau', 'error');
    } finally {
      if (item) item.classList.remove('loading');
    }
  }

  /* ── Update section settings ───────────────────────────────────────── */
  async function updateSection(sectionId, settings) {
    const wrapper = document.querySelector(`.sb-section-wrapper[data-section-id="${sectionId}"]`);
    if (wrapper) wrapper.classList.add('saving');

    try {
      const resp = await post(`/erp/site-builder/sections/${sectionId}/update/`, { settings });
      if (!resp.success) return;

      if (wrapper) {
        const content = wrapper.querySelector('.sb-section-content');
        if (content) content.innerHTML = resp.html;
        wrapper.dataset.settings = JSON.stringify(settings);
      }
    } catch (_) {
      // silent — user sees no feedback on auto-save fail
    } finally {
      if (wrapper) wrapper.classList.remove('saving');
    }
  }

  /* ── Delete section ────────────────────────────────────────────────── */
  async function deleteSection(sectionId, wrapper) {
    if (!confirm('Supprimer cette section ?')) return;

    try {
      const resp = await post(`/erp/site-builder/sections/${sectionId}/delete/`, {});
      if (!resp.success) { toast(resp.error || 'Erreur', 'error'); return; }

      wrapper.remove();
      document.querySelector(`.sb-layer-item[data-section-id="${sectionId}"]`)?.remove();

      if (selectedId === sectionId) {
        selectedId = null;
        const panel = document.getElementById('sb-settings-panel');
        if (panel) panel.innerHTML = '<div class="sb-settings-empty"><i class="bi bi-cursor-fill"></i><p>Cliquez sur une section pour modifier ses paramètres.</p></div>';
      }

      if (!document.querySelector('.sb-section-wrapper')) {
        const canvas = document.getElementById('sb-canvas');
        const dz = document.getElementById('sb-drop-zone');
        const empty = document.createElement('div');
        empty.id = 'sb-canvas-empty';
        empty.className = 'sb-canvas-empty';
        empty.innerHTML = '<i class="bi bi-layout-wtf"></i><h3>Page vide</h3><p>Cliquez sur un module dans la palette, ou glissez-le ici.</p>';
        canvas.insertBefore(empty, dz);
      }

      toast('Section supprimée', 'success');
    } catch (_) {
      toast('Erreur réseau', 'error');
    }
  }

  /* ── Move up / down ─────────────────────────────────────────────────── */
  function moveSection(wrapper, dir) {
    if (!wrapper) return;
    const canvas = document.getElementById('sb-canvas');
    const all = [...canvas.querySelectorAll('.sb-section-wrapper')];
    const idx = all.indexOf(wrapper);

    if (dir === 'up' && idx > 0) {
      canvas.insertBefore(wrapper, all[idx - 1]);
    } else if (dir === 'down' && idx < all.length - 1) {
      all[idx + 1].after(wrapper);
    } else {
      return;
    }
    saveOrder();
  }

  /* ── Save order ─────────────────────────────────────────────────────── */
  async function saveOrder() {
    const ids = [...document.querySelectorAll('.sb-section-wrapper')].map(w => w.dataset.sectionId);
    try {
      await post(`/erp/site-builder/pages/${pageId}/sections/reorder/`, { section_ids: ids });
    } catch (_) {}
  }

  /* ── Publish ────────────────────────────────────────────────────────── */
  async function publishPage() {
    const btn = document.getElementById('sb-publish-btn');
    if (!btn) return;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Publication…';

    try {
      const resp = await post(`/erp/site-builder/pages/${pageId}/publish/`, {});
      if (!resp.success) { toast(resp.error || 'Erreur', 'error'); return; }

      const badge = document.getElementById('sb-status-badge');
      if (badge) {
        badge.textContent = 'Publié';
        badge.className = 'sb-status-badge sb-status-published';
      }
      toast('Page publiée !', 'success');
      document.dispatchEvent(new Event('sb:published'));
    } catch (_) {
      toast('Erreur réseau', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-broadcast me-1"></i>Publier';
    }
  }

  /* ── Device preview ─────────────────────────────────────────────────── */
  function setDevice(device) {
    document.querySelectorAll('.sb-device-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.device === device));
    const canvas = document.getElementById('sb-canvas');
    if (canvas) canvas.className = `sb-canvas device-${device}`;
  }

  /* ── Layer helpers ──────────────────────────────────────────────────── */
  function addLayerItem(sectionId, moduleType, label, icon) {
    const list = document.getElementById('sb-layers-list');
    if (!list) return;
    const empty = list.querySelector('.sb-layers-empty');
    if (empty) empty.remove();

    const item = document.createElement('div');
    item.className = 'sb-layer-item';
    item.dataset.sectionId = String(sectionId);
    item.dataset.sectionType = moduleType;
    item.innerHTML = `<i class="bi ${icon}"></i><span>${label}</span><i class="bi bi-grip-vertical sb-layer-grip"></i>`;
    list.appendChild(item);
  }

  /* ── Toast ──────────────────────────────────────────────────────────── */
  function toast(msg, type = 'info') {
    const container = document.getElementById('sb-toasts');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `sb-toast sb-toast-${type}`;
    el.textContent = msg;
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 300);
    }, 3000);
  }

  /* ── HTTP helper ────────────────────────────────────────────────────── */
  async function post(url, body) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
      },
      body: JSON.stringify(body),
    });
    return resp.json();
  }

  document.addEventListener('DOMContentLoaded', init);

  // Expose methods DragDrop needs
  return { addSection, saveOrder };
})();
