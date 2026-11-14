import webbrowser

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QToolBar,
    QMessageBox,
    QStatusBar,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from config import APP_NAME, APP_VERSION, ALLOWED_DOMAINS
from credential_store import get_username, get_password, has_credentials
from health import normalize_url
from settings_store import load_settings

LOGIN_PATH = "/accounts/login/"


class OrionWebPage(QWebEnginePage):
    """
    Garde la navigation dans les domaines Orion autorisés.
    Les liens externes s'ouvrent dans le navigateur système.
    """

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        host = url.host().lower()

        if not host:
            return True

        allowed = any(
            host == domain or host.endswith("." + domain)
            for domain in ALLOWED_DOMAINS
        )

        if allowed:
            return True

        webbrowser.open(url.toString())
        return False


class OrionDesktopWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings_data = load_settings()
        self.erp_url = normalize_url(self.settings_data.get("erp_url"))

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(
            int(self.settings_data.get("window_width", 1400)),
            int(self.settings_data.get("window_height", 900)),
        )

        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.setHttpUserAgent(
            "OrionERPDesktop/1.0 " + self.profile.httpUserAgent()
        )
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        self.webview = QWebEngineView()
        self.page = OrionWebPage(self.profile, self.webview)
        self.webview.setPage(self.page)

        self._configure_webview()
        self._build_toolbar()

        self.setCentralWidget(self.webview)
        self.setStatusBar(QStatusBar())

        self.webview.loadStarted.connect(self._on_load_started)
        self.webview.loadFinished.connect(self._on_load_finished)
        self.webview.urlChanged.connect(self._on_url_changed)
        self.webview.titleChanged.connect(self._on_title_changed)

        if self.settings_data.get("start_maximized", True):
            self.showMaximized()

        self.load_erp()

    def _configure_webview(self):
        s = self.webview.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

    def _build_toolbar(self):
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        back_action = QAction("←", self)
        back_action.setToolTip("Retour")
        back_action.triggered.connect(self.webview.back)
        toolbar.addAction(back_action)

        forward_action = QAction("→", self)
        forward_action.setToolTip("Avancer")
        forward_action.triggered.connect(self.webview.forward)
        toolbar.addAction(forward_action)

        refresh_action = QAction("⟳", self)
        refresh_action.setToolTip("Rafraîchir (F5)")
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._hard_reload)
        toolbar.addAction(refresh_action)

        home_action = QAction("⌂  Accueil", self)
        home_action.setToolTip("Retour à l'accueil Orion ERP")
        home_action.triggered.connect(self.load_erp)
        toolbar.addAction(home_action)

        print_action = QAction("Imprimer", self)
        print_action.triggered.connect(self._print_page)
        toolbar.addAction(print_action)

        creds_action = QAction("🔑  Identifiants", self)
        creds_action.setToolTip("Sauvegarder les identifiants de connexion (coffre Windows)")
        creds_action.triggered.connect(self._open_credentials)
        toolbar.addAction(creds_action)

        settings_action = QAction("⚙  Paramètres", self)
        settings_action.setToolTip("Paramètres de l'application")
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

    def load_erp(self):
        self.webview.setUrl(QUrl(self.erp_url))

    def _hard_reload(self):
        """Recharge en ignorant le cache — un ERP ne doit jamais afficher de données/UI obsolètes."""
        self.webview.triggerPageAction(QWebEnginePage.WebAction.ReloadAndBypassCache)

    def _open_credentials(self):
        from credential_dialog import CredentialDialog
        CredentialDialog(self).exec()

    def _open_settings(self):
        from settings_dialog import DesktopSettingsDialog
        dialog = DesktopSettingsDialog(self)
        dialog.exec()
        if dialog.settings_changed:
            from settings_store import load_settings
            refreshed = load_settings()
            new_url = normalize_url(refreshed.get("erp_url", self.erp_url))
            if new_url:
                self.erp_url = new_url
            self.load_erp()

    def _print_page(self):
        self.webview.page().runJavaScript("window.print();")

    def _on_load_started(self):
        self.statusBar().showMessage("Chargement Orion ERP...")

    def _on_load_finished(self, ok):
        if ok:
            self.statusBar().showMessage("Orion ERP chargé.")
            self._try_autofill()
        else:
            self.statusBar().showMessage("Erreur de chargement.")
            self._show_offline_page()

    def _try_autofill(self):
        path = self.webview.url().path()
        if LOGIN_PATH not in path:
            return
        if not has_credentials():
            return

        username = get_username().replace("\\", "\\\\").replace("'", "\\'")
        password = get_password().replace("\\", "\\\\").replace("'", "\\'")

        js = f"""
(function() {{
  var u = document.getElementById('id_username');
  var p = document.getElementById('id_password');
  var r = document.getElementById('rememberMe');
  if (u) {{
    u.value = '{username}';
    u.dispatchEvent(new Event('input', {{bubbles: true}}));
    u.dispatchEvent(new Event('change', {{bubbles: true}}));
  }}
  if (p) {{
    p.value = '{password}';
    p.dispatchEvent(new Event('input', {{bubbles: true}}));
    p.dispatchEvent(new Event('change', {{bubbles: true}}));
  }}
  if (r) {{ r.checked = true; }}
}})();
"""
        self.webview.page().runJavaScript(js)

    def _on_url_changed(self, url):
        pass

    def _on_title_changed(self, title):
        if title:
            self.setWindowTitle(f"{title} — {APP_NAME}")
        else:
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")

    def _show_offline_page(self):
        html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #0B0B0D;
    color: #F7F2E7;
    font-family: "Segoe UI", Arial, sans-serif;
  }}
  .card {{
    width: min(680px, 90vw);
    padding: 34px;
    border: 1px solid rgba(214,179,106,.28);
    border-radius: 24px;
    background: #17171B;
    box-shadow: 0 18px 50px rgba(0,0,0,.32);
  }}
  .label {{
    color: #D6B36A;
    text-transform: uppercase;
    font-weight: 800;
    letter-spacing: .12em;
    font-size: 11px;
    margin: 0 0 16px;
  }}
  h1 {{ margin: 0 0 16px; font-size: 30px; }}
  p {{ color: #B9B2A3; line-height: 1.65; margin: 0 0 12px; }}
  code {{
    color: #F1DFA8;
    background: rgba(214,179,106,.1);
    padding: 2px 6px;
    border-radius: 4px;
  }}
  ul {{ color: #B9B2A3; padding-left: 20px; line-height: 1.8; margin: 0; }}
</style>
</head>
<body>
<div class="card">
  <p class="label">Orion ERP Desktop</p>
  <h1>Serveur Orion inaccessible</h1>
  <p>
    L'application Windows fonctionne correctement,
    mais elle ne peut pas joindre le serveur ERP à l'adresse :
    <br><br>
    <code>{self.erp_url}</code>
  </p>
  <p>Causes possibles :</p>
  <ul>
    <li>Connexion internet coupée</li>
    <li>Tunnel Cloudflare arrêté</li>
    <li>Serveur Django non lancé</li>
    <li>Erreur 502 / 503</li>
    <li>Domaine mal configuré</li>
  </ul>
</div>
</body>
</html>"""

        self.webview.setHtml(html)
