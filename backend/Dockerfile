ARG PYTHON_IMAGE=python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# The reviewed base still predates Debian's zlib security rebuild.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system app && useradd --system --gid app app
COPY requirements.txt /app/requirements.txt
COPY wheels/ /app/wheels/
COPY requirements.lock.txt /app/requirements.lock.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/app/wheels --disable-pip-version-check -r requirements.lock.txt \
    || pip install --find-links=/app/wheels --disable-pip-version-check --timeout 120 --retries 5 -r requirements.lock.txt
COPY --chown=app:app . /app
# Build-only random environment keys expire with this process. Runtime secrets
# are supplied by env_file; no real key is passed as an ARG or baked in the image.
RUN python -c "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; from config.ephemeral_environment import prepare_ephemeral_secrets; prepare_ephemeral_secrets(); from django.core.management import execute_from_command_line; execute_from_command_line(['manage.py','collectstatic','--noinput'])" \
    && chown -R app:app /app/staticfiles \
    && python -m pip uninstall --yes pip \
    && rm -rf /app/wheels /root/.cache/pip
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "45", "--access-logfile", "-", "--access-logformat", "%(m)s %(U)s %(s)s %(L)s"]
