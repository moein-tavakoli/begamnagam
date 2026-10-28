.PHONY: init up down logs test backend-test frontend-check smoke admin dev-ui

init:
	python3 scripts/init-local.py

# Initial full demo/release validation; do not use for UI edit loops.
up: init
	docker compose up --build -d --wait --wait-timeout 300

down:
	docker compose down

logs:
	docker compose logs --tail=100 -f backend worker frontend

test: backend-test frontend-check

backend-test:
	docker compose run --rm -e DJANGO_TESTING=1 -e REDIS_URL=redis://redis:6379/15 backend python manage.py test --noinput

frontend-check:
	cd frontend && npm ci && npm test && npm run typecheck && npm run build

smoke:
	python3 scripts/smoke.py

admin:
	docker compose exec backend python manage.py createsuperuser

.PHONY: foundation-check
foundation-check:
	docker compose exec -T backend python manage.py check_foundation
	python3 scripts/verify-foundation.py

# Backend is already available on localhost:8000. No Docker build or npm install.
dev-ui:
	cd frontend && npm run dev

# Explicit real product on loopback; preserves hot reload and isolates its data.
.PHONY: dev-product
dev-product:
	python3 scripts/dev-product.py
