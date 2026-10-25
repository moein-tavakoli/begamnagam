"""Pure origin checks shared by settings startup and provider dispatch guards."""
import ipaddress
import re
from urllib.parse import urlparse


def local_otp_origin_allowed(origin, internal_host, public_host=""):
    parsed = urlparse(origin)
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(internal_host)
        private = any(address in ipaddress.ip_network(network) for network in
                      ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
        domain = bool(public_host and len(public_host) <= 253 and re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", public_host))
        return bool(private and (parsed.hostname == internal_host or
                                (domain and parsed.hostname == public_host)) and parsed.scheme == "https"
                    and parsed.port in {None, 443} and not parsed.username and not parsed.password
                    and not parsed.query and not parsed.fragment and parsed.path in {"", "/"})
    except ValueError:
        return False
