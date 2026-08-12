import socket


def resolve_a_records(domain):
    try:
        _, _, ips = socket.gethostbyname_ex(domain)
        return sorted(set(ips))
    except Exception:
        return []


def domain_points_to_expected_ip(domain, expected_ip):
    if not expected_ip:
        return False, []
    ips = resolve_a_records(domain)
    return expected_ip in ips, ips


def get_root_zone_from_domain(domain):
    parts = domain.split('.')
    if len(parts) < 2:
        return domain
    return '.'.join(parts[-2:])
