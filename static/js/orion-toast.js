/**
 * Orion ERP — Toast v2
 * Usage : orionToast({ title, message, type: 'success'|'warning'|'danger'|'info', duration })
 */
window.orionToast = (function () {
  'use strict';

  var ICONS = {
    success: 'bi-check-lg',
    warning: 'bi-exclamation-circle',
    danger:  'bi-x-circle',
    info:    'bi-info-circle',
  };

  function getContainer() {
    var c = document.getElementById('orionToastContainerV2');
    if (!c) {
      c = document.createElement('div');
      c.id = 'orionToastContainerV2';
      c.className = 'orion-toast-container-v2';
      c.setAttribute('aria-live', 'polite');
      c.setAttribute('aria-atomic', 'true');
      document.body.appendChild(c);
    }
    return c;
  }

  function show(opts) {
    if (typeof opts === 'string') opts = { message: opts };
    var type     = opts.type     || 'info';
    var title    = opts.title    || { success:'Succès', warning:'Attention', danger:'Erreur', info:'Info' }[type] || '';
    var message  = opts.message  || '';
    var duration = opts.duration !== undefined ? opts.duration : 4000;
    var icon     = ICONS[type] || 'bi-info-circle';

    var toast = document.createElement('div');
    toast.className = 'orion-toast-v2 ' + type;
    toast.setAttribute('role', 'alert');
    toast.innerHTML =
      '<div class="orion-toast-icon"><i class="bi ' + icon + '"></i></div>' +
      '<div class="orion-toast-body">' +
        (title ? '<div class="orion-toast-title">' + title + '</div>' : '') +
        (message ? '<div class="orion-toast-message">' + message + '</div>' : '') +
      '</div>' +
      '<button class="orion-toast-close" aria-label="Fermer">×</button>';

    var container = getContainer();
    container.appendChild(toast);

    toast.querySelector('.orion-toast-close').addEventListener('click', function () {
      dismiss(toast);
    });

    if (duration > 0) {
      setTimeout(function () { dismiss(toast); }, duration);
    }

    return toast;
  }

  function dismiss(toast) {
    if (!toast || toast.classList.contains('dismissing')) return;
    toast.classList.add('dismissing');
    setTimeout(function () {
      if (toast.parentElement) toast.parentElement.removeChild(toast);
    }, 220);
  }

  /* Intercepte les messages Django auto-convertis en data-attributes */
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-orion-toast]').forEach(function (el) {
      show({
        message: el.getAttribute('data-orion-toast'),
        type:    el.getAttribute('data-toast-type') || 'info',
      });
      el.remove();
    });
  });

  return { show: show, dismiss: dismiss };
})();
