# Orion ERP Desktop

Application Windows WebView pour utiliser Orion ERP comme une application native.

## Principe

L'application ne duplique pas l'ERP.
Elle charge le serveur Orion ERP dans une WebView.

Toutes les données restent sur le serveur.

## Installation développement

```powershell
cd desktop\orion_desktop_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Générer l'application Windows

```powershell
python build_exe.py
```

Le fichier sera généré dans :

```text
desktop/orion_desktop_app/dist/OrionERP-Desktop/OrionERP-Desktop.exe
```

## URL par défaut

```text
https://login.elysiums.fr
```

## Fonctionnement

```text
Application Windows → WebView → Serveur Orion ERP → Base de données serveur
```

## Cloudflare Tunnel

Le tunnel doit pointer vers :

```text
http://localhost:9000
```

Et Django doit être lancé :

```powershell
python manage.py runserver 127.0.0.1:9000
```
