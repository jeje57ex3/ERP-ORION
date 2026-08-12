import requests as _requests


def check_url(url, timeout=12):
    result = {'url': url, 'ok': False, 'status_code': None, 'final_url': '', 'error': ''}
    try:
        resp = _requests.get(
            url, timeout=timeout, allow_redirects=True,
            headers={'User-Agent': 'OrionDomainDiagnostics/1.0'},
        )
        result['ok'] = resp.status_code < 500
        result['status_code'] = resp.status_code
        result['final_url'] = resp.url
    except Exception as exc:
        result['error'] = str(exc)
    return result


def check_http_https(domain):
    return {
        'http':  check_url(f'http://{domain}'),
        'https': check_url(f'https://{domain}'),
    }
