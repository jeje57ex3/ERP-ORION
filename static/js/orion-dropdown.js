/**
 * Orion ERP — Dropdown léger
 * Pour les dropdowns non-Bootstrap : [data-orion-dropdown] + [data-orion-dropdown-menu]
 */
(function () {
  'use strict';

  function initDropdowns() {
    document.querySelectorAll('[data-orion-dropdown]').forEach(function (trigger) {
      if (trigger._orionDropdownInit) return;
      trigger._orionDropdownInit = true;

      var menuId = trigger.getAttribute('data-orion-dropdown');
      var menu   = menuId ? document.getElementById(menuId) : trigger.nextElementSibling;
      if (!menu) return;

      menu.style.display = 'none';

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = menu.style.display !== 'none';
        closeAll();
        if (!open) {
          menu.style.display = 'block';
          trigger.setAttribute('aria-expanded', 'true');
          positionMenu(trigger, menu);
        }
      });
    });
  }

  function closeAll() {
    document.querySelectorAll('[data-orion-dropdown]').forEach(function (trigger) {
      var menuId = trigger.getAttribute('data-orion-dropdown');
      var menu   = menuId ? document.getElementById(menuId) : trigger.nextElementSibling;
      if (menu) menu.style.display = 'none';
      trigger.setAttribute('aria-expanded', 'false');
    });
  }

  function positionMenu(trigger, menu) {
    var rect = trigger.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.top      = (rect.bottom + 4) + 'px';
    menu.style.left     = rect.left + 'px';
    /* Ajuster si déborde à droite */
    var menuW = menu.offsetWidth;
    if (rect.left + menuW > window.innerWidth - 16) {
      menu.style.left = (rect.right - menuW) + 'px';
    }
    menu.style.zIndex = '200';
  }

  document.addEventListener('click', closeAll);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });

  document.addEventListener('DOMContentLoaded', initDropdowns);

  /* Ré-initialiser après du contenu AJAX */
  window.orionDropdownInit = initDropdowns;

})();
