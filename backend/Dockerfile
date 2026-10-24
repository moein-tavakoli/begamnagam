FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install --disable-pip-version-check --timeout 120 --retries 5 -r requirements.txt
COPY --chown=app:app . /app
RUN python manage.py collectstatic --noinput && chown -R app:app /app/staticfiles
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "--access-logfile", "-"]
