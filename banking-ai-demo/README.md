# banking-ai-demo

Monorepo demo dùng để test pipeline **CI/CD lên Kubernetes / VKS (VNG Cloud)**, image đẩy lên VNG Container Registry (vCR).

> Đây là scaffold cơ bản để kiểm thử CI/CD trước. **Không có** database, auth, hay tích hợp LLM ở phase này.
> Tất cả dữ liệu là mock in-memory và reset khi container restart.

## Services

Mỗi service là một ứng dụng FastAPI độc lập, chạy port **8080** trong container.

| Service | Mục đích | API demo chính |
|---|---|---|
| `customer-profile-service` | Customer profile: persona, behavior baseline, beneficiaries, digital twin | `GET /customers/{id}`, `GET /customers/{id}/baseline` |
| `transaction-service` | Lịch sử giao dịch: categorize, monthly summary, cashflow forecast | `GET /transactions/{id}`, `.../monthly-summary`, `.../cashflow-forecast` |
| `risk-scoring-service` | Risk score deterministic 0-100 từ ~6 factor | `POST /risk-score` |
| `scam-knowledge-service` | Lookup + match ~10 kịch bản scam phổ biến tại VN | `GET /scams`, `POST /scams/match` |
| `action-feedback-service` | Ghi nhận action (CANCEL/HOLD/CONTACT/CASE_OPEN/ALERT) và feedback | `POST /actions`, `GET /actions/{id}`, `POST /feedback` |

Mỗi service đều có: `GET /health` → `{"status":"ok","service":"<name>"}` và `GET /info` (mô tả service).

## Sơ đồ luồng

```
customer-profile ──▶ transaction ──▶ risk-scoring ──▶ scam-knowledge ──▶ action-feedback
   (profile)         (lịch sử GD)     (tính điểm)      (match kịch bản)     (hành động + feedback)
```

Luồng ý tưởng: lấy profile khách hàng → xem giao dịch → chấm điểm rủi ro → đối chiếu kịch bản scam → quyết định hành động & ghi nhận feedback.

## Cấu trúc repo

`.github/workflows/` nằm ở **gốc git repo** (cấp trên `banking-ai-demo/`) để GitHub Actions đọc được; path filter trỏ vào `banking-ai-demo/services/<name>/**`.

```
<repo-root>/
  .github/workflows/            (1 workflow build image / service)
  banking-ai-demo/
    services/
      customer-profile-service/   (main.py, requirements.txt, Dockerfile, tests/)
      transaction-service/
      risk-scoring-service/
      scam-knowledge-service/
      action-feedback-service/
    k8s/
      namespace.yaml
      customer-profile.yaml
      transaction.yaml
      risk-scoring.yaml
      scam-knowledge.yaml
      action-feedback.yaml
    Makefile
    README.md
```

## Chạy từng service local

Cần Python 3.11+.

```bash
cd services/customer-profile-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
# → http://localhost:8080/health
# → http://localhost:8080/docs  (Swagger UI)
```

Hoặc dùng Makefile (chạy 1 service, mặc định customer-profile-service):

```bash
make run                                  # customer-profile-service @ 8080
make run SERVICE=risk-scoring-service      # service khác
make run SERVICE=transaction-service PORT=8082
```

Ví dụ gọi thử:

```bash
curl localhost:8080/customers/C001
curl -X POST localhost:8080/risk-score \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"C001","amount":50000000,"new_beneficiary":true,"unusual_time":true,"geo_anomaly":true}'
```

## Test

```bash
make test          # chạy pytest cho tất cả service
```

Hoặc từng service:

```bash
cd services/risk-scoring-service
pip install -r requirements.txt
python -m pytest -q
```

## Build Docker

```bash
# Build tất cả, tag = short commit SHA
make build

# Build 1 service thủ công
docker build -t customer-profile-service:dev services/customer-profile-service
docker run -p 8080:8080 customer-profile-service:dev
```

