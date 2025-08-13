## AllerGuard Pro - Food Allergy Scanner API 🍽️🔎

A  FastAPI application that lets users scan food products by barcode and instantly assess allergen risk against their personal allergen profile. It caches product data from Open Food Facts, detects allergens from ingredients, and provides risk levels with clear, user-friendly messages.

### Key Features
- **JWT authentication** with secure password hashing
- **Scan via barcode or image** (base64/multipart) with `pyzbar` + `Pillow`
- **Allergen detection** using keyword matching, “may contain” heuristics, and fuzzy matching with confidence scores
- **Open Food Facts API caching** (SQLite-backed, 7-day TTL) with cache hit/miss logging
- **Scan history** per user with risk levels
- **Open Food Facts integration** via async `httpx`
- **CORS enabled**, structured logging with per-request IDs, robust error handling
- **Dockerized** with healthcheck and volume-mounted SQLite DB

### Problem It Solves
People with food allergies need a fast way to verify product safety. This API enables quick barcode-based checks, tailored to each user’s allergens, reducing the risk of accidental exposure.


## Tech Stack
- **FastAPI**: High-performance async Python web framework with built-in OpenAPI docs.
- **Uvicorn**: Lightning-fast ASGI server.
- **SQLAlchemy 2.0 (async)** + **aiosqlite**: Robust ORM with async SQLite driver.
- **python-jose[cryptography]**: Secure JWT encoding/decoding.
- **passlib[bcrypt]**: Trusted password hashing.
- **httpx**: Async HTTP client for Open Food Facts API.
- **pyzbar**: Barcode decoding (requires system `zbar`).
- **Pillow**: Image handling for barcode scans.
- **python-multipart**: Multipart/form-data file uploads.
- **python-dotenv**: Load environment variables from `.env`.
 - **Alpine/SQLite caching**: TTL cache for external API responses stored in SQLite.


## Quick Start
### Prerequisites
- Python 3.11+
- System dependency for barcode decoding: `zbar`
  - macOS: `brew install zbar`
  - Debian/Ubuntu: `sudo apt-get update && sudo apt-get install -y libzbar0`

### Local Installation
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
uvicorn app:app --reload
```
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Run with Docker
```bash
docker compose up --build
```
- Healthcheck: `GET /health`
- SQLite DB persists in named volume `db_data` (mapped to `/app/allergen_scanner.db`).

## Web UI (index.html)
The project has a simple, beautiful single-page UI for testing the API.

### How to use
- Start the API (local or Docker)
- Open `index.html` directly in your browser (double-click or drag-and-drop into the browser)
  - The UI calls the API at `http://localhost:8000` by default. To use a different API base, edit the `BASE_URL` constant near the top of the inline script in `index.html`.

### What it includes
- Registration and Login forms
- JWT token stored in `localStorage` and sent as `Authorization: Bearer <token>`
- Profile panel showing email and allergen list
- Scan via:
  - Manual barcode entry (with quick-test buttons like Nutella, Coca-Cola, Barilla Pasta, Ferrero)
  - Image upload with drag-and-drop
  - Mobile camera capture (`capture="environment"`)
- Loading animations and toast notifications
- Color-coded risk levels: green=safe, yellow=warning, red=danger
- Scan results (product name/brand, matched allergens, message, ingredients, image)
- Recent scan history viewer with risk badges

## Live Deployment (Render)
Deployed using Render.com with a Dockerized API and a Static Site for the UI.

- API Swagger UI: [allerguard-pro.onrender.com/docs][api-docs]
- API Health: [allerguard-pro.onrender.com/health][api-health]
- UI Demo: [allerguard-pro-ui.onrender.com][ui-demo]

What these links are:
- [API Swagger UI][api-docs]: Interactive OpenAPI docs for trying endpoints. Use Authorize to paste the Bearer token after login.
- [API Health][api-health]: JSON healthcheck used by platform health checks, returns status and timestamp.
- [UI Demo][ui-demo]: Single-page Tailwind/Alpine client to register/login, scan by barcode or image (drag & drop/camera), and view results/history.

Hosting details:
- API: Render Web Service built from Dockerfile (installs libzbar0). Persistent disk mounted (e.g., /data) for SQLite DB.
- UI: Render Static Site serving `index.html` (no build). The UI’s BASE_URL points to the API URL.


## API Documentation
- Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Authentication Flow
1. `POST /register` with `email`, `password`, `allergens` → returns access token.
2. `POST /login` with `email`, `password` → returns access token.
3. Use `Authorization: Bearer <token>` header for protected endpoints.

### Example cURL Calls
```bash
# Register
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123","allergens":["nuts","dairy"]}'

# Login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123"}'

# Profile (replace TOKEN)
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/profile

# Scan by barcode
curl -X POST http://localhost:8000/scan \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"barcode":"3017620422003"}'

# Product (public)
curl http://localhost:8000/product/3017620422003

# Test image upload via multipart (public)
curl -X POST http://localhost:8000/scan/test-image \
  -F file=@/path/to/barcode_image.jpg
```


## Features
- [x] JWT auth (HS256) with 24h expiry
- [x] Register, login, profile
- [x] Scan via barcode or base64 image
- [x] Multipart test endpoint for images (`/scan/test-image`)
- [x] Open Food Facts integration with async caching (SQLite-backed, 7 days)
- [x] Allergen detection with keyword matching, “may contain”, fuzzy matching + confidence
- [x] Scan history (last 20 scans)
- [x] CORS for testing
- [x] Structured logging with request IDs
- [x] Per-user rate limiting on `/scan` (10 req/min)
- [x] Docker support with healthcheck

