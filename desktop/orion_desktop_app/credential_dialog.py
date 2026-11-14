from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QHBoxLayout, QMessageBox,
)

from credential_store import save_credentials, get_username, has_credentials, clear_credentials


class CredentialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Identifiants sauvegardés — Orion ERP Desktop")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Identifiants de connexion")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #F7F2E7;")
        layout.addWidget(title)

        note = QLabel(
            "Les identifiants sont stockés dans le Windows Credential Manager.\n"
            "Ils seront auto-remplis à chaque ouverture de la page de connexion."
        )
        note.setStyleSheet("color: #7A7468; font-size: 11px; font-style: italic;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addWidget(QLabel("Identifiant"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Email ou nom d'utilisateur")
        self.username_input.setText(get_username())
        self.username_input.setStyleSheet(self._field_style())
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("Mot de passe"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(self._field_style())
        layout.addWidget(self.password_input)

        security_note = QLabel(
            "Le mot de passe n'est jamais stocké dans un fichier texte, "
            ".env ou base de données locale."
        )
        security_note.setStyleSheet("color: #7A7468; font-size: 10px; font-style: italic;")
        security_note.setWordWrap(True)
        layout.addWidget(security_note)

        layout.addSpacing(8)

        btns = QHBoxLayout()

        save_btn = QPushButton("Enregistrer")
        save_btn.setStyleSheet(self._btn_primary_style())
        save_btn.clicked.connect(self._save)

        clear_btn = QPushButton("Supprimer")
        clear_btn.setStyleSheet(self._btn_danger_style())
        clear_btn.clicked.connect(self._clear)
        clear_btn.setEnabled(has_credentials())

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setStyleSheet(self._btn_style())
        cancel_btn.clicked.connect(self.reject)

        btns.addWidget(save_btn)
        btns.addWidget(clear_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _save(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Champs manquants", "L'identifiant et le mot de passe sont obligatoires.")
            return
        save_credentials(username, password)
        QMessageBox.information(
            self, "Identifiants sauvegardés",
            f"Identifiant « {username} » sauvegardé dans le coffre Windows.\n"
            "Il sera auto-rempli à la prochaine ouverture de la page de connexion."
        )
        self.accept()

    def _clear(self):
        if QMessageBox.question(
            self, "Supprimer les identifiants",
            "Supprimer l'identifiant et le mot de passe du coffre Windows ?"
        ) == QMessageBox.StandardButton.Yes:
            clear_credentials()
            QMessageBox.information(self, "Supprimé", "Identifiants supprimés du coffre Windows.")
            self.accept()

    def _field_style(self):
        return (
            "background-color: #17171B; color: #F7F2E7; "
            "border: 1px solid rgba(214,179,106,0.28); border-radius: 8px; "
            "padding: 8px 12px; font-size: 13px;"
        )

    def _btn_style(self):
        return (
            "background-color: #1B1B20; color: #F7F2E7; "
            "border: 1px solid rgba(214,179,106,0.28); border-radius: 10px; "
            "padding: 9px 14px; font-weight: bold; font-size: 13px;"
        )

    def _btn_primary_style(self):
        return (
            "background-color: #D6B36A; color: #09090B; "
            "border: none; border-radius: 10px; "
            "padding: 9px 14px; font-weight: bold; font-size: 13px;"
        )

    def _btn_danger_style(self):
        return (
            "background-color: #1B1B20; color: #E88; "
            "border: 1px solid rgba(220,80,80,0.4); border-radius: 10px; "
            "padding: 9px 14px; font-weight: bold; font-size: 13px;"
        )
