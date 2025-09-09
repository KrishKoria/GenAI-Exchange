<#
.SYNOPSIS
    Comprehensive Windows setup script for GenAI-Exchange project
    
.DESCRIPTION
    This script automatically sets up all prerequisites, dependencies, and services
    needed to run the GenAI-Exchange (LegalEase AI) project on Windows.
    
    The script handles:
    - Installing core development tools (Node.js, Python, Poetry, Git, gcloud CLI)
    - Setting up the project environment
    - Configuring Google Cloud Platform services
    - Creating necessary environment files
    - Verifying the complete setup
    
.PARAMETER SkipGCP
    Skip Google Cloud Platform setup and configuration
    
.PARAMETER SkipChocolatey
    Skip Chocolatey installation (if already installed)
    
.PARAMETER ProjectPath
    Specify custom project directory path
    
.EXAMPLE
    .\setup-genai-exchange.ps1
    
.EXAMPLE
    .\setup-genai-exchange.ps1 -SkipGCP
    
.NOTES
    Author: GenAI-Exchange Team
    Requires: Windows PowerShell 5.1 or PowerShell 7+
    Requires: Administrator privileges for some installations
#>

[CmdletBinding()]
param(
    [switch]$SkipGCP,
    [switch]$SkipChocolatey,
    [string]$ProjectPath = $PSScriptRoot
)

# Script configuration
$ErrorActionPreference = "Stop"
$WarningPreference = "Continue"

# Color scheme for output
$Colors = @{
    Success = "Green"
    Warning = "Yellow" 
    Error = "Red"
    Info = "Cyan"
    Highlight = "Magenta"
}

# Required versions
$RequiredVersions = @{
    NodeJS = "22.0.0"
    Python = "3.12.0"
    Poetry = "1.7.0"
}

# GCP Services that need to be enabled
$GCPServices = @(
    "documentai.googleapis.com",
    "aiplatform.googleapis.com", 
    "generativelanguage.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "dlp.googleapis.com",
    "bigquery.googleapis.com",
    "pubsub.googleapis.com"
)

# Logging setup
$LogFile = Join-Path $ProjectPath "setup-log-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
$Global:LogEntries = @()

#region Helper Functions

function Write-ColoredOutput {
    param(
        [string]$Message,
        [string]$Color = "White",
        [switch]$NoNewLine
    )
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    $Global:LogEntries += $logEntry
    
    if ($NoNewLine) {
        Write-Host "[$timestamp] $Message" -ForegroundColor $Color -NoNewline
    } else {
        Write-Host "[$timestamp] $Message" -ForegroundColor $Color
    }
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Status = "Info"
    )
    
    $color = $Colors[$Status]
    $prefix = switch ($Status) {
        "Success" { "✓" }
        "Warning" { "⚠" }
        "Error" { "✗" }
        "Info" { "ℹ" }
        "Highlight" { "★" }
        default { "•" }
    }
    
    Write-ColoredOutput "$prefix $Message" -Color $color
}