Image được build với registry mặc định `vcr.vngcloud.vn/114544-ea-hackathon` (VNG Container Registry) — override khi cần:

```bash
make build REGISTRY=vcr.vngcloud.vn/<your-project> TAG=$(git rev-parse --short HEAD)
```

## Deploy lên Kubernetes / VKS

vCR là **private registry**, nên VKS cần một `imagePullSecret` (tên `vcr-cred`) để kéo image. Tất cả Deployment đã tham chiếu sẵn secret này.

```bash
# 1. Nạp credential vCR qua biến môi trường (KHÔNG commit vào repo)
export VCR_USERNAME='<vcr-username>'
export VCR_PASSWORD='<vcr-password>'

# 2. Tạo namespace + imagePullSecret + apply toàn bộ manifest
make k8s-apply
#   k8s-apply sẽ: tạo namespace → tạo secret 'vcr-cred' (make k8s-secret) → kubectl apply -f k8s/

# 3. Kiểm tra
kubectl -n finance-demo get pods,svc

# 4. Thử 1 service qua port-forward
kubectl -n finance-demo port-forward svc/customer-profile-service 8080:80
curl localhost:8080/health
```

Tạo/rotate riêng imagePullSecret (không apply manifest):

```bash
make k8s-secret VCR_USERNAME='<vcr-username>' VCR_PASSWORD='<vcr-password>'
```

Mỗi manifest gồm: `Deployment` (có `imagePullSecrets: vcr-cred`) + `Service` (ClusterIP), `readinessProbe` và `livenessProbe` trỏ tới `/health`, requests/limits CPU/RAM nhỏ cho demo. Namespace chung: **`finance-demo`**.

### Cập nhật image tag (commit SHA)

Manifest để `image: ...:latest`. Trong CI (sau khi push image), cập nhật deployment sang đúng commit SHA — ví dụ:

```bash
kubectl -n finance-demo set image \
  deployment/customer-profile-service \
  customer-profile-service=vcr.vngcloud.vn/114544-ea-hackathon/customer-profile-service:$GITHUB_SHA
```

## CI/CD (GitHub Actions → VNG Container Registry / vCR)

Mỗi service có 1 workflow trong `<repo-root>/.github/workflows/<service>.yml`, chỉ chạy khi folder service đó thay đổi — path filter là `banking-ai-demo/services/<name>/**`. Workflow sẽ:

1. Đăng nhập vCR tại host `vcr.vngcloud.vn`.
2. Build Docker image.
3. Push vào project `114544-ea-hackathon` với **2 tag**: `:<commit SHA>` (chính) và `:latest`.

Host (`vcr.vngcloud.vn`) và project (`114544-ea-hackathon`) để thẳng trong workflow/manifest (không phải secret). Chỉ **credentials** đưa vào GitHub Secrets (Settings → Secrets and variables → Actions):

| Secret | Ý nghĩa |
|---|---|
| `VCR_USERNAME` | Username / access key đăng nhập vCR |
| `VCR_PASSWORD` | Password / secret key vCR |

Image path đầy đủ: `vcr.vngcloud.vn/114544-ea-hackathon/<service>:<commit SHA>`.

> **Lưu ý vị trí `.github`:** GitHub Actions chỉ đọc `.github/workflows` ở **gốc git repo**. Repo này đã đặt `.github/` ở gốc repo (`msb-finance-platform/.github/`), path filter là `banking-ai-demo/services/<name>/**` và build context là `banking-ai-demo/services/<name>`. Nếu sau này tách `banking-ai-demo/` thành repo riêng, đổi lại path filter thành `services/<name>/**` và context `services/<name>`.

## Không thuộc phase này

- ❌ Database (dữ liệu mock in-memory)
- ❌ Authentication / Authorization
- ❌ Tích hợp LLM

Mục tiêu hiện tại: scaffold đơn giản để test CI/CD build → push → deploy VKS trước.
