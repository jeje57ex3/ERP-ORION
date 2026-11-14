import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QGroupBox, QFormLayout,
)
from PySide6.QtWebEngineCore import QWebEngineProfile

from config import DEFAULT_ERP_URL
from health import normalize_url, check_server
from settings_store import load_settings, save_settings


class DesktopSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres — Orion ERP Desktop")
        self.setMinimumWidth(500)
        self.settings_changed = False
        self._settings = load_settings()

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Paramètres")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F7F2E7;")
        layout.addWidget(title)

        # ── Serveur ───────────────────────────────────────────────────────────
        server_group = QGroupBox("Serveur ERP")
        server_group.setStyleSheet(
            "QGroupBox { border: 1px solid rgba(214,179,106,0.28); border-radius: 10px; "
            "margin-top: 14px; padding: 16px 12px 12px 12px; color: #D6B36A; font-weight: bold; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )
        form = QFormLayout(server_group)
        form.setSpacing(10)

        self.url_input = QLineEdit()
        self.url_input.setText(self._settings.get("erp_url", DEFAULT_ERP_URL))
        self.url_input.setPlaceholderText("https://login.elysiums.fr")
        self.url_input.setStyleSheet(self._field_style())
        form.addRow("URL ERP", self.url_input)

        layout.addWidget(server_group)

        # ── Boutons principaux ────────────────────────────────────────────────
        actions = QHBoxLayout()

        save_btn = QPushButton("Enregistrer")
        save_btn.setStyleSheet(self._btn_primary_style())
        save_btn.clicked.connect(self._save)

        test_btn = QPushButton("Tester la connexion")
        test_btn.setStyleSheet(self._btn_style())
        test_btn.clicked.connect(self._test_connection)

        actions.addWidget(save_btn)
        actions.addWidget(test_btn)
        layout.addLayout(actions)

        # ── Session ───────────────────────────────────────────────────────────
        session_group = QGroupBox("Session & Sécurité")
        session_group.setStyleSheet(
            "QGroupBox { border: 1px solid rgba(214,179,106,0.28); border-radius: 10px; "
            "margin-top: 14px; padding: 16px 12px 12px 12px; color: #D6B36A; font-weight: bold; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )
        session_layout = QVBoxLayout(session_group)
        session_layout.setSpacing(8)

        note = QLabel(
            "La session est gérée par les cookies du navigateur intégré (Chromium).\n"
            "Vider les données de session vous déconnecte de l'ERP."
        )
        note.setStyleSheet("color: #7A7468; font-size: 11px; font-style: italic;")
        note.setWordWrap(True)
        session_layout.addWidget(note)

        clear_cache_btn = QPushButton("Vider le cache navigateur")
        clear_cache_btn.setStyleSheet(self._btn_style())
        clear_cache_btn.clicked.connect(self._clear_cache)
        session_layout.addWidget(clear_cache_btn)

        logout_btn = QPushButton("Déconnexion (vider la session + cookies)")
        logout_btn.setStyleSheet(self._btn_danger_style())
        logout_btn.clicked.connect(self._logout)
        session_layout.addWidget(logout_btn)

        layout.addWidget(session_group)

        # ── Fermer ────────────────────────────────────────────────────────────
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet(self._btn_style())
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _save(self):
        url = normalize_url(self.url_input.text().strip()) or DEFAULT_ERP_URL
        self._settings["erp_url"] = url
        save_settings(self._settings)
        self.settings_changed = True
        QMessageBox.information(self, "Paramètres sauvegardés", f"URL ERP : {url}")

    def _test_connection(self):
        url = normalize_url(self.url_input.text().strip()) or DEFAULT_ERP_URL
        result = check_server(url)
        if result["ok"]:
            QMessageBox.information(self, "Connexion réussie", result["message"])
        else:
            QMessageBox.warning(self, "Connexion impossible", result["message"])

    def _clear_cache(self):
        if QMessageBox.question(
            self, "Vider le cache",
            "Vider le cache du navigateur intégré ?"
        ) == QMessageBox.StandardButton.Yes:
            profile = QWebEngineProfile.defaultProfile()
            profile.clearHttpCache()
            QMessageBox.information(self, "Cache vidé", "Le cache navigateur a été vidé.")

    def _logout(self):
        if QMessageBox.question(
            self, "Déconnexion",
            "Supprimer tous les cookies et données de session ?\n\n"
            "Vous serez déconnecté de l'ERP au rechargement."
        ) == QMessageBox.StandardButton.Yes:
            profile = QWebEngineProfile.defaultProfile()
            profile.clearHttpCache()
            profile.cookieStore().deleteAllCookies()
            self.settings_changed = True
            QMessageBox.information(
                self, "Déconnecté",
                "Session supprimée. La page ERP va se recharger."
            )
            self.accept()

    # ── Styles inline (pas de feuille globale dans cette app) ─────────────────

    def _field_style(self):
        return (
            "background-color: #17171B; color: #F7F2E7; "
            "border: 1px solid rgba(214,179,106,0.28); border-radius: 8px; "
            "padding: 8px 12px; min-height: 20px; font-size: 13px;"
        )

    def _btn_style(self):
        return (
            "background-color: #1B1B20; color: #F7F2E7; "
            "border: 1px solid rgba(214,179,106,0.28); border-radius: 10px; "
            "padding: 9px 16px; font-weight: bold; font-size: 13px;"
        )

    def _btn_primary_style(self):
        return (
            "background-color: #D6B36A; color: #09090B; "
            "border: none; border-radius: 10px; "
            "padding: 9px 16px; font-weight: bold; font-size: 13px;"
        )

    def _btn_danger_style(self):
        return (
            "background-color: #1B1B20; color: #E88; "
            "border: 1px solid rgba(220,80,80,0.4); border-radius: 10px; "
            "padding: 9px 16px; font-weight: bold; font-size: 13px;"
        )
