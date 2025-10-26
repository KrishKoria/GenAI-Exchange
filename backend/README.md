# ClauseCompass Backend API

AI-powered legal document analysis and risk assessment backend service built with FastAPI, Poetry, and Google Cloud Platform.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Poetry 1.7+
- Google Cloud Platform account with enabled APIs
- GCP Service Account with appropriate permissions

### Installation

1. **Clone and navigate to backend directory**

```bash
cd backend
```

2. **Install dependencies with Poetry**

```bash
poetry install
```

3. **Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your GCP credentials and configuration
```

4. **Activate virtual environment**

```bash
poetry shell
```

5. **Run the development server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Documentation

- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`
- **Health Check**: `http://localhost:8000/health`

## 🏗️ Architecture

### Core Components

- **FastAPI**: Modern async web framework
- **Uvicorn**: ASGI server for production deployment
- **Poetry**: Dependency management and packaging
- **Pydantic**: Data validation and settings management
- **Google Cloud SDKs**: Integration with GCP services

### GCP Services Integration

- **Document AI**: PDF/DOCX text extraction and layout analysis
- **Vertex AI**: Gemini models for summarization and Q&A
- **Firestore**: Document and clause metadata storage
- **Cloud Storage**: Optional file storage
- **DLP API**: PII detection and masking
- **Pub/Sub**: Event streaming for analytics
- **BigQuery**: Analytics and metrics storage

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/        # API endpoint handlers
│   ├── core/                     # Core configuration and utilities
│   ├── models/                   # Pydantic data models
│   ├── services/                 # Business logic services (TBD)
│   └── main.py                   # FastAPI application entry point
├── pyproject.toml               # Poetry configuration
├── Dockerfile                   # Multi-stage Docker build
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## 🔌 API Endpoints

### Document Processing

- `POST /api/v1/documents/ingest` - Upload and process legal documents
- `GET /api/v1/documents/status/{doc_id}` - Get processing status
- `GET /api/v1/documents/clauses?doc_id={id}` - Get clause summaries
- `GET /api/v1/documents/clause/{clause_id}?doc_id={id}` - Get clause details

### Question & Answer

- `POST /api/v1/qa/ask` - Ask questions about document clauses
- `GET /api/v1/qa/history/{doc_id}` - Get Q&A history

### Metrics & Analytics

- `GET /api/v1/metrics/summary` - Aggregated metrics dashboard
- `GET /api/v1/metrics/processing-stats` - Processing performance stats
- `GET /api/v1/metrics/risk-patterns` - Risk pattern analysis

### Health & Status

- `GET /health` - Basic health check
- `GET /api/v1/health/ready` - Readiness probe for deployment

## ⚙️ Configuration

### Required Environment Variables

```bash
# GCP Configuration
PROJECT_ID=your-gcp-project-id
DOC_AI_PROCESSOR_ID=your-processor-id
SECRET_KEY=your-secret-key

# Optional (with defaults)
GEMINI_MODEL_NAME=gemini-1.5-flash
MAX_FILE_SIZE_MB=10
MAX_PAGES=30

# AI Features
GEMINI_GROUNDING_ENABLED=true  # Enable Google Search grounding for up-to-date information
```

**Gemini Grounding**: When enabled, the AI model can search the internet to provide more accurate, up-to-date responses. This is particularly useful for questions about recent events, current regulations, or evolving legal standards. Disable this if you want purely document-based analysis without external information.

### GCP Service Account Permissions

Your service account needs the following roles:

- Document AI User
- Vertex AI User
- Firestore User
- Pub/Sub Publisher
- BigQuery Data Editor
- DLP User

## 🐳 Docker Deployment

### Build the container

```bash
docker build -t clausecompass-api .
```

### Run with environment variables

```bash
docker run -p 8000:8000 --env-file .env clausecompass-api
```

### Cloud Run Deployment

```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/clausecompass-api

# Deploy to Cloud Run
gcloud run deploy clausecompass-api \
  --image gcr.io/$PROJECT_ID/clausecompass-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=$PROJECT_ID,DOC_AI_PROCESSOR_ID=$DOC_AI_PROCESSOR_ID
```

## 🛠️ Development

### Code Quality

```bash
# Format code
poetry run black app/
poetry run isort app/

# Type checking
poetry run mypy app/

# Run tests (when implemented)
poetry run pytest
```

### Adding Dependencies

```bash
# Production dependency
poetry add package-name

# Development dependency
poetry add --group dev package-name
```

## 🔒 Security Features

- **PII Masking**: Automatic detection and masking of personal information
- **Rate Limiting**: Per-session request limiting
- **CORS Protection**: Configurable cross-origin request handling
- **Input Validation**: Pydantic-based request validation
- **Secure Headers**: Production security middleware

## 📊 Monitoring & Logging

- **Structured Logging**: JSON-formatted logs for GCP Cloud Logging
- **Health Checks**: Kubernetes/Cloud Run compatible health endpoints
- **Metrics**: Built-in processing and performance metrics
- **Error Tracking**: Comprehensive error handling and logging

## 🚧 Implementation Status

### ✅ Completed (Phase 1)

- [x] FastAPI application structure with Uvicorn
- [x] Poetry dependency management
- [x] Docker multi-stage build
- [x] Environment configuration with Pydantic Settings
- [x] API endpoint structure and models
- [x] Health check endpoints
- [x] Structured logging setup

### 🔄 In Progress (Phase 2-8)

- [ ] Document processing pipeline (Document AI + OCR fallback)
- [ ] Gemini integration for summarization
- [ ] Clause segmentation logic
- [ ] Risk analysis and classification
- [ ] Firestore integration
- [ ] Embeddings and Q&A system
- [ ] Analytics and monitoring
- [ ] Production deployment configuration

## 📝 License

This project is part of the ClauseCompass hackathon submission.
