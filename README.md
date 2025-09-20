# LegalEase AI - GenAI Exchange Hackathon MVP

**🏆 Built for the GenAI Exchange Hackathon**

An AI-powered legal document analysis platform that transforms complex legal jargon into plain-language summaries, identifies risk levels, and provides intelligent Q&A capabilities. This MVP was developed as part of the GenAI Exchange hackathon to address the critical need for accessible legal document comprehension in India and beyond.

## 🎯 Problem Statement

Legal documents in India are dense, jargon-heavy, and rarely localized. Consumers often sign contracts without fully understanding hidden risks like indemnity scope, auto-renewals, or unlimited liability clauses. This creates an asymmetric bargaining power dynamic where individuals lack access to confidential, jargon-free explanation tools.

## 🚀 MVP Solution

LegalEase AI provides:

- **Plain-Language Summaries**: Converts complex legal clauses into 8th-grade reading level explanations
- **Risk Assessment**: Categorizes and flags clauses by risk level (low/moderate/attention)
- **Multilingual Support**: English and Hindi with automatic language detection
- **Intelligent Q&A**: Retrieval-grounded question answering with source citations
- **Readability Analytics**: Measurable readability improvement metrics
- **Visual Risk Analysis**: Interactive heatmaps and analytics dashboards

## ✨ Key Features

### 🔍 Document Processing Pipeline

- **Smart OCR**: Google Document AI integration with PyPDF2 fallback
- **Clause Segmentation**: Intelligent clause detection and categorization
- **Batch Processing**: Efficient processing of up to 10-page documents
- **Privacy Protection**: PII detection and masking with Google DLP API

### 🎯 AI-Powered Analysis

- **Gemini Integration**: Advanced summarization using Google's Gemini models
- **Hybrid Risk Assessment**: Keyword-based heuristics + LLM analysis
- **Readability Metrics**: Flesch-Kincaid, Gunning Fog, SMOG index calculations
- **Confidence Scoring**: Transparent AI confidence levels

### 💬 Intelligent Chat Interface

- **Context-Aware Conversations**: Multi-document chat sessions with memory
- **Source Citations**: All answers include specific clause references
- **Language Detection**: Automatic language switching based on user input
- **Real-time Processing**: Live document analysis with progress indicators

### 🌍 Internationalization

- **Multilingual UI**: English, Hindi, and Bengali support
- **Smart Language Detection**: Auto-detection with manual override options
- **Localized Content**: Region-specific legal terminology understanding

### 📊 Analytics & Insights

- **Risk Heatmaps**: Visual representation of document risk distribution
- **Readability Dashboards**: Before/after readability improvement metrics
- **Processing Analytics**: Document processing statistics and performance metrics
- **Usage Tracking**: Anonymous analytics for platform improvements

## 🏗️ Architecture

### Frontend (Next.js 15)

- **Framework**: Next.js 15 with App Router and Turbopack
- **Styling**: Tailwind CSS with custom design system
- **Components**: Radix UI primitives with custom styling
- **State Management**: TanStack React Query for server state
- **Internationalization**: next-intl for multilingual support
- **Real-time UI**: Live progress indicators and streaming responses

### Backend (FastAPI + Google Cloud)

- **API Framework**: FastAPI with async/await for high performance
- **Language**: Python 3.12 with Poetry dependency management
- **Database**: Google Firestore for document and session storage
- **AI Services**:
  - Google Gemini for summarization and Q&A
  - Google Document AI for OCR and layout analysis
  - Custom embeddings service for semantic search
- **Cloud Services**:
  - Google Cloud Storage for file storage
  - Google DLP API for PII protection
  - Google Pub/Sub for analytics events
  - Google BigQuery for metrics storage

### Key Services

- **Document Orchestrator**: Manages the complete processing pipeline
- **Risk Analyzer**: Hybrid keyword + LLM risk assessment
- **Readability Service**: Multi-metric readability analysis
- **Chat Session Service**: Conversation memory and context management
- **Language Detection**: Advanced multilingual support
- **Embeddings Service**: Vector search for Q&A relevance

## 🚦 Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- Python 3.12+
- Poetry for Python dependency management
- Google Cloud Project with enabled APIs:
  - Document AI API
  - Gemini API (Vertex AI)
  - Firestore API
  - Cloud Storage API
  - DLP API (optional)

### Frontend Setup

1. **Install dependencies**

```bash
npm install
# or
yarn install
# or
pnpm install
```

2. **Environment configuration**

```bash
cp .env.example .env.local
```

Edit `.env.local` with your API endpoints.

3. **Start development server**

```bash
npm run dev
# or
npm run dev:frontend
```

