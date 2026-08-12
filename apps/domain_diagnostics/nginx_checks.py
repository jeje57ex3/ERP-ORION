from pathlib import Path

NGINX_DIRS = [
    '/etc/nginx/sites-enabled',
    '/etc/nginx/conf.d',
]


def find_nginx_files_for_domain(domain):
    matches = []
    for folder in NGINX_DIRS:
        path = Path(folder)
        if not path.exists():
            continue
        for file_path in path.glob('*'):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(errors='ignore')
            except Exception:
                continue
            if domain in content:
                matches.append(str(file_path))
    return matches


def check_nginx_server_name(domain):
    files = find_nginx_files_for_domain(domain)
    return {'domain': domain, 'found': bool(files), 'files': files}
