# Development Setup Guide

This guide explains how to run the GenAI Exchange application in development mode with both frontend and backend services.

## Prerequisites

- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)
- Poetry (for Python package management)
- Google Cloud Project with enabled APIs (for full functionality)

## Quick Start

### 1. Install Dependencies

```bash
# Frontend dependencies
npm install

# Backend dependencies
cd backend && poetry install
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env.local

# Edit .env.local with your configuration
# For local development, the default settings should work
```

### 3. Run Development Servers

**Option A: Run each service separately**

Terminal 1 (Backend):
```bash
npm run dev:backend
# This runs: cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 (Frontend):
```bash
npm run dev:frontend
# This runs: next dev --turbopack
```

**Option B: Run frontend only (for UI development)**

```bash
npm run dev
# Backend API calls will fail, but you can develop the UI
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)

## Development URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1
- Health Check: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

## Troubleshooting

### Backend Issues

1. **Poetry not found**: Install with `curl -sSL https://install.python-poetry.org | python3 -`
2. **Port 8000 in use**: Change port in dev:backend script or kill existing process
3. **Missing dependencies**: Run `cd backend && poetry install`

### Frontend Issues

1. **Port 3000 in use**: Next.js will automatically use next available port
2. **Module not found**: Run `npm install` to install dependencies
3. **Build errors**: Run `npm run type-check` to check TypeScript issues

### API Connection Issues

1. **CORS errors**: Ensure backend is running on port 8000
2. **Network errors**: Check that `NEXT_PUBLIC_API_URL` in `.env.local` matches backend URL
3. **404 errors**: Verify backend API endpoints are accessible at http://localhost:8000/docs

## Mock Mode

For development without Google Cloud setup, the backend includes placeholder responses that allow you to test the frontend integration.

## Production Deployment

- Update `NEXT_PUBLIC_API_URL` to your production backend URL
- Ensure all Google Cloud APIs are properly configured
- Run `npm run build` to create production build