4. **Access the application**
   Open [http://localhost:3000](http://localhost:3000) in your browser.

### Backend Setup

1. **Navigate to backend directory**

```bash
cd backend
```

2. **Install Poetry and dependencies**

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

3. **Environment configuration**

```bash
cp .env.example .env
```

Edit `.env` with your Google Cloud credentials and project settings.

4. **Google Cloud authentication**

```bash
# Place your service account key file
cp /path/to/your/credentials.json ./credentials.json

# Or use gcloud CLI
gcloud auth application-default login
```

5. **Start the backend server**

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# or
npm run dev:backend
```

## 📋 API Endpoints

### Document Processing

- `POST /api/v1/documents/ingest` - Upload and process legal documents
- `GET /api/v1/documents/status/{doc_id}` - Get processing status
- `GET /api/v1/documents/clauses?doc_id={id}` - Get clause summaries
- `GET /api/v1/documents/clause/{clause_id}?doc_id={id}` - Get detailed clause analysis

### Question & Answer

- `POST /api/v1/qa/ask` - Ask questions about document clauses
- `GET /api/v1/qa/history/{doc_id}` - Get Q&A conversation history

### Chat Sessions

- `POST /api/v1/chat/sessions` - Create new chat session
- `GET /api/v1/chat/sessions` - List user chat sessions
- `PUT /api/v1/chat/sessions/{session_id}/documents` - Update session context
- `POST /api/v1/chat/sessions/{session_id}/messages` - Add message to session

### Analytics & Metrics

- `GET /api/v1/metrics/summary` - Aggregated platform metrics
- `GET /api/v1/metrics/processing-stats` - Processing performance statistics
- `GET /api/v1/metrics/risk-patterns` - Risk pattern analysis

## 🎨 UI Components

### Core Components

- **Dashboard**: Main application interface with sidebar and chat
- **ChatInterface**: Conversational AI interface with markdown support
- **RiskHeatmap**: Interactive risk visualization grid
- **ReadabilityPanel**: Readability metrics and improvement analytics
- **UploadSuccessCard**: Document upload progress and status
- **LanguageSelector**: Multilingual switching interface

### Design System

- **Color Palette**: Purple/pink gradients for AI features, semantic colors for risk levels
- **Typography**: Custom font optimization with Geist font family
- **Responsive Design**: Mobile-first approach with breakpoint-specific layouts
- **Dark Theme**: Professional dark mode interface for extended usage

## 📊 Performance Features

### Frontend Optimizations

- **Next.js 15**: Latest performance improvements with Turbopack
- **Code Splitting**: Automatic route-based and component-based splitting
- **Image Optimization**: Automatic image optimization and lazy loading
- **Caching**: Intelligent caching with React Query and browser cache

### Backend Optimizations

- **Async Processing**: Fully asynchronous request handling
- **Batch Operations**: Efficient batch processing for multiple clauses
- **Connection Pooling**: Optimized database and API connections
- **Background Tasks**: Non-blocking document processing
- **Caching**: In-memory caching for frequently accessed data

## 🔒 Security & Privacy

### Data Protection

- **PII Detection**: Automatic identification and masking of personal information
- **Data Anonymization**: Anonymous analytics without storing personal data
- **Secure Storage**: Encrypted data storage in Google Cloud
- **Access Controls**: Role-based access with proper authentication

### Privacy Controls

- **Data Retention**: Configurable data retention policies
- **User Consent**: Clear consent mechanisms for data processing
- **Audit Logging**: Comprehensive audit trails for all operations
- **GDPR Compliance**: Privacy-first architecture design

## 🌟 Hackathon Innovation

This project was built as an MVP for the **GenAI Exchange Hackathon** with the following innovations:

### 🎯 Unique Value Propositions

1. **Hybrid Risk Assessment**: Combines keyword detection with LLM analysis for accurate risk identification
2. **Multilingual Legal AI**: First-of-its-kind Hindi/English legal document analysis
3. **Measurable Readability**: Quantifiable improvement metrics showing readability gains
4. **Context-Aware Q&A**: Retrieval-grounded responses with source citations to prevent hallucination
5. **Real-time Processing**: Live progress indicators with detailed processing stages

### 🚀 Technical Innovations

- **Adaptive Language Detection**: Smart language switching based on user context
- **Clause Segmentation Algorithm**: Custom legal document parsing with heading detection
- **Risk Escalation Logic**: Sophisticated risk level determination with confidence scoring
- **Streaming Analytics**: Real-time processing status with WebSocket-like updates
- **Privacy-First Architecture**: PII masking before any AI processing

### 📈 Scalability Considerations

- **Microservices Architecture**: Loosely coupled services for independent scaling
- **Cloud-Native Design**: Built for Google Cloud Platform with auto-scaling capabilities
- **API-First Approach**: RESTful APIs enabling future mobile and third-party integrations
- **Modular Frontend**: Component-based architecture for easy feature additions
