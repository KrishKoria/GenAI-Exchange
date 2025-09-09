# GenAI-Exchange Windows Setup Guide

## 🚀 Quick Start

This repository includes a comprehensive PowerShell script that automatically sets up your entire development environment on Windows with a single command.

### One-Command Setup

```powershell
# Run in PowerShell (recommended: as Administrator)
.\setup-genai-exchange.ps1
```

That's it! The script handles everything automatically.

---

## 📋 What Gets Installed

### Core Development Tools
- **Node.js 20.x LTS** - Frontend development
- **Python 3.12** - Backend development  
- **Poetry** - Python dependency management
- **Git** - Version control
- **Google Cloud CLI** - GCP services integration
- **Chocolatey** - Windows package manager

### Project Dependencies
- **Frontend**: Next.js 15, React 19, TypeScript, TailwindCSS, and all npm packages
- **Backend**: FastAPI, Uvicorn, and all Python packages via Poetry

### Google Cloud Platform Services
- Document AI (document processing)
- Vertex AI / Gemini (AI text processing)
- Google Generative AI (embeddings)
- Firestore (document database)
- Cloud Storage (file storage)
- Data Loss Prevention API (PII detection)
- BigQuery (analytics/logging)
- Pub/Sub (event messaging)

---

## 🛠️ Setup Options

### Standard Setup (Recommended)
```powershell
.\setup-genai-exchange.ps1
```
Installs everything including GCP tools and configuration.

### Skip GCP Setup
```powershell
.\setup-genai-exchange.ps1 -SkipGCP
```
Installs only local development tools, skips Google Cloud configuration.

### Skip Chocolatey Installation  
```powershell
.\setup-genai-exchange.ps1 -SkipChocolatey
```
Useful if Chocolatey is already installed.

### Custom Project Path
```powershell
.\setup-genai-exchange.ps1 -ProjectPath "C:\MyProjects\GenAI-Exchange"
```

---

## 📁 Prerequisites

### System Requirements
- **Windows 10 or later** (Windows 11 recommended)
- **PowerShell 5.1 or later** (PowerShell 7+ recommended)
- **Internet connection** for downloading packages
- **Administrator privileges** (recommended for some installations)

### Before Running
1. **Download/Clone the repository**
2. **Open PowerShell** in the project root directory
3. **Consider running as Administrator** for smoother installation

---

## 🔧 What the Script Does

### Phase 1: Prerequisites & Core Tools
- ✅ Installs Chocolatey package manager
- ✅ Installs Git for version control
- ✅ Installs Node.js 20.x LTS with npm
- ✅ Installs Python 3.12
- ✅ Installs Poetry for Python dependency management
- ✅ Installs Google Cloud CLI (gcloud)

### Phase 2: Project Setup
- ✅ Installs all Node.js dependencies (`npm install`)
- ✅ Sets up Python virtual environment with Poetry
- ✅ Installs all Python dependencies (`poetry install`)
- ✅ Creates environment file template (`.env.example`)

### Phase 3: GCP Configuration
- ✅ Initializes Google Cloud CLI (`gcloud init`)
- ✅ Enables all required GCP APIs
- ✅ Sets up Application Default Credentials
- ✅ Provides guidance for manual GCP resource creation

### Phase 4: Verification & Testing
- ✅ Verifies all tool installations
- ✅ Tests project dependencies
- ✅ Validates basic project functionality
- ✅ Creates detailed setup log

---

## ⚡ After Setup

### 1. Configure Environment Variables
```bash
# Copy the template
cp backend/.env.example backend/.env

# Edit backend/.env with your actual values:
# - PROJECT_ID=your-gcp-project-id
# - GOOGLE_GENAI_API_KEY=your-api-key
# - DOC_AI_PROCESSOR_ID=your-processor-id
# - SECRET_KEY=your-secret-key
```

### 2. Start Development Servers

**Frontend Only:**
```bash
npm run dev
# Opens http://localhost:3000
```

**Backend Only:**
```bash
npm run dev:backend
# Opens http://localhost:8000
# API docs: http://localhost:8000/docs
```

**Both (in separate terminals):**
```bash
# Terminal 1 - Frontend
npm run dev

# Terminal 2 - Backend  
npm run dev:backend
```

### 3. Required GCP Setup

The script guides you through these steps, but you'll need to complete them manually:

#### Create Document AI Processor
1. Go to [Google Cloud Document AI Console](https://console.cloud.google.com/ai/document-ai)
2. Create a new processor of type "Document OCR" 
3. Note the Processor ID
4. Add it to your `.env` file as `DOC_AI_PROCESSOR_ID`

#### Get Google Generative AI API Key
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Add it to your `.env` file as `GOOGLE_GENAI_API_KEY`

---

## 🔍 Troubleshooting

### Common Issues

**PowerShell Execution Policy Error:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Permission Denied Errors:**
- Run PowerShell as Administrator
- Or install tools manually using Chocolatey

**Path Not Found After Installation:**
- Close and reopen PowerShell/terminal
- Or restart your computer

**GCP Authentication Issues:**
```bash
gcloud auth login
gcloud auth application-default login
```

### Getting Help

1. **Check the setup log**: `setup-log-[timestamp].txt`
2. **Review error messages** in the console output
3. **Run individual commands** to isolate issues
4. **Check tool versions** with commands like `node --version`

### Manual Installation Fallback

If the script fails, you can install tools manually:

```powershell
# Install Chocolatey first
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Then install individual tools
choco install nodejs-lts python312 git gcloudsdk -y

# Install Poetry
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

---

## 📚 Additional Resources

### Project Documentation
- **Frontend**: Built with Next.js 15 + React 19 + TypeScript
- **Backend**: Built with Python 3.12 + FastAPI + Poetry  
- **Database**: Google Firestore
- **AI Services**: Google Vertex AI, Document AI, Generative AI

### Useful Commands

```bash
# Frontend development
npm run dev          # Start frontend dev server
npm run build        # Build for production
npm run lint         # Run ESLint
npm run type-check   # TypeScript checking

# Backend development  
cd backend
poetry shell         # Activate virtual environment
poetry run uvicorn app.main:app --reload  # Start backend dev server
poetry add package-name                   # Add new dependency
poetry run python -m pytest             # Run tests

# GCP commands
gcloud init                    # Initialize/reconfigure gcloud
gcloud auth list              # List authenticated accounts
gcloud config list           # Show current configuration
gcloud services list --enabled  # List enabled APIs
```

---

## 🎯 What's Next?

After setup is complete:

1. **Explore the codebase** - Check out the frontend (`src/`) and backend (`backend/app/`) directories
2. **Read the project README** - Learn about the GenAI-Exchange features
3. **Start developing** - The development servers support hot reload
4. **Test the API** - Visit `http://localhost:8000/docs` for interactive API documentation

---

**Happy coding! 🚀**