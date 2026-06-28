/* ============================================================
   btp-site.js — Site vitrine BTP — Orion ERP
   ============================================================ */

'use strict';

/* ── Mobile nav ──────────────────────────────────────────────── */
function initNav() {
  const toggle = document.getElementById('btpMenuToggle');
  const nav    = document.getElementById('btpNav');
  if (!toggle || !nav) return;
  toggle.addEventListener('click', () => {
    nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', nav.classList.contains('open'));
  });
  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!toggle.contains(e.target) && !nav.contains(e.target)) {
      nav.classList.remove('open');
    }
  });
}

/* ── Sticky header shadow ────────────────────────────────────── */
function initHeaderShadow() {
  const header = document.querySelector('.btp-header');
  if (!header) return;
  const update = () => {
    header.style.boxShadow = window.scrollY > 8
      ? '0 2px 20px rgba(58,42,26,.13)'
      : '0 1px 4px rgba(58,42,26,.06)';
  };
  window.addEventListener('scroll', update, { passive: true });
  update();
}

/* ── Scroll reveal ───────────────────────────────────────────── */
function initReveal() {
  const els = document.querySelectorAll('.btp-reveal');
  if (!els.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add('btp-revealed');
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
  els.forEach((el) => obs.observe(el));
}

/* ── Portfolio filter pills ──────────────────────────────────── */
function initPortfolioFilter() {
  const pills = document.querySelectorAll('[data-filter]');
  const cards = document.querySelectorAll('[data-work-type]');
  if (!pills.length) return;

  pills.forEach((pill) => {
    pill.addEventListener('click', () => {
      pills.forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      const filter = pill.dataset.filter;

      cards.forEach((card) => {
        if (filter === 'all' || card.dataset.workType === filter) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });
}

/* ── Before / After slider ───────────────────────────────────── */
function initBeforeAfter() {
  document.querySelectorAll('.btp-before-after').forEach((el) => {
    const after = el.querySelector('.btp-ba-after');
    if (!after) return;
    let dragging = false;

    const update = (x) => {
      const rect = el.getBoundingClientRect();
      const pct  = Math.min(Math.max(((x - rect.left) / rect.width) * 100, 0), 100);
      after.style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
    };

    el.addEventListener('mousemove',  (e) => update(e.clientX));
    el.addEventListener('touchmove',  (e) => { e.preventDefault(); update(e.touches[0].clientX); }, { passive: false });
  });
}

/* ── Guided quote multi-step ────────────────────────────────── */
function initWizard() {
  const form  = document.getElementById('btpWizardForm');
  const steps = document.querySelectorAll('.btp-wizard-panel');
  if (!form || !steps.length) return;

  let current = 0;
  const total = steps.length;

  function showStep(idx) {
    steps.forEach((s, i) => s.classList.toggle('active', i === idx));
    updateProgress(idx);
    window.scrollTo({ top: form.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
  }

  function updateProgress(idx) {
    document.querySelectorAll('.btp-wizard-step').forEach((s, i) => {
      s.classList.toggle('active', i === idx);
      s.classList.toggle('done',   i < idx);
    });
    const bar = document.getElementById('btpWizardProgress');
    if (bar) bar.style.width = `${Math.round((idx / (total - 1)) * 100)}%`;
    const counter = document.getElementById('btpStepCounter');
    if (counter) counter.textContent = `Étape ${idx + 1} sur ${total}`;
  }

  document.querySelectorAll('[data-next]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (current < total - 1) { current++; showStep(current); }
    });
  });

  document.querySelectorAll('[data-prev]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (current > 0) { current--; showStep(current); }
    });
  });

  showStep(0);
}

/* ── File upload preview ─────────────────────────────────────── */
function initFileUpload() {
  document.querySelectorAll('.btp-file-zone').forEach((zone) => {
    const input   = zone.querySelector('input[type=file]');
    const preview = zone.querySelector('.btp-file-preview');
    if (!input) return;

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.style.borderColor = 'var(--btp-secondary)'; });
    zone.addEventListener('dragleave', () => zone.style.borderColor = '');
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.style.borderColor = '';
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event('change'));
      }
    });

    input.addEventListener('change', () => {
      if (!preview) return;
      preview.innerHTML = '';
      Array.from(input.files).forEach((f) => {
        const tag = document.createElement('span');
        tag.className = 'btp-tag';
        tag.textContent = f.name;
        preview.appendChild(tag);
      });
    });
  });
}

/* ── Counter animation ───────────────────────────────────────── */
function initCounters() {
  document.querySelectorAll('[data-count]').forEach((el) => {
    const target = parseInt(el.dataset.count, 10);
    if (!target) return;

    const obs = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      obs.unobserve(el);
      let start = 0;
      const step = Math.ceil(target / 50);
      const tick = () => {
        start = Math.min(start + step, target);
        el.textContent = start.toLocaleString('fr-FR');
        if (start < target) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.5 });
    obs.observe(el);
  });
}

/* ── Contact/emergency form ──────────────────────────────────── */
function initForms() {
  document.querySelectorAll('.btp-ajax-form').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      const honeypot = form.querySelector('[name=website_url_field]');
      if (honeypot && honeypot.value) { e.preventDefault(); return; }
      // Allow normal submit — server-side handles it
    });
  });
}

/* ── Smooth anchor scroll ────────────────────────────────────── */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const target = document.querySelector(a.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ── Star rating display ─────────────────────────────────────── */
function initStarRatings() {
  document.querySelectorAll('[data-rating]').forEach((el) => {
    const rating = parseInt(el.dataset.rating, 10) || 0;
    el.innerHTML = Array.from({ length: 5 }, (_, i) =>
      `<i class="bi ${i < rating ? 'bi-star-fill' : 'bi-star'}" style="color:${i < rating ? 'var(--btp-secondary)' : '#E3D5BD'}"></i>`
    ).join('');
  });
}

/* ── Init ────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initNav();
  initHeaderShadow();
  initReveal();
  initPortfolioFilter();
  initBeforeAfter();
  initWizard();
  initFileUpload();
  initCounters();
  initForms();
  initSmoothScroll();
  initStarRatings();
});

window.BTPSite = { initPortfolioFilter, initBeforeAfter };