### Planned
- [ ] User-managed allergen presets and synonyms
- [ ] Admin dashboard and analytics
- [ ] Postgres deployment and migrations
- [ ] Advanced NLP allergen detection
- [ ] Rate limiting and API keys


## API Endpoints

| Method | Path                 | Auth | Description |
|-------:|----------------------|:----:|-------------|
| POST   | `/register`          |  ⛔  | Create user and return JWT token |
| POST   | `/login`             |  ⛔  | Login and return JWT token |
| GET    | `/profile`           |  ✅  | Current user profile |
| POST   | `/scan`              |  ✅  | Scan product by `barcode` or `image` (base64) with per-user rate limiting |
| POST   | `/scan/test-image`   |  ⛔  | Upload image (multipart) and detect barcode |
| POST   | `/scan/bulk`         |  ✅  | Bulk scan multiple barcodes |
| GET    | `/scan-history`      |  ✅  | Last 20 scans with details |
| GET    | `/product/{barcode}` |  ⛔  | Get product info (cached/offline-first) |
| GET    | `/stats`             |  ⛔  | Usage statistics (cacheable by clients) |
| GET    | `/health`            |  ⛔  | Healthcheck |

Legend: ✅ requires Bearer token, ⛔ public


## Testing
### Run the test script
```bash
python test_api.py --base-url http://127.0.0.1:8000
```
Outputs colored PASS/FAIL with full response bodies.

### Sample Credentials
- Email: `test@example.com`
- Password: `test123`

### Test Barcodes
- Nutella: `3017620422003`
- Coca-Cola: `5449000214799`
- Barilla pasta: `8076809513388`
- Ferrero Rocher: `3017620425035`


## Project Structure
```
allergy_scanner/
├─ app.py                 # Uvicorn entrypoint shim (imports app from package)
├─ requirements.txt       # Python dependencies
├─ Dockerfile             # Container build file (includes libzbar0)
├─ docker-compose.yml     # Compose for local dev/runtime + healthcheck
├─ .dockerignore          # Exclude junk from Docker build context
├─ README.md              # This documentation
├─ test_api.py            # Endpoint integration tester (httpx)
├─ allergy_app/           # Application package
│  ├─ main.py             # FastAPI app, routes, schemas, startup
│  ├─ core/
│  │  ├─ config.py        # Environment-driven configuration
│  │  └─ logging.py       # Logging configuration and request ID filter
│  ├─ db/
│  │  ├─ tables.py        # SQLAlchemy models
│  │  └─ session.py       # Engine, session maker, dependency
│  ├─ security/
│  │  └─ auth.py          # JWT, hashing, current user dependency
│  ├─ services/
│  │  └─ off_client.py    # Open Food Facts client with SQLite TTL cache
│  └─ utils/
│     └─ allergens.py     # Allergen detection and risk computation
└─ allergen_scanner.db    # SQLite DB (created at runtime)
```


## Allergen Detection
### Supported Allergen Categories
- nuts, dairy, gluten, eggs, soy, shellfish, fish, sesame, sulfites, mustard

### How Detection Works
- Ingredients text is normalized (lowercased, whitespace condensed).
- Case-insensitive keyword search with word boundaries (e.g., `milk`, `whey`).
- Detects “may contain …” within a configurable window.
- Risk levels:
  - **danger**: direct match of user allergens
  - **warning**: only “may contain” matched
  - **safe**: no matches


## Deployment
### Docker
```bash
docker compose up --build -d
```

### Environment Variables
- `SECRET_KEY`: JWT signing key (change in production)
- `DATABASE_URL`: SQLAlchemy URL (default `sqlite+aiosqlite:///allergen_scanner.db`)
- `ACCESS_TOKEN_EXPIRE_HOURS`: Token TTL (default 24)
- `JWT_ALGORITHM`: Signing algorithm (default `HS256`)
- `OFF_API_BASE`: Open Food Facts API base (default `https://world.openfoodfacts.org/api/v0`)
- `CORS_ALLOW_ORIGINS`: CORS origins (default `*` for testing)

### Production Considerations
- Use a strong `SECRET_KEY` and store secrets securely.
- Prefer Postgres for concurrency and durability.
- Run behind a reverse proxy (TLS termination, rate limiting, gzip).
- Increase workers (e.g., `gunicorn -k uvicorn.workers.UvicornWorker -w 4`).
- Monitor health, logs, and add observability.
- Ensure `zbar` is installed in the deployment environment.


## Sample Requests
### Registration
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"new@example.com","password":"pass123","allergens":["nuts","dairy","gluten"]}'
```

### Login
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"new@example.com","password":"pass123"}'
```

### Scan (example response)
```bash
curl -X POST http://localhost:8000/scan \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"barcode":"3017620422003"}'
```

```json
{
  "product_name": "Nutella",
  "brand": "Ferrero",
  "risk_level": "danger",
  "matched_allergens": ["nuts", "dairy"],
  "user_allergens": ["nuts", "dairy", "gluten"],
  "ingredients": "Sugar, palm oil, hazelnuts, milk...",
  "image_url": "...",
  "message": "WARNING: Contains nuts, dairy"
}
```

[api-docs]: https://allerguard-pro.onrender.com/docs#
[api-health]: https://allerguard-pro.onrender.com/health
[ui-demo]: https://allerguard-pro-ui.onrender.com/
