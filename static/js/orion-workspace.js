/**
 * Orion Workspace — Système d'onglets multitâche COMPLET (22 sections)
 *
 * §1  Tab bar + onglets                §12 Aperçu rapide au survol
 * §2  Protection brouillons            §13 Groupes d'onglets (couleurs)
 * §3  Raccourcis clavier               §14 Mode focus (plein contenu)
 * §4  Restauration de session          §15 Mise en veille auto des onglets
 * §5  Onglets épinglés                 §16 Pages récentes
 * §6  Drag-to-reorder                  §17 Détacher un onglet (new window)
 * §7  Historique ←/→ par onglet        §18 Détection hors-ligne
 * §8  Interception formulaires GET     §19 Sélecteur d'onglets (Ctrl+Shift+L)
 * §9  Restauration auto après POST     §20 Espaces de travail sauvegardés
 * §10 Vue divisée (split view)         §21 Redimensionnement séparateur
 * §11 Restauration split + workspaces  §22 Toast de confirmation
 */
const OWS = (() => {
  'use strict';

  /* ── Constants ──────────────────────────────────────────────── */
  const LS_KEY       = 'orion-ws-v1';
  const WS_SAVED_KEY = 'orion-ws-saved';
  const RECENT_KEY   = 'orion-ws-recent';
  const SS_FORM_KEY  = 'orion-ws-form-nav';
  const MAX_CLOSED   = 12;
  const MAX_RECENT   = 30;
  const SLEEP_MS     = 12 * 60 * 1000; // 12 min inactivity → sleep
  const SKIP_PATHS   = ['/accounts/logout', '/admin/', '/static/', '/media/'];
  const GROUP_COLORS = {
    red: '#e87878', orange: '#e8a060', yellow: '#d4c840',
    green: '#6bcf88', blue: '#5da8e8', purple: '#a878e8',
  };

  /* ── State ──────────────────────────────────────────────────── */
  let tabs        = [];     // full tab objects
  let activeL     = null;   // active id in left pane
  let activeR     = null;   // active id in right pane
  let focusPane   = 'l';
  let splitMode   = false;
  let focusMode   = false;
  let closedStack = [];
  let recentPages = [];     // [{url, title, visitedAt}]
  let dragTabId   = null;
  let sleepTimers = {};     // {tabId: timeoutId}

  function activeId()  { return focusPane === 'l' ? activeL : activeR; }
  function _activeTab(){ return tabs.find(t => t.id === activeId()) || null; }

  /* ── DOM refs ───────────────────────────────────────────────── */
  let $tabBar, $tabsList, $panels, $paneL, $paneR, $splitter;
  let $btnBack, $btnFwd, $btnSplit, $ctxMenu, $switcher;
  let ctxTargetId = null;

  /* ================================================================
     §1 INIT
  ================================================================ */
  function init() {
    const $main      = document.getElementById('orionContent');
    const $orionMain = document.getElementById('orionMain');
    const $topbar    = document.getElementById('orionTopbar');
    if (!$main || !$orionMain) return;

    /* ── Tab bar ──────────────────────────────────────────── */
    $tabBar   = ce('div'); $tabBar.id = 'orionWsTabBar';
    $tabsList = ce('div'); $tabsList.className = 'ows-tabs';

    const $nav = ce('div'); $nav.className = 'ows-nav-btns';
    $btnBack = _iconBtn('bi-chevron-left',  'Précédent (Alt+←)');
    $btnFwd  = _iconBtn('bi-chevron-right', 'Suivant (Alt+→)');
    $btnBack.disabled = true; $btnFwd.disabled = true;
    $btnBack.addEventListener('click', () => { const t = _activeTab(); if (t) navBack(t.id); });
    $btnFwd.addEventListener ('click', () => { const t = _activeTab(); if (t) navForward(t.id); });
    $nav.append($btnBack, $btnFwd);

    const $barR = ce('div'); $barR.className = 'ows-bar-actions';
    const $bNew     = _iconBtn('bi-plus',                            'Nouvel onglet (Ctrl+T)');
    const $bSwitch  = _iconBtn('bi-layout-text-sidebar-reverse',     'Onglets (Ctrl+Shift+L)');
    $btnSplit        = _iconBtn('bi-layout-split',                   'Vue divisée (Ctrl+\\)');
    const $bFocus   = _iconBtn('bi-fullscreen',                      'Mode focus (Ctrl+Shift+F)');
    const $bRecent  = _iconBtn('bi-clock-history',                   'Pages récentes');
    const $bWorksp  = _iconBtn('bi-bookmark-star',                   'Espaces de travail');
    $bNew.addEventListener   ('click', _dupActive);
    $bSwitch.addEventListener('click', _showSwitcher);
    $btnSplit.addEventListener('click', toggleSplit);
    $bFocus.addEventListener ('click', toggleFocusMode);
    $bRecent.addEventListener('click', e => { e.stopPropagation(); _showRecentMenu($bRecent); });
    $bWorksp.addEventListener('click', e => { e.stopPropagation(); _showWorkspaceMenu($bWorksp); });
    $barR.append($bNew, $bSwitch, $btnSplit, $bFocus, $bRecent, $bWorksp);

    $tabBar.append($nav, $tabsList, $barR);

    /* ── Panels area ──────────────────────────────────────── */
    $panels   = ce('div'); $panels.id = 'orionWsPanels';
    $paneL    = ce('div'); $paneL.className  = 'ows-pane ows-pane-l';
    $paneR    = ce('div'); $paneR.className  = 'ows-pane ows-pane-r ows-pane-hidden';
    $splitter = ce('div'); $splitter.className = 'ows-splitter ows-pane-hidden';
    $panels.append($paneL, $splitter, $paneR);
    _bindSplitterDrag();

    /* ── First panel ──────────────────────────────────────── */
    const $firstPanel = ce('div'); $firstPanel.className = 'ows-panel ows-panel-active';
    while ($main.firstChild) $firstPanel.appendChild($main.firstChild);
    $paneL.appendChild($firstPanel);

    /* ── Insert into layout ───────────────────────────────── */
    const anchor = $topbar ? $topbar.nextSibling : $main;
    $orionMain.insertBefore($tabBar,  anchor);
    $orionMain.insertBefore($panels,  $tabBar.nextSibling);
    $main.classList.add('ows-hidden'); $main.style.display = 'none';

    /* ── Register first tab ───────────────────────────────── */
    const firstUrl   = _norm(window.location.href);
    const firstTitle = _parseTitle(document.title);
    const firstTab   = _mkTab({ url: firstUrl, title: firstTitle, pane: 'l', panelEl: $firstPanel });
    firstTab.lastActive = Date.now();
    tabs.push(firstTab);
    activeL = firstTab.id;
    const $tEl = _renderTabEl(firstTab);
    $tabsList.appendChild($tEl);
    firstTab.tabEl = $tEl;
    $tEl.classList.add('ows-active', 'ows-active-l');

    document.body.classList.add('ows-ready');

    /* ── Boot ─────────────────────────────────────────────── */
    _loadRecent();
    _bindLinks();
    _bindForms();
    _bindKeyboard();
    _bindHistory();
    _bindQuickPreview();
    _bindOfflineDetection();
    _watchDirty(firstTab.id, $firstPanel);
    _checkRestore();
    window.addEventListener('beforeunload', _saveSession);
  }

  /* ================================================================
     TAB FACTORY
  ================================================================ */
  function _mkTab({ url, title = 'Chargement…', pinned = false, pane = 'l', group = null, panelEl = null } = {}) {
    const norm = _norm(url);
    return {
      id:          'ows-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6),
      url:         norm,
      title,
      pinned:      !!pinned,
      dirty:       false,
      scrollY:     0,
      timestamp:   Date.now(),
      lastActive:  null,
      pane,
      group,
      sleeping:    false,
      navHistory:  [norm],
      navIdx:      0,
      panelEl,
      tabEl:       null,
      _abortCtrl:  null,
    };
  }

  /* ================================================================
     §1 OPEN TAB
  ================================================================ */
  function openTab(url, { background = false, pinned = false, forceNew = false, pane = null, group = null } = {}) {
    if (_skip(url)) { window.location.href = url; return; }
    const norm = _norm(url);

    if (!forceNew) {
      const ex = tabs.find(t => t.url === norm);
      if (ex) { if (!background) activateTab(ex.id); return; }
    }

    const targetPane = pane || (splitMode ? focusPane : 'l');
    const $pane  = targetPane === 'r' ? $paneR : $paneL;
    const $panel = ce('div'); $panel.className = 'ows-panel';
    $pane.appendChild($panel);

    const tab    = _mkTab({ url: norm, pinned, pane: targetPane, group, panelEl: $panel });
    const insIdx = _insertIndex(tab);
    tabs.splice(insIdx, 0, tab);

    const $tabEl = _renderTabEl(tab);
    $tabsList.insertBefore($tabEl, $tabsList.children[insIdx] || null);
    tab.tabEl = $tabEl;

    if (!background) activateTab(tab.id);
    _loadContent(tab.id, norm);
    _saveSession();
  }

  function _insertIndex(tab) {
    if (tab.pinned) return tabs.filter(t => t.pinned).length;
    const ai  = tabs.findIndex(t => t.id === activeId());
    return ai >= 0 ? Math.min(ai + 1, tabs.length) : tabs.length;
  }

  function _navigateCurrent(url) {
    const tab = _activeTab();
    if (!tab) { openTab(url); return; }
    if (tab.dirty) {
      _dirtyDialog(tab).then(ok => { if (ok) { tab.dirty = false; _pushAndLoad(tab, url); } });
    } else {
      _pushAndLoad(tab, url);
    }
  }

  function _pushAndLoad(tab, url) {
    const norm = _norm(url);
    tab.navHistory = tab.navHistory.slice(0, tab.navIdx + 1);
    tab.navHistory.push(norm);
    tab.navIdx = tab.navHistory.length - 1;
    tab.url = norm;
    _updateTabEl(tab);
    _loadContent(tab.id, norm);
    _updateNavButtons();
  }

  /* ================================================================
     §1 ACTIVATE TAB
  ================================================================ */
  function activateTab(id) {
    const next = tabs.find(t => t.id === id);
    if (!next) return;

    const p      = next.pane;
    const prevId = p === 'l' ? activeL : activeR;
    const prev   = prevId ? tabs.find(t => t.id === prevId) : null;

    if (prev && prev !== next) {
      prev.scrollY = prev.panelEl ? prev.panelEl.scrollTop : 0;
      _setActive(prev, false);
      prev.panelEl && prev.panelEl.classList.remove('ows-panel-active');
      /* §15 Start sleep timer for deactivated tab */
      _startSleepTimer(prev.id);
    }

    if (p === 'l') activeL = id; else activeR = id;
    focusPane = p;
    next.timestamp  = Date.now();
    next.lastActive = Date.now();

    /* §15 Cancel sleep, wake if sleeping */
    _clearSleepTimer(id);
    if (next.sleeping) { next.sleeping = false; _loadContent(id, next.url); }

    _setActive(next, true);
    next.panelEl && next.panelEl.classList.add('ows-panel-active');

    if (next.scrollY && next.panelEl) {
      requestAnimationFrame(() => { if (next.panelEl) next.panelEl.scrollTop = next.scrollY; });
    }
    next.tabEl && next.tabEl.scrollIntoView({ block: 'nearest', inline: 'nearest' });

    history.replaceState({ owsTabId: id }, next.title, next.url);
    document.title = next.title + ' — Orion ERP';
    _updateNavButtons();
    _saveSession();
  }

  function _setActive(tab, on) {
    if (!tab.tabEl) return;
    tab.tabEl.classList.toggle('ows-active',   on && tab.pane === focusPane);
    tab.tabEl.classList.toggle('ows-active-l', on && tab.pane === 'l');
    tab.tabEl.classList.toggle('ows-active-r', on && tab.pane === 'r');
  }

  /* ================================================================
     §7 NAVIGATION HISTORY
  ================================================================ */
  function navBack(id) {
    const t = tabs.find(x => x.id === id);
    if (!t || t.navIdx <= 0) return;
    t.navIdx--; t.url = t.navHistory[t.navIdx]; _updateTabEl(t);
    _loadContent(id, t.url);
    if (id === activeId()) { history.replaceState({ owsTabId: id }, t.title, t.url); _updateNavButtons(); }
  }

  function navForward(id) {
    const t = tabs.find(x => x.id === id);
    if (!t || t.navIdx >= (t.navHistory || []).length - 1) return;
    t.navIdx++; t.url = t.navHistory[t.navIdx]; _updateTabEl(t);
    _loadContent(id, t.url);
    if (id === activeId()) { history.replaceState({ owsTabId: id }, t.title, t.url); _updateNavButtons(); }
  }

  function _updateNavButtons() {
    const t = _activeTab();
    if ($btnBack) $btnBack.disabled = !t || t.navIdx <= 0;
    if ($btnFwd)  $btnFwd.disabled  = !t || t.navIdx >= (t.navHistory || []).length - 1;
  }

  /* ================================================================
     §2 CLOSE TAB
  ================================================================ */
  async function closeTab(id) {
    const tab = tabs.find(t => t.id === id);
    if (!tab || tab.pinned) return;
    if (tab.dirty) { const ok = await _dirtyDialog(tab); if (!ok) return; }

    closedStack.push({ url: tab.url, title: tab.title });
    if (closedStack.length > MAX_CLOSED) closedStack.shift();

    _clearSleepTimer(id);
    if (tab._abortCtrl) tab._abortCtrl.abort();
    tab.tabEl  && tab.tabEl.remove();
    tab.panelEl && tab.panelEl.remove();
    tabs.splice(tabs.indexOf(tab), 1);

    if (!tabs.length) { window.location.href = '/'; return; }

    const wasActive = tab.pane === 'l' ? activeL === id : activeR === id;
    if (wasActive) {
      if (tab.pane === 'l') activeL = null; else activeR = null;
      const samePaneTabs = tabs.filter(t => t.pane === tab.pane);
      if (samePaneTabs.length) {
        const idx = tabs.indexOf(tab);
        activateTab(samePaneTabs[Math.min(idx, samePaneTabs.length - 1)].id);
      } else if (tab.pane === 'r') {
        _exitSplit();
      }
    }
    _saveSession();
  }

  async function closeOtherTabs(id) {
    for (const t of [...tabs]) { if (t.id !== id && !t.pinned) await closeTab(t.id); }
  }
  async function closeTabsToRight(id) {
    const idx = tabs.findIndex(t => t.id === id);
    for (const t of [...tabs]) { if (tabs.indexOf(t) > idx && !t.pinned) await closeTab(t.id); }
  }
  function reopenLastClosed() {
    const last = closedStack.pop();
    if (last) openTab(last.url, { background: false });
  }

  /* ================================================================
     §10 SPLIT VIEW
  ================================================================ */
  function toggleSplit() { splitMode ? _exitSplit() : _enterSplit(); }

  function _enterSplit() {
    splitMode = true;
    $panels.classList.add('ows-split');
    $paneR.classList.remove('ows-pane-hidden');
    $splitter.classList.remove('ows-pane-hidden');
    if ($btnSplit) { $btnSplit.classList.replace('bi-layout-split', 'bi-layout-sidebar-right-collapse'); $btnSplit.classList.add('ows-btn-active'); }
    if (!activeR) {
      const cur = _activeTab();
      openTab(cur ? cur.url : '/', { pane: 'r', forceNew: true, background: false });
    }
    _saveSession();
  }

  function _exitSplit() {
    splitMode = false;
    $panels.classList.remove('ows-split');
    $paneR.classList.add('ows-pane-hidden');
    $splitter.classList.add('ows-pane-hidden');
    if ($btnSplit) { $btnSplit.classList.replace('bi-layout-sidebar-right-collapse', 'bi-layout-split'); $btnSplit.classList.remove('ows-btn-active'); }
    tabs.filter(t => t.pane === 'r').forEach(t => {
      t.pane = 'l';
      if (t.panelEl) $paneL.appendChild(t.panelEl);
      if (t.tabEl) { t.tabEl.classList.remove('ows-active-r', 'ows-pane-r'); }
    });
    activeR = null; focusPane = 'l';
    $paneL.style.flex = ''; $paneR.style.flex = '';
    if (!activeL && tabs.length) activateTab(tabs[0].id);
    _saveSession();
  }

  function openInRight(id) {
    if (!splitMode) _enterSplit();
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    if (tab.pane !== 'r') {
      if (activeL === id) {
        activeL = null;
        const nextL = tabs.find(t => t.pane === 'l' && t.id !== id);
        if (nextL) activateTab(nextL.id);
      }
      tab.pane = 'r';
      if (tab.panelEl) $paneR.appendChild(tab.panelEl);
      if (tab.tabEl) tab.tabEl.classList.add('ows-pane-r');
    }
    activateTab(id);
  }

  /* §21 Splitter drag */
  function _bindSplitterDrag() {
    let startX, startLW;
    $splitter.addEventListener('mousedown', e => {
      e.preventDefault(); startX = e.clientX; startLW = $paneL.getBoundingClientRect().width;
      document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
      const onMove = ev => {
        const delta = ev.clientX - startX;
        const total = $panels.getBoundingClientRect().width - $splitter.offsetWidth;
        const lw    = Math.max(200, Math.min(total - 200, startLW + delta));
        $paneL.style.flex = `0 0 ${lw}px`; $paneR.style.flex = `0 0 ${total - lw}px`;
      };
      const onUp = () => {
        document.body.style.cursor = ''; document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp);
      };
      document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
    });
    $splitter.addEventListener('dblclick', () => { $paneL.style.flex = ''; $paneR.style.flex = ''; });
  }

  /* ================================================================
     §5 PIN  /  MISC
  ================================================================ */
  function togglePin(id) {
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    tab.pinned = !tab.pinned;
    const fi = tabs.indexOf(tab); tabs.splice(fi, 1);
    tabs.splice(tabs.filter(t => t.pinned).length, 0, tab);
    $tabsList.insertBefore(tab.tabEl, $tabsList.children[tabs.indexOf(tab)] || null);
    _updateTabEl(tab); _saveSession();
  }

  function duplicateTab(id) { const t = tabs.find(x => x.id === id); if (t) openTab(t.url, { forceNew: true, pane: t.pane }); }
  function copyTabLink(id)  { const t = tabs.find(x => x.id === id); if (t) navigator.clipboard.writeText(window.location.origin + t.url).catch(() => {}); }
  function refreshTab(id)   { const t = tabs.find(x => x.id === id); if (!t) return; t.dirty = false; _updateTabEl(t); _loadContent(id, t.url); }
  function _dupActive()     { const t = _activeTab(); if (t) openTab(t.url, { forceNew: true, pane: focusPane }); }

  /* §17 Detach tab */
  function detachTab(id) {
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    window.open(window.location.origin + tab.url, '_blank');
    closeTab(id);
  }

  /* ================================================================
     §13 TAB GROUPS
  ================================================================ */
  function setTabGroup(id, color) {
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    tab.group = color || null;
    _updateTabEl(tab);
    _saveSession();
  }

  /* ================================================================
     §14 FOCUS MODE
  ================================================================ */
  function toggleFocusMode() {
    focusMode = !focusMode;
    document.body.classList.toggle('ows-focus-mode', focusMode);
    const existing = document.getElementById('owsFocusExit');
    if (focusMode) {
      if (!existing) {
        const $btn = ce('button'); $btn.id = 'owsFocusExit'; $btn.className = 'ows-focus-exit';
        $btn.innerHTML = '<i class="bi bi-fullscreen-exit"></i>';
        $btn.title = 'Quitter le mode focus (Ctrl+Shift+F)';
        $btn.addEventListener('click', toggleFocusMode);
        document.body.appendChild($btn);
      }
    } else {
      if (existing) existing.remove();
    }
  }

  /* ================================================================
     §15 AUTO-SLEEP
  ================================================================ */
  function _startSleepTimer(id) {
    _clearSleepTimer(id);
    sleepTimers[id] = setTimeout(() => _sleepTab(id), SLEEP_MS);
  }
  function _clearSleepTimer(id) {
    if (sleepTimers[id]) { clearTimeout(sleepTimers[id]); delete sleepTimers[id]; }
  }
  function _sleepTab(id) {
    const tab = tabs.find(t => t.id === id);
    if (!tab || !tab.panelEl || tab.sleeping) return;
    if (activeL === id || activeR === id) return; // never sleep active tabs
    tab.sleeping = true;
    tab.panelEl.innerHTML =
      '<div class="ows-sleeping">' +
        '<i class="bi bi-moon-stars"></i>' +
        '<p>Onglet en veille</p>' +
        '<p class="sub">Cliquez pour recharger</p>' +
      '</div>';
    tab.dirty = false;
    _updateTabEl(tab);
  }

  /* ================================================================
     §16 RECENT PAGES
  ================================================================ */
  function _loadRecent() {
    try { recentPages = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch (_) { recentPages = []; }
  }
  function _trackRecent(url, title) {
    recentPages = recentPages.filter(p => p.url !== url);
    recentPages.unshift({ url, title, visitedAt: Date.now() });
    if (recentPages.length > MAX_RECENT) recentPages.pop();
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(recentPages)); } catch (_) {}
  }
  function _showRecentMenu($anchor) {
    const existing = document.getElementById('owsRecentMenu');
    if (existing) { existing.remove(); return; }
    if (!recentPages.length) { _showToast('Aucune page récente', 'bi-info-circle'); return; }
    const $menu = ce('div'); $menu.id = 'owsRecentMenu'; $menu.className = 'ows-ws-menu';
    $menu.innerHTML = recentPages.slice(0, 20).map(p =>
      `<button class="ows-ctx-item" data-url="${_esc(p.url)}">` +
        `<i class="bi bi-clock-history"></i>` +
        `<span class="ows-ws-name">${_esc(p.title || p.url)}</span>` +
        `<span class="ows-ws-meta">${_esc(p.url)}</span>` +
      '</button>'
    ).join('');
    $menu.addEventListener('click', e => {
      const $b = e.target.closest('[data-url]'); if (!$b) return;
      $menu.remove(); _navigateCurrent($b.dataset.url);
    });
    document.body.appendChild($menu);
    _positionMenu($menu, $anchor);
    setTimeout(() => { document.addEventListener('click', () => $menu.parentNode && $menu.remove(), { once: true }); }, 0);
  }

  /* ================================================================
     §12 QUICK PREVIEW
  ================================================================ */
  function _bindQuickPreview() {
    let hoverTimer = null;
    let $preview   = null;

    document.addEventListener('mouseover', e => {
      const $a = e.target.closest('a[href]');
      clearTimeout(hoverTimer);
      if (!$a) return;
      const href = $a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
      if ($a.hasAttribute('data-bs-toggle') || $a.hasAttribute('data-no-tab')) return;
      let url;
      try { url = new URL(href, window.location.origin); } catch (_) { return; }
      if (url.origin !== window.location.origin || _skip(url.pathname)) return;

      hoverTimer = setTimeout(() => {
        _showQuickPreview(url.href, $a.getBoundingClientRect());
      }, 650);
    });

    document.addEventListener('mouseout', e => {
      clearTimeout(hoverTimer);
      if (e.relatedTarget && e.relatedTarget.closest('#owsPreview')) return;
      /* Only hide if we're not moving into the preview itself */
      const $p = document.getElementById('owsPreview');
      if ($p && !e.relatedTarget) _hideQuickPreview();
    });

    document.addEventListener('click', () => _hideQuickPreview());
    document.addEventListener('keydown', e => { if (e.key === 'Escape') _hideQuickPreview(); });
  }

  function _showQuickPreview(url, rect) {
    _hideQuickPreview();
    const norm      = _norm(url);
    const cached    = recentPages.find(p => p.url === norm) || tabs.find(t => t.url === norm);
    const title     = cached ? cached.title : '';
    const $prev     = ce('div'); $prev.id = 'owsPreview';
    $prev.innerHTML =
      '<div class="ows-preview-title">' + _esc(title || norm) + '</div>' +
      '<div class="ows-preview-url">' + _esc(norm) + '</div>' +
      '<div class="ows-preview-hint"><kbd>Clic</kbd> naviguer · <kbd>Ctrl+Clic</kbd> nouvel onglet</div>';
    document.body.appendChild($prev);

    const pw = 270, vw = window.innerWidth;
    let left = rect.left;
    if (left + pw > vw - 8) left = vw - pw - 8;
    $prev.style.left = Math.max(8, left) + 'px';
    $prev.style.top  = (rect.bottom + 6) + 'px';

    $prev.addEventListener('mouseleave', _hideQuickPreview);

    /* Fetch title if unknown */
    if (!title) {
      fetch(norm, { headers: { 'X-Orion-Frame': '1' }, credentials: 'same-origin' })
        .then(res => {
          const t = res.headers.get('X-Orion-Frame-Title');
          if (t) {
            const $p = document.getElementById('owsPreview');
            if ($p) $p.querySelector('.ows-preview-title').textContent = t;
          }
          /* Cancel body download */
          return res.body ? res.body.cancel() : null;
        })
        .catch(() => {});
    }
  }

  function _hideQuickPreview() {
    const $p = document.getElementById('owsPreview');
    if ($p) $p.remove();
  }

  /* ================================================================
     §18 OFFLINE DETECTION
  ================================================================ */
  function _bindOfflineDetection() {
    let $banner = null;
    window.addEventListener('offline', () => {
      if ($banner) return;
      $banner = ce('div'); $banner.className = 'ows-offline-banner';
      $banner.innerHTML = '<i class="bi bi-wifi-off"></i> Connexion perdue — les pages ne peuvent pas être chargées';
      document.body.appendChild($banner);
    });
    window.addEventListener('online', () => {
      if ($banner) { $banner.remove(); $banner = null; }
      _showToast('Connexion rétablie', 'bi-wifi');
    });
  }

  /* ================================================================
     LOAD CONTENT
  ================================================================ */
  function _loadContent(id, url) {
    const tab = tabs.find(t => t.id === id);
    if (!tab || !tab.panelEl) return;
    const $panel = tab.panelEl;

    if (tab._abortCtrl) tab._abortCtrl.abort();
    const ctrl = new AbortController(); tab._abortCtrl = ctrl;

    tab.tabEl && tab.tabEl.classList.add('ows-loading');
    $panel.innerHTML =
      '<div class="ows-panel-loading">' +
        '<div class="ows-panel-loading-inner">' +
          '<div class="ows-panel-loading-spinner"></div><span>Chargement…</span>' +
        '</div>' +
      '</div>';

    fetch(url, {
      headers: { 'X-Orion-Frame': '1', 'X-Requested-With': 'XMLHttpRequest' },
      signal: ctrl.signal, credentials: 'same-origin', redirect: 'follow',
    })
    .then(res => {
      if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status });
      const finalUrl = res.url, frameTitle = res.headers.get('X-Orion-Frame-Title') || '';
      return res.text().then(html => ({ html, frameTitle, finalUrl }));
    })
    .then(({ html, frameTitle, finalUrl }) => {
      tab._abortCtrl = null;
      const doc    = new DOMParser().parseFromString(html, 'text/html');
      const isFrame = doc.body && doc.body.hasAttribute('data-frame-title');
      let content, title;
      if (isFrame) {
        content = doc.body.innerHTML;
        title   = frameTitle || doc.body.getAttribute('data-frame-title') || _parseTitle(doc.title);
      } else {
        const $m = doc.getElementById('orionContent');
        content  = $m ? $m.innerHTML : (doc.body ? doc.body.innerHTML : html);
        title    = frameTitle || _parseTitle(doc.title) || _titleFromUrl(finalUrl);
      }
      title   = title || _titleFromUrl(finalUrl || url);
      tab.url = _norm(finalUrl || url);
      tab.title = title; tab.dirty = false;
      if (tab.navHistory[tab.navIdx] !== tab.url) tab.navHistory[tab.navIdx] = tab.url;
      _updateTabEl(tab);
      $panel.innerHTML = content;
      _execScripts($panel);
      _initBs($panel);
      _watchDirty(id, $panel);
      /* §16 Track recent page */
      _trackRecent(tab.url, title);
      if (id === activeId()) {
        history.replaceState({ owsTabId: id }, title, tab.url);
        document.title = title + ' — Orion ERP';
        _updateNavButtons();
      }
      _saveSession();
    })
    .catch(err => {
      if (err.name === 'AbortError') return;
      tab._abortCtrl = null;
      tab.tabEl && tab.tabEl.classList.remove('ows-loading');
      $panel.innerHTML =
        '<div class="ows-panel-error">' +
          '<i class="bi bi-exclamation-triangle"></i>' +
          '<p>' + (err.status === 404 ? 'Page introuvable (404)' : 'Impossible de charger la page') + '</p>' +
          '<p class="sub">' + _esc(err.message) + '</p>' +
          '<button class="orion-btn sm" onclick="OWS.refreshTab(\'' + id + '\')">Réessayer</button>' +
        '</div>';
    });
  }

  function _execScripts($c) {
    $c.querySelectorAll('script:not([src])').forEach(o => {
      if (!o.textContent.trim()) return;
      const s = document.createElement('script'); s.textContent = o.textContent; o.replaceWith(s);
    });
  }
  function _initBs($c) {
    if (typeof bootstrap === 'undefined') return;
    $c.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => { try { new bootstrap.Tooltip(el); } catch (_) {} });
  }

  /* ================================================================
     §2 DIRTY STATE
  ================================================================ */
  function _watchDirty(id, $panel) {
    const mark = () => { const t = tabs.find(x => x.id === id); if (!t || t.dirty) return; t.dirty = true; _updateTabEl(t); };
    $panel.addEventListener('input',  mark, { capture: true, passive: true });
    $panel.addEventListener('change', mark, { capture: true, passive: true });
  }

  /* ================================================================
     §1 RENDER / UPDATE TAB ELEMENT
  ================================================================ */
  function _renderTabEl(tab) {
    const $el = ce('div');
    $el.className  = 'ows-tab' + (tab.pane === 'r' ? ' ows-pane-r' : '');
    $el.draggable  = true;
    $el.dataset.id = tab.id;
    $el.innerHTML  =
      '<span class="ows-tab-group-bar"></span>' +
      '<i class="ows-tab-pin bi bi-pin-fill"></i>' +
      '<i class="ows-tab-icon bi bi-window"></i>' +
      '<div class="ows-tab-spinner"></div>' +
      '<span class="ows-tab-title"></span>' +
      '<span class="ows-tab-dirty"></span>' +
      '<i class="ows-tab-sleep bi bi-moon"></i>' +
      '<button class="ows-tab-close bi bi-x" aria-label="Fermer"></button>';

    _applyTabClasses($el, tab);

    $el.addEventListener('click', e => {
      if (e.target.classList.contains('ows-tab-close')) return;
      activateTab(tab.id);
    });
    $el.querySelector('.ows-tab-close').addEventListener('click', e => { e.stopPropagation(); closeTab(tab.id); });
    $el.addEventListener('mouseup', e => { if (e.button === 1) { e.preventDefault(); closeTab(tab.id); } });
    $el.addEventListener('contextmenu', e => { e.preventDefault(); _showCtxMenu(tab.id, e.clientX, e.clientY); });

    /* §6 Drag */
    $el.addEventListener('dragstart', e => {
      dragTabId = tab.id; setTimeout(() => $el.classList.add('ows-dragging'), 0);
      e.dataTransfer.effectAllowed = 'move';
    });
    $el.addEventListener('dragend', () => {
      dragTabId = null; $el.classList.remove('ows-dragging');
      document.querySelectorAll('.ows-drag-over').forEach(n => n.classList.remove('ows-drag-over'));
    });
    $el.addEventListener('dragover', e => {
      e.preventDefault(); e.dataTransfer.dropEffect = 'move';
      document.querySelectorAll('.ows-drag-over').forEach(n => n.classList.remove('ows-drag-over'));
      if (dragTabId && dragTabId !== tab.id) $el.classList.add('ows-drag-over');
    });
    $el.addEventListener('drop', e => {
      e.preventDefault(); $el.classList.remove('ows-drag-over');
      if (dragTabId && dragTabId !== tab.id) _reorderTab(dragTabId, tab.id);
    });

    tab.tabEl = $el;
    return $el;
  }

  function _updateTabEl(tab) { if (tab.tabEl) _applyTabClasses(tab.tabEl, tab); }

  function _applyTabClasses($el, tab) {
    const $title = $el.querySelector('.ows-tab-title');
    if ($title) $title.textContent = tab.title || 'Chargement…';
    $el.classList.toggle('ows-pinned',   !!tab.pinned);
    $el.classList.toggle('ows-dirty',    !!tab.dirty);
    $el.classList.toggle('ows-pane-r',   tab.pane === 'r');
    $el.classList.toggle('ows-sleeping', !!tab.sleeping);
    $el.classList.remove('ows-loading');
    $el.title = tab.title || '';
    /* §13 Group color bar */
    const $bar = $el.querySelector('.ows-tab-group-bar');
    if ($bar) $bar.style.background = tab.group ? (GROUP_COLORS[tab.group] || 'transparent') : 'transparent';
  }

  /* ================================================================
     §6 DRAG REORDER
  ================================================================ */
  function _reorderTab(fromId, toId) {
    const fi = tabs.findIndex(t => t.id === fromId);
    const ti = tabs.findIndex(t => t.id === toId);
    if (fi < 0 || ti < 0 || fi === ti) return;
    const [tab] = tabs.splice(fi, 1);
    const ai = fi < ti ? ti : ti;
    tabs.splice(ai, 0, tab);
    $tabsList.insertBefore(tab.tabEl, $tabsList.children[ai] || null);
    _saveSession();
  }

  /* ================================================================
     CONTEXT MENU
  ================================================================ */
  function _showCtxMenu(id, x, y) {
    _hideCtxMenu(); ctxTargetId = id;
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    const idx     = tabs.indexOf(tab);
    const canBack = tab.navIdx > 0;
    const canFwd  = tab.navIdx < (tab.navHistory || []).length - 1;
    const hasR    = tabs.slice(idx + 1).some(t => !t.pinned);
    const hasOth  = tabs.some(t => t.id !== id && !t.pinned);

    /* §13 Build group color picker */
    const groupRow = '<div class="ows-ctx-group-row">' +
      '<span class="ows-ctx-group-label">Groupe :</span>' +
      '<button class="ows-gp-dot ows-gp-none" data-act="group" data-color="" title="Aucun">✕</button>' +
      Object.entries(GROUP_COLORS).map(([c, hex]) =>
        `<button class="ows-gp-dot${tab.group === c ? ' ows-gp-active' : ''}" data-act="group" data-color="${c}" style="background:${hex}" title="${_capFirst(c)}"></button>`
      ).join('') +
    '</div>';

    $ctxMenu = ce('div'); $ctxMenu.id = 'owsContextMenu';
    $ctxMenu.innerHTML =
      _ctxBtn('back',    'bi-chevron-left',           'Précédent',          'Alt+←',       false, !canBack) +
      _ctxBtn('fwd',     'bi-chevron-right',          'Suivant',            'Alt+→',       false, !canFwd) +
      _ctxBtn('refresh', 'bi-arrow-clockwise',        'Actualiser',         'Ctrl+R') +
      '<div class="ows-ctx-sep"></div>' +
      _ctxBtn('new',     'bi-plus',                   'Nouvel onglet',      'Ctrl+T') +
      _ctxBtn('dup',     'bi-copy',                   'Dupliquer') +
      _ctxBtn('detach',  'bi-box-arrow-up-right',     'Détacher (nouvel onglet)') +
      _ctxBtn('pin',     tab.pinned ? 'bi-pin' : 'bi-pin-fill', tab.pinned ? 'Désépingler' : 'Épingler') +
      _ctxBtn('right',   tab.pane === 'r' ? 'bi-layout-sidebar-right-collapse' : 'bi-layout-split',
              tab.pane === 'r' ? 'Déplacer à gauche' : 'Ouvrir à droite') +
      _ctxBtn('copy',    'bi-link-45deg',             'Copier le lien') +
      '<div class="ows-ctx-sep"></div>' +
      groupRow +
      '<div class="ows-ctx-sep"></div>' +
      (!tab.pinned ? _ctxBtn('close',       'bi-x-lg',      'Fermer',            'Ctrl+W') : '') +
      (hasOth      ? _ctxBtn('close-other', 'bi-x-circle',  'Fermer les autres') : '') +
      (hasR        ? _ctxBtn('close-right', 'bi-x-square',  'Fermer à droite') : '') +
      (closedStack.length ? _ctxBtn('reopen', 'bi-arrow-counterclockwise', 'Rouvrir fermé', 'Ctrl+Shift+T') : '');

    $ctxMenu.addEventListener('click', e => {
      const $b = e.target.closest('[data-act]'); if (!$b) return;
      const act = $b.dataset.act, tid = ctxTargetId;
      if (act === 'group') { setTabGroup(tid, $b.dataset.color); _hideCtxMenu(); return; }
      _hideCtxMenu();
      switch (act) {
        case 'back':        navBack(tid); break;
        case 'fwd':         navForward(tid); break;
        case 'refresh':     refreshTab(tid); break;
        case 'new':         _dupActive(); break;
        case 'dup':         duplicateTab(tid); break;
        case 'detach':      detachTab(tid); break;
        case 'pin':         togglePin(tid); break;
        case 'right':       openInRight(tid); break;
        case 'copy':        copyTabLink(tid); break;
        case 'close':       closeTab(tid); break;
        case 'close-other': closeOtherTabs(tid); break;
        case 'close-right': closeTabsToRight(tid); break;
        case 'reopen':      reopenLastClosed(); break;
      }
    });

    document.body.appendChild($ctxMenu);
    const w = $ctxMenu.offsetWidth || 210, h = $ctxMenu.offsetHeight || 260;
    $ctxMenu.style.left = Math.min(x, window.innerWidth  - w - 10) + 'px';
    $ctxMenu.style.top  = Math.min(y, window.innerHeight - h - 10) + 'px';
    setTimeout(() => {
      document.addEventListener('click',       _hideCtxMenu, { once: true });
      document.addEventListener('contextmenu', _hideCtxMenu, { once: true });
      document.addEventListener('keydown',     _ctxEsc);
    }, 0);
  }

  function _ctxEsc(e) {
    if (e.key === 'Escape') { _hideCtxMenu(); document.removeEventListener('keydown', _ctxEsc); }
  }
  function _hideCtxMenu() {
    if ($ctxMenu) { $ctxMenu.remove(); $ctxMenu = null; }
    document.removeEventListener('click', _hideCtxMenu);
    document.removeEventListener('contextmenu', _hideCtxMenu);
    document.removeEventListener('keydown', _ctxEsc);
  }
  function _ctxBtn(act, icon, label, kbd = '', danger = false, disabled = false) {
    return `<button class="ows-ctx-item${danger ? ' danger' : ''}${disabled ? ' ows-ctx-disabled' : ''}" data-act="${act}"${disabled ? ' disabled' : ''}>` +
      `<i class="bi ${icon}"></i>${_esc(label)}` + (kbd ? `<span class="ows-ctx-kbd">${_esc(kbd)}</span>` : '') + '</button>';
  }

  /* ================================================================
     §20 SAVED WORKSPACES
  ================================================================ */
  function _getSaved()     { try { return JSON.parse(localStorage.getItem(WS_SAVED_KEY) || '[]'); } catch (_) { return []; } }
  function _putSaved(arr)  { try { localStorage.setItem(WS_SAVED_KEY, JSON.stringify(arr)); } catch (_) {} }

  function saveWorkspace() {
    _wsNameDialog().then(name => {
      if (!name) return;
      const saved = _getSaved();
      saved.push({ name, savedAt: Date.now(), split: splitMode, tabs: tabs.map(t => ({ url: t.url, title: t.title, pinned: t.pinned, pane: t.pane, group: t.group })) });
      _putSaved(saved);
      _showToast('Espace « ' + name + ' » enregistré', 'bi-bookmark-check');
    });
  }

  function loadWorkspace(idx) {
    const ws = _getSaved()[idx];
    if (!ws) return;
    ws.tabs.forEach(t => openTab(t.url, { background: true, pinned: t.pinned, pane: t.pane || 'l', group: t.group }));
    if (ws.split && !splitMode) toggleSplit();
    _showToast('Espace « ' + ws.name + ' » restauré');
  }

  function deleteWorkspace(idx) {
    const saved = _getSaved(), name = saved[idx] ? saved[idx].name : '';
    saved.splice(idx, 1); _putSaved(saved);
    _showToast('Espace « ' + name + ' » supprimé');
  }

  function _wsNameDialog() {
    return new Promise(resolve => {
      const $ov = ce('div'); $ov.id = 'owsDirtyOverlay';
      $ov.innerHTML =
        '<div class="ows-dialog">' +
          '<p class="ows-dialog-title">Enregistrer l\'espace de travail</p>' +
          '<p class="ows-dialog-body">Nom pour cet ensemble de ' + tabs.length + ' onglet' + (tabs.length > 1 ? 's' : '') + ' :</p>' +
          '<input id="owsWsNameInput" class="ows-ws-name-input" placeholder="Ex : Chantier Martin" autocomplete="off">' +
          '<div class="ows-dialog-actions">' +
            '<button class="ows-dialog-btn cancel" data-r="0">Annuler</button>' +
            '<button class="ows-dialog-btn confirm-close" data-r="1">Enregistrer</button>' +
          '</div>' +
        '</div>';
      $ov.addEventListener('click', e => {
        const $b = e.target.closest('[data-r]'); if (!$b) return;
        $ov.remove(); resolve($b.dataset.r === '1' ? ($ov.querySelector('#owsWsNameInput').value.trim()) : '');
      });
      $ov.addEventListener('keydown', e => {
        if (e.key === 'Escape') { $ov.remove(); resolve(''); }
        if (e.key === 'Enter') { const v = $ov.querySelector('#owsWsNameInput').value.trim(); $ov.remove(); resolve(v); }
      });
      document.body.appendChild($ov);
      setTimeout(() => { const i = $ov.querySelector('#owsWsNameInput'); if (i) i.focus(); }, 40);
    });
  }

  function _showWorkspaceMenu($anchor) {
    const ex = document.getElementById('owsWsMenu'); if (ex) { ex.remove(); return; }
    const saved = _getSaved();
    const $menu = ce('div'); $menu.id = 'owsWsMenu'; $menu.className = 'ows-ws-menu';
    $menu.innerHTML =
      '<button class="ows-ctx-item" data-wact="save"><i class="bi bi-bookmark-plus"></i>Enregistrer l\'espace actuel…</button>' +
      (saved.length ? '<div class="ows-ctx-sep"></div>' : '') +
      saved.map((ws, i) =>
        '<div class="ows-ws-entry">' +
          `<button class="ows-ctx-item ows-ws-load" data-wact="load" data-idx="${i}">` +
            `<i class="bi bi-bookmark-fill"></i><span class="ows-ws-name">${_esc(ws.name)}</span>` +
            `<span class="ows-ws-meta">${ws.tabs.length} onglet${ws.tabs.length > 1 ? 's' : ''}</span>` +
          '</button>' +
          `<button class="ows-ws-del bi bi-trash" data-wact="del" data-idx="${i}" title="Supprimer"></button>` +
        '</div>'
      ).join('') +
      (saved.length === 0 ? '<div class="ows-sw-empty">Aucun espace sauvegardé</div>' : '');
    $menu.addEventListener('click', e => {
      const $b = e.target.closest('[data-wact]'); if (!$b) return;
      e.stopPropagation();
      const act = $b.dataset.wact, idx = parseInt($b.dataset.idx ?? '-1');
      $menu.remove();
      if (act === 'save') saveWorkspace();
      else if (act === 'load') loadWorkspace(idx);
      else if (act === 'del')  deleteWorkspace(idx);
    });
    document.body.appendChild($menu);
    _positionMenu($menu, $anchor);
    setTimeout(() => { document.addEventListener('click', () => $menu.parentNode && $menu.remove(), { once: true }); }, 0);
  }

  /* ================================================================
     §19 TAB SWITCHER
  ================================================================ */
  function _showSwitcher() {
    if ($switcher) { _hideSwitcher(); return; }
    $switcher = ce('div'); $switcher.id = 'owsSwitcher';
    const $box = ce('div'); $box.className = 'ows-sw-box';
    const $inp = ce('input'); $inp.type = 'text'; $inp.className = 'ows-sw-input';
    $inp.placeholder = 'Filtrer les onglets…'; $inp.autocomplete = 'off';
    const $list = ce('div'); $list.className = 'ows-sw-list';

    const _render = q => {
      $list.innerHTML = '';
      const lower = q.toLowerCase();
      const vis   = tabs.filter(t => !q || t.title.toLowerCase().includes(lower) || t.url.toLowerCase().includes(lower));
      if (!vis.length) {
        const $e = ce('div'); $e.className = 'ows-sw-empty'; $e.textContent = 'Aucun onglet trouvé'; return $list.appendChild($e);
      }
      vis.forEach(tab => {
        const isAct = tab.id === activeL || tab.id === activeR;
        const $i = ce('button'); $i.className = 'ows-sw-item' + (isAct ? ' ows-sw-active' : '');
        $i.innerHTML =
          `<span class="ows-sw-group-dot" style="background:${tab.group ? (GROUP_COLORS[tab.group] || 'transparent') : 'transparent'}"></span>` +
          `<i class="bi bi-window ows-sw-icon${tab.pane === 'r' ? ' ows-sw-right' : ''}"></i>` +
          `<span class="ows-sw-title">${_esc(tab.title)}</span>` +
          `<span class="ows-sw-url">${_esc(tab.url)}</span>` +
          (tab.dirty    ? '<span class="ows-sw-dot"></span>' : '') +
          (tab.sleeping ? '<i class="bi bi-moon ows-sw-sleep"></i>' : '');
        $i.addEventListener('click', () => { activateTab(tab.id); _hideSwitcher(); });
        $list.appendChild($i);
      });
    };

    _render('');
    $inp.addEventListener('input', () => _render($inp.value));
    $inp.addEventListener('keydown', e => {
      if (e.key === 'Escape') { _hideSwitcher(); return; }
      if (e.key === 'Enter') { const $f = $list.querySelector('.ows-sw-item'); if ($f) $f.click(); return; }
      const items = [...$list.querySelectorAll('.ows-sw-item')];
      if (!items.length) return;
      const ci = items.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); items[(ci + 1) % items.length].focus(); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); items[(ci - 1 + items.length) % items.length].focus(); }
    });

    $box.append($inp, $list);
    $switcher.appendChild($box);
    $switcher.addEventListener('click', e => { if (e.target === $switcher) _hideSwitcher(); });
    document.body.appendChild($switcher);
    $inp.focus();
  }
  function _hideSwitcher() { if ($switcher) { $switcher.remove(); $switcher = null; } }

  /* ================================================================
     §2 DIRTY DIALOG
  ================================================================ */
  function _dirtyDialog(tab) {
    return new Promise(resolve => {
      const $ov = ce('div'); $ov.id = 'owsDirtyOverlay';
      $ov.innerHTML =
        '<div class="ows-dialog">' +
          '<p class="ows-dialog-title">Modifications non sauvegardées</p>' +
          '<p class="ows-dialog-body">L\'onglet « <strong>' + _esc(tab.title) + '</strong> » contient des modifications non enregistrées.</p>' +
          '<div class="ows-dialog-actions">' +
            '<button class="ows-dialog-btn cancel" data-r="0">Annuler</button>' +
            '<button class="ows-dialog-btn confirm-close" data-r="1">Continuer quand même</button>' +
          '</div>' +
        '</div>';
      $ov.addEventListener('click', e => { const $b = e.target.closest('[data-r]'); if (!$b) return; $ov.remove(); resolve($b.dataset.r === '1'); });
      $ov.addEventListener('keydown', e => { if (e.key === 'Escape') { $ov.remove(); resolve(false); } });
      document.body.appendChild($ov);
      $ov.querySelector('.cancel').focus();
    });
  }

  /* ================================================================
     §8 FORM INTERCEPTION
  ================================================================ */
  function _bindForms() {
    document.addEventListener('submit', e => {
      const $f = e.target, method = ($f.method || 'get').toLowerCase();
      if (method === 'get') {
        let url; try { url = new URL($f.action || window.location.href, window.location.origin); } catch (_) { return; }
        if (url.origin !== window.location.origin || _skip(url.pathname)) return;
        e.preventDefault();
        new FormData($f).forEach((v, k) => { if (v !== '') url.searchParams.set(k, v); });
        _navigateCurrent(url.href);
      } else {
        _saveSession(); sessionStorage.setItem(SS_FORM_KEY, '1');
      }
    });
  }

  /* ================================================================
     §4/§9/§11 SESSION SAVE / RESTORE
  ================================================================ */
  function _saveSession() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({
        tabs: tabs.map(t => ({
          id: t.id, url: t.url, title: t.title, pinned: t.pinned,
          scrollY: t.scrollY || 0, timestamp: t.timestamp, pane: t.pane,
          group: t.group, navHistory: (t.navHistory || [t.url]).slice(-30), navIdx: t.navIdx || 0,
        })),
        activeL, activeR, focusPane, splitMode,
        closed: closedStack.slice(-MAX_CLOSED),
      }));
    } catch (_) {}
  }

  function _checkRestore() {
    try {
      const auto    = sessionStorage.getItem(SS_FORM_KEY);
      sessionStorage.removeItem(SS_FORM_KEY);
      const raw     = localStorage.getItem(LS_KEY);
      if (!raw) return;
      const data    = JSON.parse(raw);
      const curNorm = _norm(window.location.href);
      const toRest  = (data.tabs || []).filter(t => _norm(t.url) !== curNorm);
      if (!toRest.length) return;
      if (data.closed) closedStack = data.closed;

      const _restore = () => {
        toRest.forEach(t => openTab(t.url, { background: true, pinned: !!t.pinned, pane: t.pane || 'l', group: t.group }));
        if (data.splitMode && !splitMode) _enterSplit();
      };

      if (auto) {
        _restore();
      } else {
        const $bar = ce('div'); $bar.id = 'owsRestoreBar';
        const n = toRest.length;
        $bar.innerHTML =
          '<i class="bi bi-clock-history"></i>' +
          `<span>${n} onglet${n > 1 ? 's' : ''} précédent${n > 1 ? 's' : ''}</span>` +
          '<button class="ows-restore-btn primary" id="owsRestoreYes">Restaurer</button>' +
          '<button class="ows-restore-btn dismiss"  id="owsRestoreNo">Ignorer</button>';
        document.body.appendChild($bar);
        $bar.querySelector('#owsRestoreYes').addEventListener('click', () => { $bar.remove(); _restore(); });
        $bar.querySelector('#owsRestoreNo').addEventListener('click',  () => { $bar.remove(); localStorage.removeItem(LS_KEY); });
        setTimeout(() => { if ($bar.parentNode) $bar.remove(); }, 10000);
      }
    } catch (_) {}
  }

  /* ================================================================
     LINK INTERCEPTION
  ================================================================ */
  function _bindLinks() {
    document.addEventListener('click', e => {
      const $a = e.target.closest('a[href]'); if (!$a) return;
      const href = $a.getAttribute('href');
      if (!href || href === '#' || href.startsWith('javascript:') || href.startsWith('#')) return;
      if ($a.hasAttribute('data-bs-toggle') || $a.hasAttribute('data-bs-dismiss') || $a.hasAttribute('data-bs-target')) return;
      if ($a.hasAttribute('download') || $a.hasAttribute('data-no-tab')) return;
      if ($a.target === '_blank') return;
      let url; try { url = new URL(href, window.location.origin); } catch (_) { return; }
      if (url.origin !== window.location.origin || _skip(url.pathname)) return;
      e.preventDefault();
      if (e.ctrlKey || e.metaKey || e.button === 1) {
        openTab(url.href, { forceNew: true, background: !!e.shiftKey });
      } else {
        _navigateCurrent(url.href);
      }
    });
  }

  /* ================================================================
     §3 KEYBOARD SHORTCUTS
  ================================================================ */
  function _bindKeyboard() {
    document.addEventListener('keydown', e => {
      const ctrl = e.ctrlKey || e.metaKey;
      const alt  = e.altKey;

      if (ctrl && !e.shiftKey && e.key === 't')               { e.preventDefault(); _dupActive(); return; }
      if (ctrl && !e.shiftKey && e.key === 'w')               { e.preventDefault(); const t = _activeTab(); if (t) closeTab(t.id); return; }
      if (ctrl && e.shiftKey  && e.key.toLowerCase() === 't') { e.preventDefault(); reopenLastClosed(); return; }
      if (ctrl && !e.shiftKey && e.key === 'Tab')             { e.preventDefault(); _cycle(1); return; }
      if (ctrl && e.shiftKey  && e.key === 'Tab')             { e.preventDefault(); _cycle(-1); return; }
      if (ctrl && (e.key === 'r' || e.key === 'R'))           { e.preventDefault(); const t = _activeTab(); if (t) refreshTab(t.id); return; }
      if (e.key === 'F5')                                      { e.preventDefault(); const t = _activeTab(); if (t) refreshTab(t.id); return; }
      if (ctrl && e.key >= '1' && e.key <= '9')               { const t = tabs[parseInt(e.key) - 1]; if (t) { e.preventDefault(); activateTab(t.id); } return; }
      if (alt  && e.key === 'ArrowLeft')                      { e.preventDefault(); const t = _activeTab(); if (t) navBack(t.id); return; }
      if (alt  && e.key === 'ArrowRight')                     { e.preventDefault(); const t = _activeTab(); if (t) navForward(t.id); return; }
      if (ctrl && e.shiftKey && e.key.toLowerCase() === 'l') { e.preventDefault(); _showSwitcher(); return; }
      if (ctrl && e.shiftKey && e.key.toLowerCase() === 'f') { e.preventDefault(); toggleFocusMode(); return; }
      if (ctrl && e.key === '\\')                             { e.preventDefault(); toggleSplit(); return; }

      if (e.key === 'Escape') {
        if ($switcher) { _hideSwitcher(); return; }
        if ($ctxMenu)  { _hideCtxMenu(); return; }
        if (focusMode) { toggleFocusMode(); return; }
        const $m = document.getElementById('owsWsMenu') || document.getElementById('owsRecentMenu');
        if ($m) { $m.remove(); return; }
      }
    });
  }

  function _cycle(dir) {
    if (!tabs.length) return;
    const paneTabs = tabs.filter(t => t.pane === focusPane);
    if (!paneTabs.length) return;
    const cur = _activeTab();
    const idx = cur ? paneTabs.indexOf(cur) : -1;
    activateTab(paneTabs[(idx + dir + paneTabs.length) % paneTabs.length].id);
  }

  /* ================================================================
     BROWSER HISTORY
  ================================================================ */
  function _bindHistory() {
    window.addEventListener('popstate', e => {
      const id = e.state && e.state.owsTabId;
      if (id && tabs.find(t => t.id === id)) activateTab(id);
    });
  }

  /* ================================================================
     §22 TOAST
  ================================================================ */
  function _showToast(msg, icon = 'bi-check-circle') {
    const $t = ce('div'); $t.className = 'ows-toast';
    $t.innerHTML = `<i class="bi ${icon}"></i> ${_esc(msg)}`;
    document.body.appendChild($t);
    requestAnimationFrame(() => requestAnimationFrame(() => $t.classList.add('ows-toast-show')));
    setTimeout(() => { $t.classList.remove('ows-toast-show'); setTimeout(() => $t.remove(), 300); }, 3000);
  }

  /* ================================================================
     UTILITIES
  ================================================================ */
  function _norm(url) {
    try { const u = new URL(url, window.location.origin); return u.pathname + (u.search || ''); } catch (_) { return url; }
  }
  function _skip(url) {
    const path = typeof url === 'string' ? url : (url.pathname || '');
    return SKIP_PATHS.some(p => path.startsWith(p));
  }
  function _parseTitle(raw) { return (raw || '').split('—')[0].split('|')[0].trim() || 'Orion ERP'; }
  function _titleFromUrl(url) {
    try { const p = new URL(url, window.location.origin).pathname.split('/').filter(Boolean); return p[p.length - 1] || 'Orion'; } catch (_) { return 'Orion'; }
  }
  function _positionMenu($menu, $anchor) {
    const rect = $anchor.getBoundingClientRect();
    const mw   = $menu.offsetWidth || 240;
    $menu.style.top   = (rect.bottom + 6) + 'px';
    $menu.style.left  = 'auto';
    $menu.style.right = (window.innerWidth - Math.min(rect.right, window.innerWidth - 10)) + 'px';
  }
  function _capFirst(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }
  function ce(tag) { return document.createElement(tag); }
  function _iconBtn(iconClass, title) {
    const $b = ce('button'); $b.className = 'ows-btn-icon bi ' + iconClass; $b.title = title; return $b;
  }
  function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* ================================================================
     PUBLIC API
  ================================================================ */
  return {
    init, openTab, activateTab, closeTab, navBack, navForward,
    toggleSplit, openInRight, togglePin, duplicateTab, copyTabLink,
    refreshTab, reopenLastClosed, closeOtherTabs, closeTabsToRight,
    setTabGroup, toggleFocusMode, detachTab,
    saveWorkspace, loadWorkspace, deleteWorkspace,
  };
})();

document.addEventListener('DOMContentLoaded', OWS.init);
