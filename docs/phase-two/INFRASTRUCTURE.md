# Infrastructure evidence — 0.3.1

Date: 2026-10-24. This report supersedes the open Docker blocker in the historical
phase-one handoff; those original hash-identified historical packages remain unchanged.

## Verified

- Full Compose backend/migrate/worker/beat/frontend images built successfully.
- A new `begamnagam-g2` Compose project was created with fresh named data volumes,
  subnet `10.253.242.0/24`, loopback web3080/API8088. Existing local3000 data and
  unrelated project services were not replaced.
- PostgreSQL17, Redis7.4, RabbitMQ4.4 (official image digest
  `sha256:5b70d54d53d0ce9558b84ad93cb237d06fa2e8c57115fa0ff7223b9eaffa44ed`),
  migrations, backend, independent Celery worker/beat and frontend reached healthy.
- `check_foundation` passed inside the clean backend.
- All 46 backend tests passed inside the final container against its own PostgreSQL
  test database and Redis15, with zero skips. The fixed120-case corpus is included. `pip check` found no broken requirements.
- Frontend10 tests, TypeScript and production build passed locally. The complete
  frontend image also built successfully.
- Actual broker/worker/beat outage: paid order stayed queued in PostgreSQL while
  publish failed; after restart, outbox reconciliation completed the same order.
  Repeated demo payment returned the same order. Database inspection of every paid
  order in the isolated stack found exactly one capture and one delivery attempt.
- Demo smoke and manifest/icon/worker-header checks ran against the clean web
  origin `http://localhost:3080`; no live SMS, OTP, AI or payment was called.

Celery5.6 initially failed with RabbitMQ4.4 `Queue.declare (541)` because its
transient non-exclusive event/control queues are no longer permitted. Event and
control queues now use exclusive ownership; task queues remain durable with
persistent messages, late acknowledgement and worker-loss rejection. No deprecated
RabbitMQ feature was re-enabled. The actual clean-stack smoke passed after this
fix. See [Celery configuration](https://docs.celeryq.dev/en/v5.6.3/userguide/configuration.html)
and [RabbitMQ queues](https://www.rabbitmq.com/docs/queues).

A separate first startup attempt was made while image builds were still consuming CPU;
RabbitMQ diagnostics briefly failed, then its next healthcheck passed. Repeating
startup after build completion reached healthy without weakening authentication
or healthcheck configuration.

## Outage check performed

On the isolated demo stack only, stop `worker beat rabbitmq`, then create/pay a
demo order. The API must return `queued` and `financial_status: verified`, even
when publishing is deferred. Start RabbitMQ with `docker compose start --wait
rabbitmq`, then start worker/beat. Poll the same order until `delivered_demo`,
repeat its `pay-demo` request, and inspect the capture/delivery counts. The actual
run passed; it was not a mocked connection exception. This checks complete
broker outage and recovery, not a crash midway through a real provider call.

## Dependency resolution

A slow connection to the official package CDN prevented earlier pip builds.
Official wheels were fetched and checked against the SHA-256 values in PyPI's
HTTPS release metadata. The optional `backend/wheels` cache is ignored by Git;
only its empty directory marker is tracked. No binaries or credentials are committed.
Docker preinstalls locally cached wheels without network access and validates the
fully pinned `requirements.lock.txt`; without this cache, normal official pip
resolution remains available. TLS checks were never disabled and version pins
were not downgraded.

`requirements.txt` lists direct dependencies; `requirements.lock.txt` includes the
resolved transitive versions tested in the Linux image. Docker and backend CI use
the lock. A fresh clone needs registry/CDN access, or a compatible verified wheel
cache. A cached successful build is not proof that the external network has recovered.

## Repeat (default local ports)

```sh
python3 scripts/init-local.py
docker compose up --build -d --wait --wait-timeout 300
python3 scripts/smoke.py
make foundation-check
docker compose run --rm -e DJANGO_TESTING=1 -e REDIS_URL=redis://redis:6379/15 backend python manage.py test --noinput
```

To populate a Linux wheel cache on an ARM development host, use a Python environment
with pip and the lock (use x86_64 variants for an Intel Linux build):

```sh
python -m pip download -r backend/requirements.lock.txt --dest backend/wheels --only-binary=:all: --python-version 3.13 --platform manylinux_2_28_aarch64 --platform manylinux2014_aarch64 --abi cp313 --abi abi3
```

An optional smaller helper `python3 scripts/cache-crypto-wheel.py` caches and verifies
just the previously blocked cryptography artifact. Cache architecture must match
Docker's target; a macOS wheel does not validate a Linux container.

## Explicit limits

GitHub-hosted CI was not run, because nothing was pushed. Native localhost3000
still uses its previous local data/broker; the isolated clean-stack run is the
RabbitMQ4.4 evidence. Real-device Android/iOS installation, full WCAG evaluation,
rollback and later operational/provider/pilot gates remain NOT TESTED. They are
not represented as passed by these infrastructure checks.

After verification, only the isolated `begamnagam-g2` containers/network were
removed with `docker compose down`; named volumes were preserved. The native
preview at localhost3000 was rebuilt/restarted as0.3.1 and remains available.
