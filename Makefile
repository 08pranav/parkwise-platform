.PHONY: help install infra dev worker test lint format analyze flutter-test web-build seed

PY ?= python3
BACKEND = backend
API_BASE_URL ?= http://127.0.0.1:8000

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## Install backend and Flutter dependencies
	cd $(BACKEND) && $(PY) -m pip install -r requirements.txt -r requirements-dev.txt
	cd mobile && flutter pub get && dart pub global activate melos

infra: ## Start local PostgreSQL and Redis
	docker compose up -d db redis

dev: infra ## Run migrations and start the API on :8000
	cd $(BACKEND) && DB_HOST=localhost $(PY) manage.py migrate && DB_HOST=localhost $(PY) manage.py runserver

worker: ## Run the Celery worker with beat
	cd $(BACKEND) && DB_HOST=localhost celery -A parking_platform worker -B -l info

test: ## Backend tests (needs `make infra`)
	cd $(BACKEND) && DJANGO_SETTINGS_MODULE=parking_platform.settings.test pytest

lint: ## Ruff lint + format check
	cd $(BACKEND) && ruff check . && ruff format --check .

format: ## Auto-format backend and Flutter code
	cd $(BACKEND) && ruff check --fix . && ruff format .
	cd mobile && dart format .

analyze: ## Flutter analyze (all packages)
	cd mobile && melos run analyze

flutter-test: ## Flutter unit and widget tests
	cd mobile && melos run test

web-build: ## Build every Flutter app for web against API_BASE_URL
	./scripts/build-web.sh $(API_BASE_URL)