function Test-AdminPrivileges {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-CommandExists {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Compare-Version {
    param(
        [string]$Version1,
        [string]$Version2
    )
    
    try {
        $v1 = [version]($Version1 -replace '[^\d\.]', '')
        $v2 = [version]($Version2 -replace '[^\d\.]', '')
        return $v1 -ge $v2
    } catch {
        return $false
    }
}

function Install-Chocolatey {
    if ($SkipChocolatey -or (Test-CommandExists "choco")) {
        Write-Status "Chocolatey is already installed" "Success"
        return $true
    }
    
    Write-Status "Installing Chocolatey package manager..." "Info"
    try {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        if (Test-CommandExists "choco") {
            Write-Status "Chocolatey installed successfully" "Success"
            return $true
        } else {
            throw "Chocolatey installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Chocolatey: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Install-NodeJS {
    Write-Status "Checking Node.js installation..." "Info"
    
    if (Test-CommandExists "node") {
        $currentVersion = & node --version 2>$null
        $currentVersion = $currentVersion -replace '^v', ''
        
        if (Compare-Version $currentVersion $RequiredVersions.NodeJS) {
            Write-Status "Node.js $currentVersion is already installed (required: $($RequiredVersions.NodeJS)+)" "Success"
            return $true
        } else {
            Write-Status "Node.js $currentVersion is outdated (required: $($RequiredVersions.NodeJS)+)" "Warning"
        }
    }
    
    Write-Status "Installing Node.js LTS..." "Info"
    try {
        & choco install nodejs-lts -y --force
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Start-Sleep -Seconds 5
        
        if (Test-CommandExists "node") {
            $installedVersion = & node --version 2>$null
            Write-Status "Node.js $installedVersion installed successfully" "Success"
            return $true
        } else {
            throw "Node.js installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Node.js: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Install-Python {
    Write-Status "Checking Python installation..." "Info"
    
    if (Test-CommandExists "python") {
        $currentVersion = & python --version 2>$null
        $currentVersion = ($currentVersion -split '\s+')[1]
        
        if (Compare-Version $currentVersion $RequiredVersions.Python) {
            Write-Status "Python $currentVersion is already installed (required: $($RequiredVersions.Python)+)" "Success"
            return $true
        } else {
            Write-Status "Python $currentVersion is outdated (required: $($RequiredVersions.Python)+)" "Warning"
        }
    }
    
    Write-Status "Installing Python 3.12..." "Info"
    try {
        & choco install python312 -y --force
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Start-Sleep -Seconds 5
        
        if (Test-CommandExists "python") {
            $installedVersion = & python --version 2>$null
            Write-Status "$installedVersion installed successfully" "Success"
            return $true
        } else {
            throw "Python installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Python: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Install-Poetry {
    Write-Status "Checking Poetry installation..." "Info"
    
    if (Test-CommandExists "poetry") {
        $currentVersion = & poetry --version 2>$null
        $currentVersion = ($currentVersion -split '\s+')[-1] -replace '[()]', ''
        
        if (Compare-Version $currentVersion $RequiredVersions.Poetry) {
            Write-Status "Poetry $currentVersion is already installed (required: $($RequiredVersions.Poetry)+)" "Success"
            return $true
        } else {
            Write-Status "Poetry $currentVersion is outdated (required: $($RequiredVersions.Poetry)+)" "Warning"
        }
    }
    
    Write-Status "Installing Poetry..." "Info"
    try {
        # Install Poetry using the official installer
        (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
        
        # Add Poetry to PATH
        $poetryPath = "$env:USERPROFILE\.local\bin"
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentPath -notlike "*$poetryPath*") {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$poetryPath", "User")
        }
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Start-Sleep -Seconds 5
        
        if (Test-CommandExists "poetry") {
            $installedVersion = & poetry --version 2>$null
            Write-Status "Poetry installed successfully: $installedVersion" "Success"
            return $true
        } else {
            throw "Poetry installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Poetry: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Install-Git {
    if (Test-CommandExists "git") {
        $version = & git --version 2>$null
        Write-Status "Git is already installed: $version" "Success"
        return $true
    }
    
    Write-Status "Installing Git..." "Info"
    try {
        & choco install git -y --force
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Start-Sleep -Seconds 5
        
        if (Test-CommandExists "git") {
            $installedVersion = & git --version 2>$null
            Write-Status "Git installed successfully: $installedVersion" "Success"
            return $true
        } else {
            throw "Git installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Git: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Install-GoogleCloudCLI {
    if (Test-CommandExists "gcloud") {
        $version = & gcloud version --quiet 2>$null | Select-String "Google Cloud SDK"
        Write-Status "Google Cloud CLI is already installed: $version" "Success"
        return $true
    }
    
    Write-Status "Installing Google Cloud CLI..." "Info"
    try {
        & choco install gcloudsdk -y --force
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Start-Sleep -Seconds 10
        
        if (Test-CommandExists "gcloud") {
            $installedVersion = & gcloud version --quiet 2>$null | Select-String "Google Cloud SDK"
            Write-Status "Google Cloud CLI installed successfully: $installedVersion" "Success"
            return $true
        } else {
            throw "Google Cloud CLI installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Google Cloud CLI: $($_.Exception.Message)" "Error"
        return $false
    }
}

#endregion

#region Main Functions

function Initialize-Prerequisites {
    Write-Status "=== Phase 1: Installing Prerequisites & Core Tools ===" "Highlight"
    
    # Check Windows version
    $winVersion = [System.Environment]::OSVersion.Version
    if ($winVersion.Major -lt 10) {
        Write-Status "Warning: Windows 10 or later is recommended for best compatibility" "Warning"
    }
    
    # Check if running as administrator for some installations
    if (-not (Test-AdminPrivileges)) {
        Write-Status "Warning: Some installations may require administrator privileges" "Warning"
        Write-Status "Consider running PowerShell as Administrator if you encounter permission issues" "Info"
    }
    
    # Install tools
    $success = $true
    
    if (-not (Install-Chocolatey)) { $success = $false }
    if (-not (Install-Git)) { $success = $false }
    if (-not (Install-NodeJS)) { $success = $false }
    if (-not (Install-Python)) { $success = $false }
    if (-not (Install-Poetry)) { $success = $false }
    if (-not $SkipGCP -and -not (Install-GoogleCloudCLI)) { $success = $false }
    
    if ($success) {
        Write-Status "All prerequisites installed successfully!" "Success"
    } else {
        Write-Status "Some prerequisite installations failed. Please check the errors above." "Error"
        return $false
    }
    
    return $true
}

function Initialize-ProjectSetup {
    Write-Status "=== Phase 2: Project Setup ===" "Highlight"
    
    try {
        # Ensure we're in the project directory
        if (-not (Test-Path $ProjectPath)) {
            Write-Status "Project directory not found: $ProjectPath" "Error"
            return $false
        }
        
        Set-Location $ProjectPath
        Write-Status "Working in project directory: $ProjectPath" "Info"
        
        # Verify project files exist
        $requiredFiles = @("package.json", "backend\pyproject.toml")
        foreach ($file in $requiredFiles) {
            if (-not (Test-Path $file)) {
                Write-Status "Required project file not found: $file" "Error"
                return $false
            }
        }
        
        # Install Node.js dependencies
        Write-Status "Installing Node.js dependencies..." "Info"
        & npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Status "Failed to install Node.js dependencies" "Error"
            return $false
        }
        Write-Status "Node.js dependencies installed successfully" "Success"
        
        # Setup Python environment with Poetry
        Write-Status "Setting up Python environment with Poetry..." "Info"
        Set-Location "backend"
        
        # Configure Poetry to create venv in project directory
        & poetry config virtualenvs.in-project true
        
        # Install Python dependencies
        & poetry install
        if ($LASTEXITCODE -ne 0) {
            Write-Status "Failed to install Python dependencies" "Error"
            Set-Location $ProjectPath
            return $false
        }
        Write-Status "Python dependencies installed successfully" "Success"
        
        Set-Location $ProjectPath
        
        # Create environment file template
        $envTemplate = @"
# GenAI-Exchange Environment Configuration
# Copy this to .env and fill in your actual values

# Required: Google Cloud Project Configuration
PROJECT_ID=your-gcp-project-id
PROJECT_NUMBER=your-gcp-project-number

# Required: API Keys
SECRET_KEY=your-secret-key-here
GOOGLE_GENAI_API_KEY=your-google-genai-api-key
DOC_AI_PROCESSOR_ID=your-document-ai-processor-id

# Optional: Service Account (if not using default credentials)
GOOGLE_APPLICATION_CREDENTIALS=path-to-your-service-account-key.json

# Application Configuration
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ALLOWED_HOSTS=localhost,127.0.0.1

# GCP Service Configuration
LOCATION=us-central1
DOC_AI_LOCATION=us
VERTEX_AI_LOCATION=us-central1
GEMINI_MODEL_NAME=gemini-2.5-flash

# Firestore Configuration
FIRESTORE_DATABASE=(default)

# BigQuery Configuration
BIGQUERY_DATASET=clausecompass
BIGQUERY_TABLE=events

# Pub/Sub Configuration
PUBSUB_TOPIC=clausecompass-events

# Application Limits
MAX_FILE_SIZE_MB=10
MAX_PAGES=10
MAX_CLAUSES_PER_BATCH=10
RATE_LIMIT_PER_MINUTE=60
MAX_PROMPT_TOKENS=30000
MAX_OUTPUT_TOKENS=8000

# Privacy Configuration
DLP_ENABLED=true
"@
        
        $envPath = Join-Path $ProjectPath "backend\.env.example"
        Set-Content -Path $envPath -Value $envTemplate
        Write-Status "Environment template created at: backend\.env.example" "Success"
        
        Write-Status "Project setup completed successfully!" "Success"
        return $true
        
    } catch {
        Write-Status "Project setup failed: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Initialize-GCPSetup {
    if ($SkipGCP) {
        Write-Status "Skipping GCP setup as requested" "Info"
        return $true
    }
    
    Write-Status "=== Phase 3: Google Cloud Platform Configuration ===" "Highlight"
    
    try {
        # Initialize gcloud
        Write-Status "Initializing Google Cloud CLI..." "Info"
        Write-Host ""
        Write-ColoredOutput "Please follow the prompts to:" "Yellow"
        Write-ColoredOutput "1. Log in to your Google Cloud account" "Yellow"
        Write-ColoredOutput "2. Select or create a Google Cloud project" "Yellow"
        Write-ColoredOutput "3. Choose a default region (recommended: us-central1)" "Yellow"
        Write-Host ""
        
        & gcloud init
        if ($LASTEXITCODE -ne 0) {
            Write-Status "GCP initialization failed or was cancelled" "Warning"
            Write-Status "You can run 'gcloud init' manually later" "Info"
            return $false
        }
        
        # Get current project
        $currentProject = & gcloud config get-value project 2>$null
        if (-not $currentProject) {
            Write-Status "No GCP project selected. Please run 'gcloud init' to set up your project" "Warning"
            return $false
        }
        
        Write-Status "Current GCP Project: $currentProject" "Success"
        
        # Enable required APIs
        Write-Status "Enabling required GCP APIs..." "Info"
        foreach ($service in $GCPServices) {
            Write-Status "Enabling $service..." "Info"
            & gcloud services enable $service --project=$currentProject
            if ($LASTEXITCODE -eq 0) {
                Write-Status "✓ $service enabled" "Success"
            } else {
                Write-Status "Failed to enable $service" "Warning"
            }
        }
        
        # Check for Application Default Credentials
        Write-Status "Setting up authentication..." "Info"
        & gcloud auth application-default login
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Application Default Credentials configured" "Success"
        } else {
            Write-Status "Failed to configure Application Default Credentials" "Warning"
        }
        
        # Display next steps for GCP setup
        Write-Host ""
        Write-Status "GCP Services Configuration Required:" "Highlight"
        Write-ColoredOutput "Please complete the following steps in Google Cloud Console:" "Yellow"
        Write-ColoredOutput "1. Create a Document AI processor:" "White"
        Write-ColoredOutput "   - Go to: https://console.cloud.google.com/ai/document-ai" "Cyan"
        Write-ColoredOutput "   - Create a 'Document OCR' processor" "White"
        Write-ColoredOutput "   - Note the Processor ID" "White"
        Write-Host ""
        Write-ColoredOutput "2. Get Google Generative AI API key:" "White"
        Write-ColoredOutput "   - Go to: https://aistudio.google.com/app/apikey" "Cyan"
        Write-ColoredOutput "   - Create an API key" "White"
        Write-Host ""
        Write-ColoredOutput "3. Update backend/.env file with your values" "White"
        Write-Host ""
        
        Write-Status "GCP setup completed!" "Success"
        return $true
        
    } catch {
        Write-Status "GCP setup failed: $($_.Exception.Message)" "Error"
        return $false
    }
}

function Test-ProjectSetup {
    Write-Status "=== Phase 4: Verification & Testing ===" "Highlight"
    
    $allPassed = $true
    
    # Test tool installations
    Write-Status "Verifying tool installations..." "Info"
    
    $tools = @(
        @{ Name = "Node.js"; Command = "node"; VersionArg = "--version"; Required = $true },
        @{ Name = "npm"; Command = "npm"; VersionArg = "--version"; Required = $true },
        @{ Name = "Python"; Command = "python"; VersionArg = "--version"; Required = $true },
        @{ Name = "Poetry"; Command = "poetry"; VersionArg = "--version"; Required = $true },
        @{ Name = "Git"; Command = "git"; VersionArg = "--version"; Required = $true },
        @{ Name = "Google Cloud CLI"; Command = "gcloud"; VersionArg = "--version"; Required = $false }
    )
    
    foreach ($tool in $tools) {
        if (Test-CommandExists $tool.Command) {
            try {
                $version = & $tool.Command $tool.VersionArg 2>$null | Select-Object -First 1
                Write-Status "✓ $($tool.Name): $version" "Success"
            } catch {
                Write-Status "✓ $($tool.Name): Available" "Success"
            }
        } else {
            if ($tool.Required) {
                Write-Status "✗ $($tool.Name): Not found" "Error"
                $allPassed = $false
            } else {
                Write-Status "? $($tool.Name): Not found (optional)" "Warning"
            }
        }
    }
    
    # Test project dependencies
    Write-Status "Verifying project dependencies..." "Info"
    
    try {
        Set-Location $ProjectPath
        
        # Check node_modules
        if (Test-Path "node_modules") {
            Write-Status "✓ Node.js dependencies installed" "Success"
        } else {
            Write-Status "✗ Node.js dependencies not installed" "Error"
            $allPassed = $false
        }
        
        # Check Python virtual environment
        Set-Location "backend"
        $poetryCheck = & poetry check 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "✓ Python dependencies verified" "Success"
        } else {
            Write-Status "✗ Python dependencies verification failed" "Error"
            $allPassed = $false
        }
        
        Set-Location $ProjectPath
        
    } catch {
        Write-Status "Error during dependency verification: $($_.Exception.Message)" "Error"
        $allPassed = $false
    }
    
    # Test basic project startup (dry run)
    Write-Status "Testing project startup..." "Info"
    
    try {
        # Test frontend build
        Write-Status "Testing frontend build..." "Info"
        $buildOutput = & npm run build 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Status "✓ Frontend build successful" "Success"
        } else {
            Write-Status "✗ Frontend build failed (this is expected if .env is not configured)" "Warning"
        }
        
        # Test backend syntax (without starting server)
        Write-Status "Testing backend syntax..." "Info"
        Set-Location "backend"
        $syntaxCheck = & poetry run python -m py_compile app/main.py 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "✓ Backend syntax check passed" "Success"
        } else {
            Write-Status "✗ Backend syntax check failed" "Warning"
        }
        
        Set-Location $ProjectPath
        
    } catch {
        Write-Status "Error during startup test: $($_.Exception.Message)" "Warning"
    }
    
    return $allPassed
}

function Show-NextSteps {
    Write-Status "=== Setup Complete! Next Steps ===" "Highlight"
    Write-Host ""
    
    Write-ColoredOutput "1. Configure Environment Variables:" "Yellow"
    Write-ColoredOutput "   • Copy backend/.env.example to backend/.env" "White"
    Write-ColoredOutput "   • Fill in your GCP project details and API keys" "White"
    Write-Host ""
    
    Write-ColoredOutput "2. Start Development Servers:" "Yellow"
    Write-ColoredOutput "   Frontend: npm run dev" "Cyan"
    Write-ColoredOutput "   Backend:  npm run dev:backend" "Cyan"
    Write-ColoredOutput "   Or both:  npm run dev (frontend only by default)" "Cyan"
    Write-Host ""
    
    Write-ColoredOutput "3. Access the Application:" "Yellow"
    Write-ColoredOutput "   Frontend: http://localhost:3000" "Cyan"
    Write-ColoredOutput "   Backend:  http://localhost:8000" "Cyan"
    Write-ColoredOutput "   API Docs: http://localhost:8000/docs" "Cyan"
    Write-Host ""
    
    Write-ColoredOutput "4. Additional Resources:" "Yellow"
    Write-ColoredOutput "   • Project README: README.md" "White"
    Write-ColoredOutput "   • Environment template: backend/.env.example" "White"
    Write-ColoredOutput "   • Setup log: $LogFile" "White"
    Write-Host ""
    
    if (-not $SkipGCP) {
        Write-ColoredOutput "5. Complete GCP Setup:" "Yellow"
        Write-ColoredOutput "   • Create Document AI processor" "White"
        Write-ColoredOutput "   • Get Google Generative AI API key" "White"
        Write-ColoredOutput "   • Update .env file with your values" "White"
        Write-Host ""
    }
    
    Write-Status "Happy coding! 🚀" "Success"
}

function Save-LogFile {
    try {
        $Global:LogEntries | Out-File -FilePath $LogFile -Encoding utf8
        Write-Status "Setup log saved to: $LogFile" "Info"
    } catch {
        Write-Status "Failed to save log file: $($_.Exception.Message)" "Warning"
    }
}

#endregion

#region Main Execution

function Main {
    # Script header
    Clear-Host
    Write-Host "=============================================================" -ForegroundColor Magenta
    Write-Host "      GenAI-Exchange (LegalEase AI) Setup Script" -ForegroundColor Magenta
    Write-Host "=============================================================" -ForegroundColor Magenta
    Write-Host ""
    
    Write-ColoredOutput "This script will set up your complete development environment for:" "White"
    Write-ColoredOutput "• Frontend: Next.js 15 with React 19, TypeScript, TailwindCSS" "Cyan"
    Write-ColoredOutput "• Backend: Python 3.12, FastAPI, Poetry" "Cyan"
    Write-ColoredOutput "• GCP Services: Document AI, Vertex AI, Firestore, and more" "Cyan"
    Write-Host ""
    
    if ($SkipGCP) {
        Write-Status "GCP setup will be skipped" "Info"
    }
    
    $confirmation = Read-Host "Continue with setup? (Y/n)"
    if ($confirmation -eq 'n' -or $confirmation -eq 'N') {
        Write-Status "Setup cancelled by user" "Info"
        exit 0
    }
    
    $startTime = Get-Date
    Write-Status "Setup started at: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))" "Info"
    Write-Host ""
    
    try {
        # Execute phases
        $phase1Success = Initialize-Prerequisites
        $phase2Success = $phase1Success -and (Initialize-ProjectSetup)
        $phase3Success = $phase2Success -and (Initialize-GCPSetup)
        $phase4Success = $phase3Success -and (Test-ProjectSetup)
        
        Write-Host ""
        Write-Status "=== Setup Summary ===" "Highlight"
        
        if ($phase4Success) {
            $endTime = Get-Date
            $duration = $endTime - $startTime
            Write-Status "✓ Setup completed successfully in $($duration.TotalMinutes.ToString('F1')) minutes!" "Success"
            Show-NextSteps
        } else {
            Write-Status "✗ Setup completed with some issues. Please review the errors above." "Warning"
            Write-Status "You may need to complete some steps manually." "Info"
        }
        
    } catch {
        Write-Status "Setup failed with error: $($_.Exception.Message)" "Error"
        Write-Status "Please check the log file for details: $LogFile" "Info"
    } finally {
        Save-LogFile
    }
}

# Execute main function
if ($MyInvocation.InvocationName -ne '.') {
    Main
}

#endregion