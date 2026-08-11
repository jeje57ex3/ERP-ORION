/* ============================================================
   orion-site.js — Comportements partagés des sites publics Orion ERP
   (Électricité, BTP). Vanilla JS, aucune dépendance.
   ============================================================ */
'use strict';

/* ── Thème Dark / Light (persisté) ──────────────────────────── */
function initTheme() {
  const root = document.documentElement;
  const stored = localStorage.getItem('site-theme');
  if (stored) root.setAttribute('data-theme', stored);
  const btn = document.getElementById('siteThemeToggle');
  if (!btn) return;
  const sync = () => {
    const isLight = root.getAttribute('data-theme') === 'light';
    btn.innerHTML = isLight ? '<i class="bi bi-moon-stars-fill"></i>' : '<i class="bi bi-sun-fill"></i>';
    btn.setAttribute('aria-label', isLight ? 'Activer le mode sombre' : 'Activer le mode clair');
  };
  sync();
  btn.addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    localStorage.setItem('site-theme', next);
    sync();
  });
}

/* ── Navbar : compacte au scroll + menu mobile ──────────────── */
function initNav() {
  const header = document.querySelector('.site-header');
  if (header) {
    const onScroll = () => header.classList.toggle('is-compact', window.scrollY > 12);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
  const toggle = document.getElementById('siteMenuToggle');
  const nav = document.getElementById('siteNav');
  if (!toggle || !nav) return;
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open);
  });
  document.addEventListener('click', (e) => {
    if (!toggle.contains(e.target) && !nav.contains(e.target)) {
      nav.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
  });
}

/* ── Sélecteur de langue (bouton icône + menu déroulant) ─────── */
function initLangSwitcher() {
  const wrap = document.getElementById('siteLangSwitcher');
  const toggle = document.getElementById('siteLangToggle');
  if (!wrap || !toggle) return;
  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = wrap.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open);
  });
  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) {
      wrap.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { wrap.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
  });
}

/* ── Recherche (soumission simple vers le moteur de recherche du site) ── */
function initSearch() {
  const form = document.getElementById('siteSearchForm');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    const input = form.querySelector('input[type="search"]');
    if (!input || !input.value.trim()) e.preventDefault();
  });
}

/* ── Scroll reveal ───────────────────────────────────────────── */
function initReveal() {
  const els = document.querySelectorAll('.site-reveal');
  if (!els.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('site-revealed'); obs.unobserve(e.target); } });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
  els.forEach((el) => obs.observe(el));
}

/* ── Compteurs animés ────────────────────────────────────────── */
function initStats() {
  const els = document.querySelectorAll('[data-count]');
  if (!els.length) return;
  const animate = (el) => {
    const target = parseInt(el.dataset.count, 10) || 0;
    const duration = 1200;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - progress, 3)));
      if (progress < 1) requestAnimationFrame(step); else el.textContent = target;
    };
    requestAnimationFrame(step);
  };
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { animate(e.target); obs.unobserve(e.target); } });
  }, { threshold: 0.4 });
  els.forEach((el) => obs.observe(el));
}

/* ── Léger effet parallax (transform, pas de dépendance) ────── */
function initParallax() {
  const els = document.querySelectorAll('.site-parallax');
  if (!els.length) return;
  const onScroll = () => {
    els.forEach((el) => {
      const speed = parseFloat(el.dataset.speed || '0.15');
      const rect = el.getBoundingClientRect();
      const offset = (rect.top - window.innerHeight / 2) * speed;
      el.style.transform = `translate3d(0, ${offset * -0.05}px, 0)`;
    });
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/* ── FAQ accordéon ───────────────────────────────────────────── */
function initFaq() {
  document.querySelectorAll('.site-faq-q').forEach((btn) => {
    btn.setAttribute('aria-expanded', 'false');
    btn.addEventListener('click', () => {
      const item = btn.closest('.site-faq-item');
      const wasOpen = item.classList.contains('open');
      item.parentElement.querySelectorAll('.site-faq-item.open').forEach((i) => {
        i.classList.remove('open');
        i.querySelector('.site-faq-q')?.setAttribute('aria-expanded', 'false');
      });
      if (!wasOpen) { item.classList.add('open'); btn.setAttribute('aria-expanded', 'true'); }
    });
  });
}

/* ── Slider témoignages ──────────────────────────────────────── */
function initTestimonialSlider() {
  document.querySelectorAll('.site-testimonial-slider').forEach((slider) => {
    const track = slider.querySelector('.site-testimonial-track');
    const slides = slider.querySelectorAll('.site-testimonial-slide');
    const dotsWrap = slider.querySelector('.site-testimonial-nav');
    if (!track || slides.length < 2) return;
    let current = 0;
    const dots = [];
    if (dotsWrap) {
      slides.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.className = 'site-testimonial-dot' + (i === 0 ? ' active' : '');
        dot.setAttribute('aria-label', `Témoignage ${i + 1}`);
        dot.addEventListener('click', () => show(i));
        dotsWrap.appendChild(dot);
        dots.push(dot);
      });
    }
    function show(i) {
      current = (i + slides.length) % slides.length;
      track.style.transform = `translateX(-${current * 100}%)`;
      dots.forEach((d, di) => d.classList.toggle('active', di === current));
    }
    let timer = setInterval(() => show(current + 1), 6000);
    slider.addEventListener('mouseenter', () => clearInterval(timer));
    slider.addEventListener('mouseleave', () => { timer = setInterval(() => show(current + 1), 6000); });
  });
}

