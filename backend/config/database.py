"""Parse reviewed libpq options without silently discarding TLS requirements."""
from urllib.parse import parse_qsl
from django.core.exceptions import ImproperlyConfigured


def connection_options(query):
    options = {"connect_timeout": 5}
    allowed = {"sslmode", "sslrootcert", "sslcert", "sslkey", "connect_timeout", "application_name"}
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=12)
        seen = set()
        for key, value in pairs:
            if key not in allowed or key in seen or not value:
                raise ValueError()
            seen.add(key)
            if key == "sslmode" and value not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
                raise ValueError()
            if key == "connect_timeout":
                value = int(value)
                if not 1 <= value <= 30:
                    raise ValueError()
            options[key] = value
    except (ValueError, TypeError):
        # Do not include the DSN, credential or certificate path in an error.
        raise ImproperlyConfigured("Unsupported or invalid DATABASE_URL connection options") from None
    return options
