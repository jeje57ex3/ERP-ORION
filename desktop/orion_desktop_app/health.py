import requests

from config import HEALTH_ENDPOINTS


def normalize_url(url):
    url = str(url or "").strip()

    if not url:
        return ""

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    return url.rstrip("/")


def join_url(base_url, path):
    base_url = normalize_url(base_url)
    path = str(path or "/").strip()

    if not path.startswith("/"):
        path = "/" + path

    return base_url + path


def check_server(base_url, timeout=5):
    base_url = normalize_url(base_url)

    if not base_url:
        return {
            "ok": False,
            "message": "URL ERP vide.",
        }

    last_error = ""

    for endpoint in HEALTH_ENDPOINTS:
        url = join_url(base_url, endpoint)

        try:
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=False,
                headers={
                    "User-Agent": "OrionERPDesktop/1.0"
                },
            )

            if response.status_code in [200, 204, 301, 302, 303, 401, 403]:
                return {
                    "ok": True,
                    "url": url,
                    "status_code": response.status_code,
                    "message": f"Serveur accessible HTTP {response.status_code}",
                }

            last_error = f"Réponse inattendue HTTP {response.status_code}"

        except requests.exceptions.SSLError as exc:
            last_error = f"Erreur SSL : {exc}"

        except requests.exceptions.ConnectionError:
            last_error = "Connexion impossible au serveur Orion."

        except requests.exceptions.Timeout:
            last_error = "Le serveur Orion ne répond pas assez vite."

        except Exception as exc:
            last_error = str(exc)

    return {
        "ok": False,
        "message": last_error or "Serveur Orion inaccessible.",
    }