/* ── Galerie : filtres + lightbox ────────────────────────────── */
function initGallery() {
  document.querySelectorAll('.site-filter-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      const group = pill.closest('.site-filters');
      const filter = pill.dataset.filter;
      group.querySelectorAll('.site-filter-pill').forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      document.querySelectorAll('[data-category]').forEach((card) => {
        card.style.display = (filter === 'all' || card.dataset.category === filter) ? '' : 'none';
      });
    });
  });

  const lightbox = document.getElementById('siteLightbox');
  if (!lightbox) return;
  const lightboxImg = lightbox.querySelector('img');
  document.querySelectorAll('[data-lightbox]').forEach((trigger) => {
    trigger.addEventListener('click', (e) => {
      e.preventDefault();
      lightboxImg.src = trigger.dataset.lightbox;
      lightboxImg.alt = trigger.dataset.lightboxAlt || '';
      lightbox.classList.add('open');
    });
  });
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox || e.target.closest('.site-lightbox-close')) lightbox.classList.remove('open');
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') lightbox.classList.remove('open'); });
}

/* ── Modale ──────────────────────────────────────────────────── */
function initModals() {
  document.querySelectorAll('[data-modal-target]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      document.getElementById(trigger.dataset.modalTarget)?.classList.add('open');
    });
  });
  document.querySelectorAll('.site-modal-overlay').forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay || e.target.closest('[data-modal-close]')) overlay.classList.remove('open');
    });
  });
}

/* ── Toasts ──────────────────────────────────────────────────── */
function siteToast(message, type = 'info', duration = 4000) {
  let region = document.querySelector('.site-toast-region');
  if (!region) {
    region = document.createElement('div');
    region.className = 'site-toast-region';
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    document.body.appendChild(region);
  }
  const toast = document.createElement('div');
  toast.className = `site-toast ${type}`;
  toast.textContent = message;
  region.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}
window.siteToast = siteToast;

/* ── Bouton : effet ripple ───────────────────────────────────── */
function initRipple() {
  document.querySelectorAll('.site-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement('span');
      const size = Math.max(rect.width, rect.height);
      ripple.className = 'site-ripple';
      ripple.style.width = ripple.style.height = `${size}px`;
      ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
      ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 650);
    });
  });
}

/* ── Formulaires : validation instantanée ───────────────────── */
function initFormValidation() {
  document.querySelectorAll('form[data-validate]').forEach((form) => {
    form.querySelectorAll('input[required], textarea[required], input[type="email"]').forEach((input) => {
      const field = input.closest('.site-field');
      if (!field) return;
      const validate = () => {
        const valid = input.checkValidity();
        field.classList.toggle('is-invalid', !valid && input.value !== '');
        field.classList.toggle('is-valid', valid && input.value !== '');
      };
      input.addEventListener('input', validate);
      input.addEventListener('blur', validate);
    });
    form.addEventListener('submit', (e) => {
      if (!form.checkValidity()) {
        e.preventDefault();
        form.querySelectorAll(':invalid').forEach((el) => el.closest('.site-field')?.classList.add('is-invalid'));
      }
    });
  });
}

/* ── Configurateur : navigation par étapes (panneaux) ───────── */
function initWizardSteps() {
  document.querySelectorAll('form[data-wizard]').forEach((form) => {
    const panels = form.querySelectorAll('.site-step-panel');
    if (!panels.length) return;
    let current = 0;
    const progressSteps = form.querySelectorAll('.site-progress-step');
    const show = (idx) => {
      panels.forEach((p, i) => p.classList.toggle('active', i === idx));
      progressSteps.forEach((s, i) => { s.classList.toggle('done', i < idx); s.classList.toggle('current', i === idx); });
      current = idx;
      panels[idx].scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    form.querySelectorAll('[data-wizard-next]').forEach((btn) => {
      btn.addEventListener('click', () => { if (current < panels.length - 1) show(current + 1); });
    });
    form.querySelectorAll('[data-wizard-prev]').forEach((btn) => {
      btn.addEventListener('click', () => { if (current > 0) show(current - 1); });
    });
    show(0);
  });
}

/* ── Choix / pills sélectionnables ───────────────────────────── */
function initChoiceCards() {
  document.querySelectorAll('.site-choice-card, .site-pill').forEach((card) => {
    const input = card.querySelector('input');
    if (!input) return;
    const sync = () => card.classList.toggle('selected', input.checked);
    input.addEventListener('change', () => {
      if (input.type === 'radio') {
        document.querySelectorAll(`input[name="${input.name}"]`).forEach((i) => {
          i.closest('.site-choice-card, .site-pill')?.classList.remove('selected');
        });
      }
      sync();
    });
    sync();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNav();
  initLangSwitcher();
  initSearch();
  initReveal();
  initStats();
  initParallax();
  initFaq();
  initTestimonialSlider();
  initGallery();
  initModals();
  initRipple();
  initFormValidation();
  initWizardSteps();
  initChoiceCards();
});
