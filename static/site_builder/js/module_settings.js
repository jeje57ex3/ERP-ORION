/* module_settings.js — Dynamic settings form renderer */
const ModuleSettings = (() => {

  // image_url = text input + upload button + live preview
  const FIELDS = {
    hero: [
      { name: 'title',           label: 'Titre',              type: 'text' },
      { name: 'subtitle',        label: 'Sous-titre',         type: 'textarea' },
      { name: 'image',           label: 'Image de fond',      type: 'image_url' },
      { name: 'overlay_opacity', label: 'Opacité overlay',    type: 'range', min: 0, max: 100 },
      { name: 'cta_label',       label: 'Bouton (texte)',     type: 'text' },
      { name: 'cta_url',         label: 'Bouton (URL)',       type: 'text' },
      { name: 'bg_color',        label: 'Couleur de fond',    type: 'color' },
      { name: 'text_color',      label: 'Couleur du texte',   type: 'color' },
    ],
    text_image: [
      { name: 'title',      label: 'Titre',              type: 'text' },
      { name: 'body',       label: 'Contenu',            type: 'textarea' },
      { name: 'image',      label: 'Image',              type: 'image_url' },
      { name: 'image_side', label: "Côté de l'image",   type: 'select', choices: [['left','Gauche'],['right','Droite']] },
      { name: 'cta_label',  label: 'Bouton (texte)',     type: 'text' },
      { name: 'cta_url',    label: 'Bouton (URL)',       type: 'text' },
      { name: 'bg_color',   label: 'Couleur de fond',    type: 'color' },
      { name: 'text_color', label: 'Couleur du texte',   type: 'color' },
    ],
    product_grid: [
      { name: 'title',         label: 'Titre de section',   type: 'text' },
      { name: 'count',         label: 'Nombre de produits', type: 'number', min: 1, max: 24 },
      { name: 'category_slug', label: 'Catégorie (slug)',   type: 'text' },
      { name: 'bg_color',      label: 'Couleur de fond',    type: 'color' },
    ],
    collection_filter: [
      { name: 'title',    label: 'Titre',           type: 'text' },
      { name: 'bg_color', label: 'Couleur de fond', type: 'color' },
    ],
    gallery: [
      { name: 'title',    label: 'Titre',            type: 'text' },
      { name: 'columns',  label: 'Colonnes',         type: 'select', choices: [['2','2'],['3','3'],['4','4']] },
      { name: 'bg_color', label: 'Couleur de fond',  type: 'color' },
    ],
    features: [
      { name: 'title',      label: 'Titre de section', type: 'text' },
      { name: 'bg_color',   label: 'Couleur de fond',  type: 'color' },
      { name: 'text_color', label: 'Couleur du texte', type: 'color' },
    ],
    cta: [
      { name: 'title',      label: 'Titre',            type: 'text' },
      { name: 'subtitle',   label: 'Sous-titre',       type: 'text' },
      { name: 'cta_label',  label: 'Bouton (texte)',   type: 'text' },
      { name: 'cta_url',    label: 'Bouton (URL)',      type: 'text' },
      { name: 'bg_color',   label: 'Couleur de fond',  type: 'color' },
      { name: 'text_color', label: 'Couleur du texte', type: 'color' },
    ],
    faq: [
      { name: 'title',    label: 'Titre de section', type: 'text' },
      { name: 'bg_color', label: 'Couleur de fond',  type: 'color' },
    ],
    full_image: [
      { name: 'eyebrow',         label: 'Étiquette (au-dessus)',  type: 'text' },
      { name: 'title',           label: 'Titre',                  type: 'text' },
      { name: 'subtitle',        label: 'Texte descriptif',       type: 'textarea' },
      { name: 'image',           label: 'Image plein écran',      type: 'image_url' },
      { name: 'overlay_opacity', label: 'Assombrissement (%)',    type: 'range', min: 0, max: 90 },
      { name: 'min_height',      label: 'Hauteur minimale',       type: 'select', choices: [['50vh','Moitié écran'],['70vh','70% écran'],['100vh','Plein écran']] },
      { name: 'cta_label',       label: 'Bouton (texte)',         type: 'text' },
      { name: 'cta_url',         label: 'Bouton (lien)',          type: 'text' },
      { name: 'bg_color',        label: 'Couleur de fond',        type: 'color' },
      { name: 'text_color',      label: 'Couleur du texte',       type: 'color' },
    ],
    spacer: [
      { name: 'height',   label: 'Hauteur (px)',    type: 'range', min: 10, max: 300 },
      { name: 'bg_color', label: 'Couleur de fond', type: 'color' },
    ],
  };

  function esc(str) {
    return String(str ?? '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function getCsrf() {
    return document.getElementById('csrf-token')?.value || '';
  }

  function renderForm(moduleType, settings, sectionId, onChange) {
    const panel = document.getElementById('sb-settings-panel');
    const fields = FIELDS[moduleType] || [];

    let html = `<div class="sb-settings-header"><span class="sb-settings-module-type">${esc(moduleType)}</span></div>`;

    fields.forEach(f => {
      const val = settings[f.name] ?? '';
      html += `<div class="sb-field-group"><label class="sb-field-label">${esc(f.label)}</label>`;

      if (f.type === 'text') {
        html += `<input type="text" class="sb-field" name="${f.name}" value="${esc(val)}" data-sid="${sectionId}">`;

      } else if (f.type === 'textarea') {
        html += `<textarea class="sb-field sb-field-textarea" name="${f.name}" data-sid="${sectionId}">${esc(val)}</textarea>`;

      } else if (f.type === 'number') {
        html += `<input type="number" class="sb-field" name="${f.name}" value="${esc(val)}" min="${f.min||0}" max="${f.max||9999}" data-sid="${sectionId}">`;

      } else if (f.type === 'color') {
        const hex = /^#[0-9A-Fa-f]{6}$/.test(val) ? val : '#000000';
        html += `<div class="sb-color-wrap">
          <input type="color" class="sb-field sb-field-color" name="${f.name}" value="${hex}" data-sid="${sectionId}">
          <input type="text" class="sb-field sb-field-color-text" value="${esc(val)}" data-linked="${f.name}">
        </div>`;

      } else if (f.type === 'range') {
        const num = Number(val) || f.min || 0;
        html += `<div class="sb-range-wrap">
          <input type="range" class="sb-field sb-field-range" name="${f.name}" value="${num}" min="${f.min||0}" max="${f.max||100}" data-sid="${sectionId}">
          <span class="sb-range-value">${num}</span>
        </div>`;

      } else if (f.type === 'select') {
        html += `<select class="sb-field" name="${f.name}" data-sid="${sectionId}">`;
        (f.choices || []).forEach(([v, l]) => {
          html += `<option value="${esc(v)}"${v === String(val) ? ' selected' : ''}>${esc(l)}</option>`;
        });
        html += `</select>`;

      } else if (f.type === 'image_url') {
        // Image field: URL input + upload button + live preview
        const hasImg = !!val;
        html += `
          <div class="sb-image-wrap">
            <div class="sb-image-preview">
              ${hasImg
                ? `<img src="${esc(val)}" alt="" class="sb-image-preview-img">`
                : `<span class="sb-image-empty"><i class="bi bi-image"></i><br>Aucune image</span>`}
            </div>
            <div class="sb-image-controls">
              <input type="text" class="sb-field sb-image-url-input" name="${f.name}"
                     value="${esc(val)}" data-sid="${sectionId}" placeholder="https://…  ou uploadez →">
              <label class="sb-image-upload-btn" title="Uploader depuis votre ordinateur">
                <i class="bi bi-cloud-upload"></i>
                <input type="file" accept="image/jpeg,image/png,image/webp,image/gif,image/avif"
                       class="sb-image-file-input" style="display:none">
              </label>
            </div>
          </div>`;
      }

      html += `</div>`;
    });

    panel.innerHTML = html;

    // ── Event binding ────────────────────────────────────────────────────

    // Standard fields (text, number, range, select, color, textarea)
    panel.querySelectorAll('[data-sid]').forEach(el => {
      el.addEventListener('input', () => {
        syncRange(el, panel);
        syncColorText(el, panel);
        // For image URL text inputs: update preview
        if (el.classList.contains('sb-image-url-input')) {
          updateImagePreview(el);
        }
        const s = collectSettings(panel, sectionId, settings);
        onChange(sectionId, s);
      });
    });

    // Color text → picker sync
    panel.querySelectorAll('.sb-field-color-text').forEach(txt => {
      txt.addEventListener('change', () => {
        const v = txt.value.trim();
        const picker = panel.querySelector(`input[type="color"][name="${txt.dataset.linked}"]`);
        if (picker && /^#[0-9A-Fa-f]{6}$/.test(v)) {
          picker.value = v;
          picker.dispatchEvent(new Event('input'));
        }
      });
    });

    // Image file upload
    panel.querySelectorAll('.sb-image-file-input').forEach(fileInput => {
      fileInput.addEventListener('change', () => {
        const file = fileInput.files?.[0];
        if (!file) return;
        uploadImage(file, fileInput, sectionId, settings, onChange);
      });
    });
  }

  function updateImagePreview(urlInput) {
    const wrap = urlInput.closest('.sb-image-wrap');
    if (!wrap) return;
    const preview = wrap.querySelector('.sb-image-preview');
    if (!preview) return;
    const url = urlInput.value.trim();
    if (url) {
      preview.innerHTML = `<img src="${url}" alt="" class="sb-image-preview-img" onerror="this.style.opacity=.25">`;
    } else {
      preview.innerHTML = `<span class="sb-image-empty"><i class="bi bi-image"></i><br>Aucune image</span>`;
    }
  }

  async function uploadImage(file, fileInput, sectionId, settings, onChange) {
    const btn = fileInput.closest('.sb-image-upload-btn');
    const icon = btn?.querySelector('i');
    if (btn) btn.classList.add('uploading');
    if (icon) icon.className = 'bi bi-hourglass-split';

    const formData = new FormData();
    formData.append('image', file);

    try {
      const resp = await fetch('/erp/site-builder/upload-image/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrf() },
        body: formData,
      });
      const data = await resp.json();
      if (data.success) {
        const wrap = fileInput.closest('.sb-image-wrap');
        const urlInput = wrap?.querySelector('.sb-image-url-input');
        if (urlInput) {
          urlInput.value = data.url;
          updateImagePreview(urlInput);
          // Trigger save
          const panel = document.getElementById('sb-settings-panel');
          const s = collectSettings(panel, sectionId, settings);
          // Notify onChange
          const evt = new Event('input');
          urlInput.dispatchEvent(evt);
        }
      } else {
        showUploadError(btn, data.error || 'Erreur upload');
      }
    } catch (_) {
      showUploadError(btn, 'Erreur réseau');
    } finally {
      if (icon) icon.className = 'bi bi-cloud-upload';
      if (btn) btn.classList.remove('uploading');
      fileInput.value = '';
    }
  }

  function showUploadError(btn, msg) {
    if (!btn) return;
    const err = document.createElement('span');
    err.style.cssText = 'position:absolute;bottom:calc(100%+4px);left:50%;transform:translateX(-50%);background:#ef4444;color:#fff;font-size:11px;padding:3px 8px;border-radius:5px;white-space:nowrap;z-index:999;';
    err.textContent = msg;
    btn.style.position = 'relative';
    btn.appendChild(err);
    setTimeout(() => err.remove(), 3000);
  }

  function syncRange(el, panel) {
    if (el.type === 'range') {
      const wrap = el.closest('.sb-range-wrap');
      if (wrap) wrap.querySelector('.sb-range-value').textContent = el.value;
    }
  }

  function syncColorText(el, panel) {
    if (el.type === 'color') {
      const txt = panel.querySelector(`[data-linked="${el.name}"]`);
      if (txt) txt.value = el.value;
    }
  }

  function collectSettings(panel, sectionId, existing) {
    const out = Object.assign({}, existing);
    panel.querySelectorAll(`[data-sid="${sectionId}"]`).forEach(el => {
      if (!el.name) return;
      if (el.type === 'number' || el.type === 'range') {
        out[el.name] = Number(el.value);
      } else if (el.type === 'checkbox') {
        out[el.name] = el.checked;
      } else {
        out[el.name] = el.value;
      }
    });
    return out;
  }

  return { renderForm };
})();
