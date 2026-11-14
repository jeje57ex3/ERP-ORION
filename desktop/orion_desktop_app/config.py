APP_NAME = "Orion ERP Desktop"
APP_VERSION = "1.0.0"

DEFAULT_ERP_URL = "https://login.elysiums.fr"

ALLOWED_DOMAINS = [
    "login.elysiums.fr",
    "elysiums.fr",
    "localhost",
    "127.0.0.1",
]

HEALTH_ENDPOINTS = [
    "/health/",
    "/ha/public-health/",
    "/",
]
