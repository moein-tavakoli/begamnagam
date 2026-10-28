"""Loopback-only TLS WSGI development server; no request URLs in access logs."""
import os
from pathlib import Path
from socketserver import ThreadingMixIn
import ssl
import sys
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.local_live_settings":
    raise SystemExit("Only the isolated local product profile is permitted")

from django.core.wsgi import get_wsgi_application


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class Handler(WSGIRequestHandler):
    def get_environ(self):
        environ = super().get_environ()
        environ["HTTPS"] = "on"
        return environ

    def log_message(self, *_):
        pass


tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.minimum_version = ssl.TLSVersion.TLSv1_2
tls.load_cert_chain(root / ".local/local-product/localhost.crt", root / ".local/local-product/localhost.key")
with make_server("127.0.0.1", 8000, get_wsgi_application(), server_class=Server, handler_class=Handler) as server:
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
