"""Read-only attestation of the loaded configuration and optional data services."""
import json
from urllib.parse import urlsplit
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Report security checks without printing DSNs/secrets or changing data, users, queues or provider state."

    def add_arguments(self, parser):
        parser.add_argument("--database", action="store_true", help="Read PostgreSQL role and connection metadata")
        parser.add_argument("--redis", action="store_true", help="Attempt an unauthenticated PING only")

    def handle(self, *args, **options):
        checks = []

        def record(name, state, detail):
            checks.append({"check": name, "state": state, "detail": detail})

        def expect(name, condition, detail, severity="warning"):
            record(name, "pass" if condition else severity, detail)

        expect("debug_disabled", not settings.DEBUG, "Public deployments require DEBUG=false", "error")
        expect("secure_cookies", settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE,
               "Both session and CSRF cookies must require HTTPS", "error")
        expect("host_only_cookies", settings.SESSION_COOKIE_DOMAIN is None and settings.CSRF_COOKIE_DOMAIN is None,
               "Cookie scope must remain limited to the application host", "error")
        expect("csrf_enabled", "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE,
               "All mutations, including capability actions, require CSRF", "error")
        expect("admin_login_throttle", "core.middleware.AdminLoginThrottle" in settings.MIDDLEWARE,
               "Admin password attempts need a shared, fail-closed rate limiter", "error")
        cache = settings.CACHES["default"]
        expect("cache_json_serializer", cache.get("OPTIONS", {}).get("serializer") == "core.cache.JSONSerializer",
               "Redis must never deserialize executable pickle values", "error")
        expect("celery_json_only", settings.CELERY_TASK_SERIALIZER == "json" and settings.CELERY_ACCEPT_CONTENT == ["json"],
               "Only JSON task messages are accepted", "error")
        expect("celery_remote_control_disabled", not settings.CELERY_WORKER_ENABLE_REMOTE_CONTROL,
               "Broker clients must not control worker processes", "error")
        broker = urlsplit(settings.CELERY_BROKER_URL)
        expect("rabbitmq_credentials", bool(broker.username and broker.password), "Use a dedicated broker credential")
        expect("rabbitmq_dedicated_vhost", broker.path not in {"", "/", "//"},
               "Use a dedicated vhost and restrict its configure/write/read permissions")
        redis_url = urlsplit(settings.REDIS_URL)
        expect("redis_credentials", bool(redis_url.password), "Use dedicated Redis ACL credentials")

        if options["database"]:
            if connection.vendor != "postgresql":
                record("postgres_role", "unknown", "The loaded connection is not PostgreSQL")
            else:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                                       "FROM pg_roles WHERE rolname = current_user")
                        role = cursor.fetchone()
                        expect("postgres_least_privilege_role", bool(role) and not any(role),
                               "Runtime role must have no superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS privileges", "error")
                        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = current_schema() "
                                       "AND tableowner = current_user), has_schema_privilege(current_user, current_schema(), 'CREATE')")
                        ownership = cursor.fetchone()
                        expect("postgres_separate_schema_owner", not any(ownership),
                               "Use a separate migration owner; runtime should not own tables or create schema objects")
                        cursor.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
                        row = cursor.fetchone()
                        expect("postgres_transport_tls", bool(row and row[0]),
                               "TLS is required across untrusted networks; loopback/isolated-host transport is a documented exception")
                except Exception:
                    record("postgres_role", "unknown", "Could not read role/connection metadata; no error or DSN was printed")
        else:
            record("postgres_role", "unknown", "Use --database on the actual deployment to attest its loaded role")

        if options["redis"] and redis_url.scheme in {"redis", "rediss"} and redis_url.hostname:
            from redis import Redis
            from redis.exceptions import AuthenticationError
            probe = Redis(host=redis_url.hostname, port=redis_url.port or 6379, ssl=redis_url.scheme == "rediss",
                          socket_timeout=3, socket_connect_timeout=3)
            try:
                reachable = probe.ping()
            except AuthenticationError:
                record("redis_anonymous_ping", "pass", "Unauthenticated connection was rejected")
            except Exception:
                record("redis_anonymous_ping", "unknown", "No connection/authentication conclusion; no exception details printed")
            else:
                record("redis_anonymous_ping", "warning" if reachable else "unknown",
                       "Unauthenticated PING was accepted; key/administration permissions were not probed")
            finally:
                probe.close()
        else:
            record("redis_anonymous_ping", "unknown", "Use --redis on the deployment; no cache values are read or written")

        record("network_firewall_and_rabbitmq_acls", "unknown",
               "Verify listeners, firewall, Redis ACLs and broker permissions on the actual host; config is not runtime evidence")
        self.stdout.write(json.dumps({"scope": "loaded_process_configuration", "read_only": True,
            "checks": checks, "errors": sum(check["state"] == "error" for check in checks)}, ensure_ascii=False, indent=2))
