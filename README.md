# DataSift API

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/datasift/api)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Enterprise-grade data intelligence platform with automated machine learning analysis.**

DataSift transforms raw CSV data into actionable insights using advanced ML algorithms including outlier detection, clustering, and intelligent recommendations.

## Features

- **Automated ML Analysis** — Isolation Forest for outlier detection, K-Means clustering
- **Enterprise Security** — JWT authentication, API key management, Row-Level Security
- **Scalable Infrastructure** — Built on Supabase PostgreSQL with connection pooling
- **Flexible Billing** — PayPal integration with monthly/yearly plans
- **RESTful API** — OpenAPI documentation, SDK-ready endpoints
- **Real-time Processing** — Sub-second analysis for datasets up to 500MB

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or Supabase account)
- PayPal Developer account (for payments)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/datasift.git
cd datasift

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the application
uvicorn app.main:app --reload
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build manually
docker build -t datasift-api .
docker run -p 8000:8000 --env-file .env datasift-api
```

## API Documentation

Once running, access the interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Authentication

```bash
# Register
curl -X POST "http://localhost:8000/auth/register" \
  -d "email=user@example.com" \
  -d "password=SecurePass123"

# Login
curl -X POST "http://localhost:8000/auth/login" \
  -d "email=user@example.com" \
  -d "password=SecurePass123"

# Use API Key for requests
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "X-API-Key: ds_your_api_key_here" \
  -F "file=@dataset.csv"
```

### Analyze Dataset

```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@sales_data.csv" \
  -F "analysis_type=full"
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "dataset_name": "sales_data.csv",
  "dataset_hash": "a1b2c3d4...",
  "summary": {
    "overall": {
      "rows": 10000,
      "columns": 15,
      "missing_cells": 234
    },
    "numeric_stats": { ... }
  },
  "patterns": [
    {
      "type": "outliers",
      "description": "Detected 127 outliers",
      "confidence": 0.85
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "category": "data_quality",
      "message": "Column 'revenue' has 12% missing values",
      "action": "Consider imputation strategies"
    }
  ],
  "processing_time_ms": 145,
  "requests_remaining": 999,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Architecture

```
DataSift/
├── app/
│   ├── main.py           # FastAPI application
│   ├── auth.py           # JWT & API key authentication
│   ├── payments.py       # PayPal integration
│   ├── database.py       # SQLAlchemy configuration
│   ├── models.py         # Database models
│   └── ml/
│       ├── analyzer.py       # API endpoints
│       └── enhanced_analyzer.py  # ML algorithms
├── supabase.sql          # Database schema
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Database Schema

The application uses Supabase PostgreSQL with the following tables:

- `users` — User accounts with subscription info
- `plans` — Subscription plan configurations
- `payments` — PayPal payment transactions
- `analysis_reports` — ML analysis results
- `api_key_logs` — API key audit trail
- `usage_logs` — API usage tracking

Run `supabase.sql` in your Supabase SQL Editor to initialize the schema.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT signing key (min 64 chars) | Yes |
| `PAYPAL_CLIENT_ID` | PayPal API client ID | For payments |
| `PAYPAL_CLIENT_SECRET` | PayPal API secret | For payments |
| `PAYPAL_MODE` | `sandbox` or `live` | No (default: sandbox) |

See `.env` for complete configuration options.

## Pricing Plans

| Plan | Price | Requests | File Size | Features |
|------|-------|----------|-----------|----------|
| Starter | Free | 1,000/mo | 10 MB | Basic analysis |
| Professional | $29.99/mo | 10,000/mo | 100 MB | Advanced ML, priority support |
| Enterprise | $199.99/mo | 100,000/mo | 500 MB | Dedicated infra, SSO, 24/7 support |

## Security

- **Password hashing**: bcrypt with 12 rounds
- **JWT tokens**: HS256 algorithm, 30-minute expiry
- **API keys**: 64-character cryptographically secure tokens
- **Database**: SSL-required connections, Row-Level Security
- **Headers**: Security headers (HSTS, CSP, X-Frame-Options)

## Monitoring

Health check endpoint:

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "service": "DataSift API",
  "version": "2.0.0",
  "timestamp": 1705315800
}
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Support

- Documentation: https://docs.datasift.io
- Email: support@datasift.io
- Enterprise: enterprise@datasift.io
