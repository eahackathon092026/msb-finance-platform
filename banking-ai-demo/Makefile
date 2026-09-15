# Makefile cho banking-ai-demo
# Yêu cầu: python3.12+, docker, kubectl, psql (cho các target db-*)

SERVICES := customer-profile-service transaction-service risk-scoring-service scam-knowledge-service action-feedback-service

REGISTRY ?= vcr.vngcloud.vn/114544-ea-hackathon
TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)

SERVICE ?= customer-profile-service
PORT ?= 8080
PYTHON ?= python3.12

REGISTRY_HOST ?= vcr.vngcloud.vn
NAMESPACE ?= finance-demo
PULL_SECRET ?= vcr-cred

SCHEMA := ../msb_guardian_schema.sql
SEED   := db/seed.sql

.PHONY: help test build run sync-common k8s-apply k8s-secret k8s-db-secret \
        db-init db-seed db-reset db-gen-seed db-test dev-up dev-down

help:
	@echo "Phát triển"
	@echo "  make sync-common  - đồng bộ services/_common/common.py vào 5 service"
	@echo "  make test         - chạy pytest cho tất cả service (không cần database)"
	@echo "  make run          - chạy 1 service local (SERVICE=<tên> PORT=<cổng>)"
	@echo "  make dev-up       - dựng Postgres trong docker + nạp schema + seed"
	@echo "  make dev-down     - xóa Postgres dev"
	@echo ""
	@echo "Database  (cần DATABASE_URL)"
	@echo "  make db-init      - nạp schema 18 bảng"
	@echo "  make db-gen-seed  - sinh lại db/seed.sql từ generator"
	@echo "  make db-seed      - nạp dữ liệu mẫu 10 khách hàng"
	@echo "  make db-reset     - db-init + db-seed"
	@echo "  make db-test      - chấm engine trên 10 fraud case (cần service đang chạy)"
	@echo ""
	@echo "Đóng gói & triển khai"
	@echo "  make build        - docker build tất cả service, tag = $(TAG)"
	@echo "  make k8s-db-secret- tạo secret chứa DATABASE_URL"
	@echo "  make k8s-secret   - tạo imagePullSecret '$(PULL_SECRET)'"
	@echo "  make k8s-apply    - apply toàn bộ manifest"

# --- Phát triển -------------------------------------------------------------
# Docker build context là services/<tên> nên mỗi service phải có bản copy riêng
# của common.py. services/_common/common.py là bản gốc duy nhất được sửa.
sync-common:
	@for svc in $(SERVICES); do \
		cp services/_common/common.py services/$$svc/common.py; \
		echo "  → services/$$svc/common.py"; \
	done
	@echo "Đã đồng bộ common.py vào $(words $(SERVICES)) service."

test: sync-common
	@failed=0; \
	for svc in $(SERVICES); do \
		echo "==> test $$svc"; \
		( cd services/$$svc && $(PYTHON) -m pytest -q ) || failed=1; \
	done; \
	exit $$failed

run: sync-common
	@echo "==> $(SERVICE) tại http://localhost:$(PORT)/docs  (Ctrl+C để dừng)"
	cd services/$(SERVICE) && $(PYTHON) -m pip install -q -r requirements.txt && \
		$(PYTHON) -m uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

# --- Database ---------------------------------------------------------------
db-init:
	@test -n "$(DATABASE_URL)" || { echo "ERROR: chưa đặt DATABASE_URL"; exit 1; }
	psql "$(DATABASE_URL)" -v ON_ERROR_STOP=1 -f $(SCHEMA)
	@echo "Đã nạp schema."

db-gen-seed:
	$(PYTHON) db/generate_seed.py > $(SEED)
	@echo "Đã sinh $(SEED)."

db-seed:
	@test -n "$(DATABASE_URL)" || { echo "ERROR: chưa đặt DATABASE_URL"; exit 1; }
	psql "$(DATABASE_URL)" -v ON_ERROR_STOP=1 -f $(SEED)
	@echo "Đã nạp dữ liệu mẫu."

db-reset: db-init db-seed

db-test:
	@test -n "$(DATABASE_URL)" || { echo "ERROR: chưa đặt DATABASE_URL"; exit 1; }
	$(PYTHON) db/run_fraud_tests.py

# Postgres dùng cho phát triển local, dữ liệu nằm trong container nên xóa là sạch.
dev-up:
	docker rm -f msb-dev-db 2>/dev/null || true
	docker run -d --name msb-dev-db -e POSTGRES_PASSWORD=guardian \
		-e POSTGRES_DB=guardian -p 5432:5432 postgres:16-alpine
	@echo "Chờ Postgres sẵn sàng..."
	@for i in $$(seq 1 40); do \
		docker exec msb-dev-db pg_isready -U postgres -d guardian >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	docker exec -i msb-dev-db psql -U postgres -d guardian -v ON_ERROR_STOP=1 < $(SCHEMA)
	docker exec -i msb-dev-db psql -U postgres -d guardian -v ON_ERROR_STOP=1 < $(SEED)
	@echo ""
	@echo "Sẵn sàng. Dùng:"
	@echo "  export DATABASE_URL='postgresql://postgres:guardian@localhost:5432/guardian'"

dev-down:
	docker rm -f msb-dev-db 2>/dev/null || true

# --- Đóng gói & triển khai --------------------------------------------------
build: sync-common
	@for svc in $(SERVICES); do \
		echo "==> build $(REGISTRY)/$$svc:$(TAG)"; \
		docker build -t $(REGISTRY)/$$svc:$(TAG) -t $(REGISTRY)/$$svc:latest services/$$svc || exit 1; \
	done

k8s-secret:
	@test -n "$(VCR_USERNAME)" || { echo "ERROR: chưa đặt VCR_USERNAME"; exit 1; }
	@test -n "$(VCR_PASSWORD)" || { echo "ERROR: chưa đặt VCR_PASSWORD"; exit 1; }
	kubectl apply -f k8s/namespace.yaml
	kubectl -n $(NAMESPACE) create secret docker-registry $(PULL_SECRET) \
		--docker-server=$(REGISTRY_HOST) \
		--docker-username=$(VCR_USERNAME) \
		--docker-password=$(VCR_PASSWORD) \
		--dry-run=client -o yaml | kubectl apply -f -

k8s-db-secret:
	@test -n "$(DATABASE_URL)" || { echo "ERROR: chưa đặt DATABASE_URL"; exit 1; }
	kubectl apply -f k8s/namespace.yaml
	kubectl -n $(NAMESPACE) create secret generic guardian-db \
		--from-literal=DATABASE_URL="$(DATABASE_URL)" \
		--dry-run=client -o yaml | kubectl apply -f -
	@echo "Đã tạo secret 'guardian-db'."

k8s-apply:
	kubectl apply -f k8s/namespace.yaml
	$(MAKE) k8s-secret
	$(MAKE) k8s-db-secret
	kubectl apply -f k8s/
