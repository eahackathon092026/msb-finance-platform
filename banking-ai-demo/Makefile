# Makefile cho banking-ai-demo monorepo
# Yêu cầu: python3, docker, kubectl

SERVICES := customer-profile-service transaction-service risk-scoring-service scam-knowledge-service action-feedback-service

# Registry đích (override khi build/push): make build REGISTRY=vcr.vngcloud.vn/114544-ea-hackathon
REGISTRY ?= vcr.vngcloud.vn/114544-ea-hackathon
# Tag mặc định = short commit SHA
TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)

# Service chạy local (dùng cho `make run`)
SERVICE ?= customer-profile-service
PORT ?= 8080

# vCR registry host + imagePullSecret (credentials lấy từ biến môi trường, KHÔNG hardcode)
REGISTRY_HOST ?= vcr.vngcloud.vn
NAMESPACE ?= finance-demo
PULL_SECRET ?= vcr-cred

.PHONY: help test build run k8s-apply k8s-secret

help:
	@echo "make test        - chạy pytest cho tất cả service"
	@echo "make build        - docker build tất cả service, tag = $(TAG)"
	@echo "make run          - chạy 1 service local (SERVICE=<name> PORT=<port>)"
	@echo "make k8s-secret   - tạo imagePullSecret '$(PULL_SECRET)' (cần VCR_USERNAME, VCR_PASSWORD)"
	@echo "make k8s-apply    - kubectl apply namespace + toàn bộ manifest"

test:
	@for svc in $(SERVICES); do \
		echo "==> test $$svc"; \
		( cd services/$$svc && pip install -q -r requirements.txt && python -m pytest -q ) || exit 1; \
	done

build:
	@for svc in $(SERVICES); do \
		echo "==> build $(REGISTRY)/$$svc:$(TAG)"; \
		docker build -t $(REGISTRY)/$$svc:$(TAG) -t $(REGISTRY)/$$svc:latest services/$$svc || exit 1; \
	done

run:
	@echo "==> run $(SERVICE) tại http://localhost:$(PORT) (Ctrl+C để dừng)"
	cd services/$(SERVICE) && pip install -q -r requirements.txt && \
		uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

k8s-secret:
	@test -n "$(VCR_USERNAME)" || { echo "ERROR: set VCR_USERNAME"; exit 1; }
	@test -n "$(VCR_PASSWORD)" || { echo "ERROR: set VCR_PASSWORD"; exit 1; }
	kubectl apply -f k8s/namespace.yaml
	kubectl -n $(NAMESPACE) create secret docker-registry $(PULL_SECRET) \
		--docker-server=$(REGISTRY_HOST) \
		--docker-username=$(VCR_USERNAME) \
		--docker-password=$(VCR_PASSWORD) \
		--dry-run=client -o yaml | kubectl apply -f -

k8s-apply:
	kubectl apply -f k8s/namespace.yaml
	$(MAKE) k8s-secret
	kubectl apply -f k8s/
