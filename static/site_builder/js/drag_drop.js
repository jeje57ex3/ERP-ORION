/* drag_drop.js — Drag & drop: module palette → canvas, section reorder */
const DragDrop = (() => {

  let dragModuleType = null;
  let dragWrapper = null;
  let dropIndicator = null;

  function init() {
    initModuleDrag();
    initCanvasDrop();
    initSectionHandleDrag();
  }

  /* ── Module palette drag ───────────────────────────────────────────── */
  function initModuleDrag() {
    document.querySelectorAll('.sb-module-item').forEach(item => {
      item.addEventListener('dragstart', e => {
        dragModuleType = item.dataset.moduleType;
        dragWrapper = null;
        e.dataTransfer.effectAllowed = 'copy';
        item.classList.add('dragging');
      });
      item.addEventListener('dragend', () => {
        dragModuleType = null;
        item.classList.remove('dragging');
        clearIndicator();
      });
    });
  }

  /* ── Canvas drop target ─────────────────────────────────────────────── */
  function initCanvasDrop() {
    const canvas = document.getElementById('sb-canvas');
    if (!canvas) return;

    canvas.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = dragWrapper ? 'move' : 'copy';
      const target = dropTarget(e.clientY);
      showIndicator(canvas, target);

      const dropZone = document.getElementById('sb-drop-zone');
      if (dropZone) dropZone.classList.toggle('drag-over', !target);
    });

    canvas.addEventListener('dragleave', e => {
      if (!canvas.contains(e.relatedTarget)) {
        clearIndicator();
        const dz = document.getElementById('sb-drop-zone');
        if (dz) dz.classList.remove('drag-over');
      }
    });

    canvas.addEventListener('drop', e => {
      e.preventDefault();
      clearIndicator();
      const dz = document.getElementById('sb-drop-zone');
      if (dz) dz.classList.remove('drag-over');

      if (dragModuleType) {
        Builder.addSection(dragModuleType);
      } else if (dragWrapper) {
        const target = dropTarget(e.clientY);
        if (target && target !== dragWrapper) {
          const rect = target.getBoundingClientRect();
          const before = e.clientY < rect.top + rect.height / 2;
          if (before) {
            canvas.insertBefore(dragWrapper, target);
          } else {
            target.after(dragWrapper);
          }
        } else if (!target) {
          const dz2 = document.getElementById('sb-drop-zone');
          canvas.insertBefore(dragWrapper, dz2 || null);
        }
        Builder.saveOrder();
      }

      dragModuleType = null;
      dragWrapper = null;
    });
  }

  /* ── Section handle drag (reorder) ─────────────────────────────────── */
  function initSectionHandleDrag() {
    document.addEventListener('mousedown', e => {
      const handle = e.target.closest('.sb-section-drag-handle');
      if (!handle) return;
      const wrapper = handle.closest('.sb-section-wrapper');
      if (!wrapper) return;

      wrapper.setAttribute('draggable', 'true');

      const onDragStart = de => {
        dragWrapper = wrapper;
        dragModuleType = null;
        de.dataTransfer.effectAllowed = 'move';
        wrapper.classList.add('dragging');
      };
      const onDragEnd = () => {
        wrapper.removeAttribute('draggable');
        wrapper.classList.remove('dragging');
        dragWrapper = null;
        wrapper.removeEventListener('dragstart', onDragStart);
        wrapper.removeEventListener('dragend', onDragEnd);
      };

      wrapper.addEventListener('dragstart', onDragStart, { once: true });
      wrapper.addEventListener('dragend', onDragEnd, { once: true });
    });
  }

  /* ── Helpers ────────────────────────────────────────────────────────── */
  function dropTarget(clientY) {
    const wrappers = [...document.querySelectorAll('.sb-section-wrapper')];
    for (const w of wrappers) {
      const rect = w.getBoundingClientRect();
      if (clientY < rect.top + rect.height / 2) return w;
    }
    return null;
  }

  function showIndicator(canvas, target) {
    if (!dropIndicator) {
      dropIndicator = document.createElement('div');
      dropIndicator.className = 'sb-drop-indicator';
    }
    if (target) {
      canvas.insertBefore(dropIndicator, target);
    } else {
      const dz = document.getElementById('sb-drop-zone');
      canvas.insertBefore(dropIndicator, dz || null);
    }
  }

  function clearIndicator() {
    dropIndicator?.remove();
  }

  return { init };
})();

document.addEventListener('DOMContentLoaded', DragDrop.init);
