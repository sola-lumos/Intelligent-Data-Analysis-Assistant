.PHONY: install-backend install-frontend dev-backend dev-frontend test-backend test-frontend verify-langchain

install-backend:
	test -d backend/.venv || (cd backend && python3 -m venv .venv)
	cd backend && .venv/bin/pip install -U pip -q && .venv/bin/pip install -r requirements-dev.txt -q

install-frontend:
	cd frontend && npm install

test-backend:
	cd backend && PYTHONPATH=. .venv/bin/python -m pytest

verify-langchain:
	cd backend && PYTHONPATH=. .venv/bin/python scripts/langchain_integration_check.py

test-frontend:
	cd frontend && npm run build

dev-backend:
	cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev
