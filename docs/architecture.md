# Receipt Scanner – Architecture Document

## 1. System Overview

Receipt Scanner is a self-hosted web application that:

1. **Ingests** receipt files (PDF, image, plain-text) via a web upload form, a watched local folder, or future email/drive integrations.
2. **Parses** the raw text into a canonical structured format (merchant, date, line items, totals).
3. **Categorizes** each line item using a priority-ordered rule engine and an optional TF-IDF machine-learning classifier.
4. **Matches** each receipt to a transaction in the user's [YNAB](https://ynab.com) budget using a multi-signal scoring algorithm.
5. **Proposes** and applies YNAB split transactions broken down by line item and taxonomy category.
6. Provides a **web UI** (Jinja2 + Bootstrap 5) and a **JSON API** (FastAPI) for browsing, editing, and analyzing receipts.

---

## 2. Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                          User / Browser                              │
│             (Jinja2 HTML UI  +  fetch() JSON calls)                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                            │
│  /upload  /inbox  /receipts  /ynab  /rules  /analytics  /ui/*         │
│                                                                        │
│   Routers ──► Services ──► Parsing Pipeline                           │
│                   │                                                    │
│                   ├── StorageService (MinIO/S3)                        │
│                   ├── YnabClient (httpx → api.ynab.com)               │
│                   ├── MatchingService (scoring algorithm)              │
│                   ├── RulesEngine (contains / regex / merchant_dept)   │
│                   ├── TaxonomyClassifier (TF-IDF + LinearSVC)         │
│                   └── CryptoService (Fernet encryption)               │
│                                                                        │
│   SQLAlchemy ORM ──► PostgreSQL 16                                    │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
              ┌─────────────────┴──────────────────┐
              │                                    │
              ▼                                    ▼
  ┌──────────────────────┐           ┌─────────────────────────┐
  │   Celery Worker       │           │     MinIO Object Store   │
  │                       │           │  (receipts bucket)       │
  │  • poll_watched_folder│           │                          │
  │  • retrain_classifier │           └─────────────────────────┘
  └──────────┬────────────┘
             │
             ▼
  ┌──────────────────────┐
  │   Redis (Broker +    │
  │   Result Backend)    │
  └──────────────────────┘
```

---

## 3. Data Model

### Core tables

| Table | Purpose |
|---|---|
| `receipts` | One row per receipt; stores merchant, totals, parse metadata |
| `line_items` | One row per purchased item; FK to receipt |
| `artifacts` | Raw file URI + extracted text; FK to receipt |

### YNAB integration tables

| Table | Purpose |
|---|---|
| `ynab_tokens` | Encrypted OAuth access/refresh tokens |
| `ynab_links` | Confirmed receipt ↔ YNAB transaction link |
| `ynab_split_proposals` | Generated and applied split proposals |

### Rules & ML tables

| Table | Purpose |
|---|---|
| `taxonomy_categories` | Hierarchical category tree (mirrors YNAB categories) |
| `category_rules` | Deterministic rules: contains / regex / merchant+dept |
| `learning_examples` | Human-confirmed categorizations used to train the ML model |

### Audit & settings

| Table | Purpose |
|---|---|
| `audit_logs` | Immutable log of every write action (match, split apply, …) |
| `user_settings` | Per-user preferences (default budget, timezone, …) |

### Key relationships

```
Receipt 1──* LineItem
Receipt 1──* Artifact
Receipt 1──* YnabLink
Receipt 1──* YnabSplitProposal
LineItem *──1 TaxonomyCategory (nullable)
TaxonomyCategory 1──* CategoryRule
TaxonomyCategory 1──* LearningExample
TaxonomyCategory 1──0..1 TaxonomyCategory (parent)
```

---

## 4. Ingestion Flows

### 4a. Web Upload

```
Browser  POST /upload (multipart)
  → FastAPI router reads bytes
  → If PDF: pdfplumber extracts text
  → parse_receipt_text(text) → CanonicalReceipt
  → StorageService.upload_file() → MinIO
  → INSERT receipt, line_items, artifact (SQLAlchemy)
  → Return {receipt_id, merchant}
```

### 4b. Watched Folder (Celery beat)

```
Celery beat every N seconds
  → poll_watched_folder task
  → Scan WATCHED_FOLDER_PATH for *.txt / *.pdf
  → For each file: extract text, parse, store to DB + MinIO
  → Rename file to *.done to prevent re-processing
```

### 4c. Future: Gmail / Google Drive

Reserved `source_type` enum values (`gmail`, `drive`) are defined in the `Receipt` model; integration routers can be added as new modules under `app/routers/`.

---

## 5. Parsing Pipeline

```
parse_receipt_text(text, source_type)
  │
  ├── CostcoParser.can_parse(text)?  → yes → CostcoParser.parse()
  ├── WalmartParser.can_parse(text)? → yes → WalmartParser.parse()
  ├── AldiParser.can_parse(text)?    → yes → AldiParser.parse()
  └── FallbackParser.parse()  (always accepted)
```

Each parser returns a `CanonicalReceipt` dataclass containing:
- `merchant`, `source_type`, `purchase_datetime`
- `subtotal`, `tax`, `total`, `currency`
- `payment_method_last4`, `parse_confidence`, `parse_notes`
- `line_items: list[CanonicalLineItem]`

`CanonicalLineItem` fields: `description_raw`, `description_normalized`, `sku`, `quantity`, `unit_price`, `total_price`, `discounts`, `tax_flag`, `department_hint`.

### Adding a new parser

1. Create `app/parsing/<merchant>.py` subclassing `BaseParser`.
2. Implement `can_parse(text)` and `parse(text, source_type)`.
3. Register the instance in `app/parsing/pipeline.py`'s `_PARSERS` list.

---

## 6. Categorization

### 6a. Rule Engine (deterministic, high confidence)

Rules are evaluated in descending priority order. The first matching rule wins.

| Rule type | Match logic |
|---|---|
| `contains` | `pattern` (lowercased) is a substring of the normalized description |
| `regex` | `re.search(pattern, description, IGNORECASE)` |
| `merchant_dept` | Combines `merchant_filter` and `department_filter` fields |

### 6b. ML Classifier (fallback / suggestion)

- Algorithm: scikit-learn `TfidfVectorizer(ngram_range=(1,2))` → `LinearSVC`
- Input feature: `f"{merchant} {description_normalized}"`
- Labels: `str(taxonomy_category_id)`
- Trained nightly via the `retrain_classifier` Celery task on all `LearningExample` rows
- Model persisted to `MODEL_DIR/taxonomy_classifier.pkl`
- A minimum of 2 distinct classes (categories) is required to train

---

## 7. YNAB Integration

### 7a. OAuth Flow

```
User → GET /ynab/connect
  → Redirect to https://app.ynab.com/oauth/authorize
  ← Redirect to GET /ynab/callback?code=…&state=…
  → Exchange code for tokens (POST /oauth/token)
  → Encrypt tokens with Fernet (ENCRYPTION_KEY)
  → Store in ynab_tokens table
```

### 7b. Matching Algorithm

Candidate transactions are scored using a weighted sum:

| Signal | Weight | Formula |
|---|---|---|
| Merchant name similarity | 35% | Jaccard on word sets |
| Date proximity | 30% | 1 / (1 + days_apart) |
| Amount match | 30% | Tiered: exact=1.0, ≤0.5%=0.9, ≤1%=0.75, ≤5%=0.4, ≤10%=0.2 |
| Card last-4 in memo | 5% | 0.5 if found, else 0.0 |

Top 5 candidates are returned ordered by score descending.

### 7c. Split Proposal

1. User views `/ui/ynab/split/{receipt_id}/confirm?txn=<ynab_id>`
2. Server generates a `YnabSplitProposal` from the receipt's line items
3. Each line item becomes a YNAB sub-transaction with:
   - `amount`: line item total (negative milliunits = outflow)
   - `memo`: normalized description
   - `category_id`: YNAB category ID from taxonomy (if mapped)
4. User reviews and edits in the browser
5. POST `/ynab/split/{receipt_id}/confirm` → `PUT /budgets/{id}/transactions/{id}` on YNAB API
6. An `AuditLog` row is written before the YNAB write

### 7d. Safety Considerations

- **Encrypted tokens**: YNAB OAuth tokens are encrypted at rest using `cryptography.Fernet` (AES-128-CBC + HMAC-SHA256). The `ENCRYPTION_KEY` must be a valid Fernet key stored outside source control.
- **Audit log**: Every YNAB write (match confirmation, split apply) is recorded in `audit_logs` with before/after JSON.
- **No auto-apply**: Splits are only applied after explicit user confirmation via the UI.
- **State parameter**: The OAuth `state` parameter is validated to prevent CSRF.

---

## 8. Security Considerations

| Area | Approach |
|---|---|
| YNAB token storage | Fernet encryption (AES + HMAC); key from environment variable |
| Secret key | `SECRET_KEY` env var for session signing (itsdangerous) |
| SQL injection | SQLAlchemy ORM with parameterized queries throughout |
| File upload | Files stored directly to MinIO; text extracted in-process; no shell execution |
| Presigned URLs | MinIO presigned URLs expire after 1 hour by default |
| YNAB OAuth CSRF | `state` nonce generated per request, validated on callback |
| Audit trail | Every destructive / write action logged with user_id and timestamps |
| Dependency supply chain | `pyproject.toml` pins minimum versions; advisories checked via GitHub dependabot |

---

## 9. Configuration Reference

All configuration is via environment variables (`.env` file or system environment). See `.env.example` for the full list.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask/FastAPI session signing key (min 32 chars) |
| `ENCRYPTION_KEY` | Fernet key for YNAB token encryption (base64url 32-byte) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string (broker + result backend) |
| `MINIO_*` | MinIO/S3 endpoint, credentials, bucket |
| `YNAB_CLIENT_ID/SECRET` | YNAB OAuth application credentials |
| `YNAB_REDIRECT_URI` | Must match YNAB app configuration |
| `WATCHED_FOLDER_PATH` | Host path polled by Celery worker |
| `WATCHED_FOLDER_POLL_SECONDS` | Poll interval (default 30) |
| `MODEL_DIR` | Where the ML classifier pickle is saved |
| `DEBUG` | Set to `true` in development (auto-creates DB tables) |

---

## 10. Development Quick-Start

```bash
# 1. Copy env file
cp .env.example .env
# Edit .env – set SECRET_KEY and ENCRYPTION_KEY at minimum

# 2. Start infrastructure
docker compose up db redis minio -d

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Run migrations
alembic upgrade head

# 5. Start the API
uvicorn app.main:app --reload

# 6. (Optional) Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info --beat

# 7. Run tests
pytest
```

Drop receipt text files into the watched folder (`/data/watched` by default) to test end-to-end parsing without a browser.
