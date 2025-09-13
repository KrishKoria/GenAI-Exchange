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

function Test-CorporateEnvironment {
    Write-Status "Detecting corporate environment..." "Info"
    
    $indicators = @()
    
    # Check for proxy settings
    $proxySettings = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -ErrorAction SilentlyContinue
    if ($proxySettings.ProxyEnable -eq 1) {
        $indicators += "HTTP Proxy detected: $($proxySettings.ProxyServer)"
    }
    
    # Check for corporate certificate authorities
    $corporateCAs = Get-ChildItem -Path "Cert:\LocalMachine\Root" | Where-Object { 
        $_.Subject -notlike "*Microsoft*" -and 
        $_.Subject -notlike "*VeriSign*" -and 
        $_.Subject -notlike "*DigiCert*" -and
        $_.Subject -notlike "*GlobalSign*" -and
        $_.Subject -notlike "*GeoTrust*" -and
        $_.Issuer -eq $_.Subject
    }
    
    if ($corporateCAs.Count -gt 0) {
        $indicators += "Corporate certificate authorities detected: $($corporateCAs.Count)"
    }
    
    # Check for domain environment
    try {
        $domain = (Get-WmiObject -Class Win32_ComputerSystem).Domain
        if ($domain -ne "WORKGROUP") {
            $indicators += "Domain environment: $domain"
        }
    } catch {
        # Ignore errors
    }
    
    if ($indicators.Count -gt 0) {
        Write-Status "Corporate environment detected:" "Warning"
        foreach ($indicator in $indicators) {
            Write-Status "  - $indicator" "Info"
        }
        return $true
    } else {
        Write-Status "No corporate environment indicators found" "Success"
        return $false
    }
}

function Set-SSLSecuritySettings {
    param(
        [switch]$Disable,
        [switch]$Restore
    )
    
    if ($Restore) {
        Write-Status "Restoring SSL security settings..." "Info"
        # Restore default SSL protocols
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::SystemDefault
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null
        return
    }
    
    if ($Disable) {
        Write-Status "Temporarily disabling SSL certificate validation..." "Warning"
        # Allow all SSL protocols
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls11 -bor [System.Net.SecurityProtocolType]::Tls
        # Disable certificate validation (ONLY for this session)
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    } else {
        Write-Status "Configuring secure SSL settings..." "Info"
        # Use TLS 1.2 and above
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    }
}

function Invoke-WebRequestWithFallback {
    param(
        [string]$Uri,
        [string]$OutFile = $null,
        [int]$MaxRetries = 3
    )
    
    $attempt = 0
    $lastError = $null
    
    while ($attempt -lt $MaxRetries) {
        $attempt++
        Write-Status "Attempting download from $Uri (attempt $attempt/$MaxRetries)..." "Info"
        
        try {
            if ($OutFile) {
                Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
            } else {
                return Invoke-WebRequest -Uri $Uri -UseBasicParsing
            }
            Write-Status "Download successful" "Success"
            return $true
        } catch {
            $lastError = $_.Exception.Message
            Write-Status "Download attempt $attempt failed: $lastError" "Warning"
            
            if ($lastError -like "*SSL*" -or $lastError -like "*certificate*") {
                Write-Status "SSL certificate error detected, trying with relaxed security..." "Warning"
                
                # Try with SSL validation disabled
                Set-SSLSecuritySettings -Disable
                try {
                    if ($OutFile) {
                        Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
                    } else {
                        $result = Invoke-WebRequest -Uri $Uri -UseBasicParsing
                        Set-SSLSecuritySettings -Restore
                        return $result
                    }
                    Write-Status "Download successful with relaxed SSL settings" "Success"
                    Set-SSLSecuritySettings -Restore
                    return $true
                } catch {
                    $lastError = $_.Exception.Message
                    Write-Status "Download failed even with relaxed SSL: $lastError" "Error"
                } finally {
                    Set-SSLSecuritySettings -Restore
                }
            }
            
            if ($attempt -lt $MaxRetries) {
                Write-Status "Waiting 3 seconds before retry..." "Info"
                Start-Sleep -Seconds 3
            }
        }
    }
    
    Write-Status "All download attempts failed. Last error: $lastError" "Error"
    return $false
}

function Set-PipTrustedHosts {
    Write-Status "Configuring pip trusted hosts for corporate environment..." "Info"
    
    $trustedHosts = @(
        "pypi.org",
        "pypi.python.org", 
        "files.pythonhosted.org",
        "download.pytorch.org"
    )
    
    # Create pip config directory if it doesn't exist
    $pipConfigDir = "$env:APPDATA\pip"
    if (-not (Test-Path $pipConfigDir)) {
        New-Item -Path $pipConfigDir -ItemType Directory -Force | Out-Null
    }
    
    $pipConfigFile = Join-Path $pipConfigDir "pip.ini"
    $trustedHostsString = ($trustedHosts -join " ")
    
    $pipConfig = @"
[global]
trusted-host = $($trustedHosts -join "`n               ")
disable-pip-version-check = true
timeout = 60

[install]
trusted-host = $($trustedHosts -join "`n               ")
"@
    
    Set-Content -Path $pipConfigFile -Value $pipConfig -Force
    Write-Status "Pip configuration updated at: $pipConfigFile" "Success"
    
    return $trustedHosts
}

function Install-Chocolatey {
    if ($SkipChocolatey -or (Test-CommandExists "choco")) {
        Write-Status "Chocolatey is already installed" "Success"
        return $true
    }
    
    Write-Status "Installing Chocolatey package manager..." "Info"
    
    # Detect corporate environment
    $isCorporate = Test-CorporateEnvironment
    
    try {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        
        # Method 1: Standard installation
        Write-Status "Attempting standard Chocolatey installation..." "Info"
        try {
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        } catch {
            Write-Status "Standard installation failed: $($_.Exception.Message)" "Warning"
            
            # Method 2: Installation with SSL workarounds for corporate environments
            if ($isCorporate) {
                Write-Status "Attempting Chocolatey installation with SSL workarounds..." "Info"
                
                Set-SSLSecuritySettings -Disable
                try {
                    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
                } finally {
                    Set-SSLSecuritySettings -Restore
                }
            } else {
                throw $_
            }
        }
        
        # Refresh environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        # Wait a moment for the installation to complete
        Start-Sleep -Seconds 3
        
        if (Test-CommandExists "choco") {
            Write-Status "Chocolatey installed successfully" "Success"
            
            # Configure Chocolatey for corporate environment if needed
            if ($isCorporate) {
                Write-Status "Configuring Chocolatey for corporate environment..." "Info"
                try {
                    & choco feature enable -n=allowGlobalConfirmation | Out-Null
                    & choco config set --name=commandExecutionTimeoutSeconds --value=2700 | Out-Null
                    Write-Status "Chocolatey configured for corporate environment" "Success"
                } catch {
                    Write-Status "Failed to configure Chocolatey for corporate environment: $($_.Exception.Message)" "Warning"
                }
            }
            
            return $true
        } else {
            throw "Chocolatey installation verification failed"
        }
    } catch {
        Write-Status "Failed to install Chocolatey: $($_.Exception.Message)" "Error"
        
        # Provide manual installation guidance
        Write-Status "Please install Chocolatey manually:" "Info"
        Write-Status "1. Open PowerShell as Administrator" "Info"
        Write-Status "2. Run: Set-ExecutionPolicy Bypass -Scope Process -Force" "Info"
        
        if ($isCorporate) {
            Write-Status "3. For corporate environments, you may need to:" "Info"
            Write-Status "   - Configure proxy settings in PowerShell" "Info"
            Write-Status "   - Download install.ps1 manually and run it" "Info"
            Write-Status "   - Visit: https://chocolatey.org/install for alternative methods" "Info"
        } else {
            Write-Status "3. Run: iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" "Info"
        }
        
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
    
    Write-Status "Installing Poetry with multiple fallback methods..." "Info"
    
    # Detect corporate environment
    $isCorporate = Test-CorporateEnvironment
    
    # Method 1: Use pip with trusted hosts (recommended for corporate environments)
    if ($isCorporate) {
        Write-Status "Attempting Poetry installation via pip with trusted hosts..." "Info"
        try {
            # Configure pip trusted hosts
            $trustedHosts = Set-PipTrustedHosts
            
            # Build pip install command with trusted hosts
            $trustedHostArgs = ($trustedHosts | ForEach-Object { "--trusted-host $_" }) -join " "
            $pipCommand = "python -m pip install poetry $trustedHostArgs --user --upgrade"
            
            Write-Status "Running: $pipCommand" "Info"
            Invoke-Expression $pipCommand
            
            if ($LASTEXITCODE -eq 0) {
                # Add Poetry to PATH
                $poetryPath = "$env:USERPROFILE\.local\bin"
                $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
                if ($currentPath -notlike "*$poetryPath*") {
                    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$poetryPath", "User")
                    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                }
                
                Start-Sleep -Seconds 3
                if (Test-CommandExists "poetry") {
                    $installedVersion = & poetry --version 2>$null
                    Write-Status "Poetry installed successfully via pip: $installedVersion" "Success"
                    return $true
                }
            }
        } catch {
            Write-Status "Pip installation method failed: $($_.Exception.Message)" "Warning"
        }
    }
    
    # Method 2: Use Chocolatey
    Write-Status "Attempting Poetry installation via Chocolatey..." "Info"
    try {
        if (Test-CommandExists "choco") {
            & choco install poetry -y --force
            
            if ($LASTEXITCODE -eq 0) {
                # Refresh environment
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                Start-Sleep -Seconds 3
                
                if (Test-CommandExists "poetry") {
                    $installedVersion = & poetry --version 2>$null
                    Write-Status "Poetry installed successfully via Chocolatey: $installedVersion" "Success"
                    return $true
                }
            }
        } else {
            Write-Status "Chocolatey not available, skipping this method" "Warning"
        }
    } catch {
        Write-Status "Chocolatey installation method failed: $($_.Exception.Message)" "Warning"
    }
    
    # Method 3: Official installer with SSL fallback
    Write-Status "Attempting Poetry installation via official installer..." "Info"
    try {
        # Try official installer with our enhanced web request function
        $installerContent = Invoke-WebRequestWithFallback -Uri "https://install.python-poetry.org"
        
        if ($installerContent) {
            $installerContent.Content | python -
            
            # Add Poetry to PATH
            $poetryPath = "$env:USERPROFILE\.local\bin"
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
            if ($currentPath -notlike "*$poetryPath*") {
                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$poetryPath", "User")
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            }
            
            Start-Sleep -Seconds 5
            
            if (Test-CommandExists "poetry") {
                $installedVersion = & poetry --version 2>$null
                Write-Status "Poetry installed successfully via official installer: $installedVersion" "Success"
                return $true
            }
        }
    } catch {
        Write-Status "Official installer method failed: $($_.Exception.Message)" "Warning"
    }
    
    # Method 4: Manual pip installation without certificate verification (last resort)
    Write-Status "Attempting Poetry installation with relaxed SSL settings (last resort)..." "Warning"
    try {
        Set-SSLSecuritySettings -Disable
        
        $pipCommand = "python -m pip install poetry --user --upgrade --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org"
        Write-Status "Running: $pipCommand" "Info"
        Invoke-Expression $pipCommand
        
        Set-SSLSecuritySettings -Restore
        
        if ($LASTEXITCODE -eq 0) {
            # Add Poetry to PATH
            $poetryPath = "$env:USERPROFILE\.local\bin"
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
            if ($currentPath -notlike "*$poetryPath*") {
                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$poetryPath", "User")
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            }
            
            Start-Sleep -Seconds 3
            if (Test-CommandExists "poetry") {
                $installedVersion = & poetry --version 2>$null
                Write-Status "Poetry installed successfully with relaxed SSL: $installedVersion" "Success"
                return $true
            }
        }
    } catch {
        Write-Status "Final installation method failed: $($_.Exception.Message)" "Warning"
    } finally {
        Set-SSLSecuritySettings -Restore
    }
    
    # All methods failed
    Write-Status "All Poetry installation methods failed!" "Error"
    Write-Status "Please try installing Poetry manually:" "Info"
    Write-Status "1. Open PowerShell as Administrator" "Info"
    Write-Status "2. Run: python -m pip install poetry --user --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org" "Info"
    Write-Status "3. Add %USERPROFILE%\.local\bin to your PATH environment variable" "Info"
    
    return $false
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
    
    Write-Status "Installing Google Cloud CLI with multiple fallback methods..." "Info"
    
    # Detect corporate environment
    $isCorporate = Test-CorporateEnvironment
    
    # Method 1: Chocolatey with SSL workarounds
    Write-Status "Attempting Google Cloud CLI installation via Chocolatey..." "Info"
    try {
        if (Test-CommandExists "choco") {
            # Configure Chocolatey to ignore SSL issues if in corporate environment
            if ($isCorporate) {
                Write-Status "Configuring Chocolatey for corporate environment..." "Info"
                & choco config set --name='"'commandExecutionTimeoutSeconds'"' --value='"'2700'"' | Out-Null
                & choco feature enable -n='"'allowGlobalConfirmation'"' | Out-Null
            }
            
            & choco install gcloudsdk -y --force --ignore-checksums
            
            if ($LASTEXITCODE -eq 0) {
                # Refresh environment
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                Start-Sleep -Seconds 10
                
                if (Test-CommandExists "gcloud") {
                    $installedVersion = & gcloud version --quiet 2>$null | Select-String "Google Cloud SDK"
                    Write-Status "Google Cloud CLI installed successfully via Chocolatey: $installedVersion" "Success"
                    return $true
                }
            }
        } else {
            Write-Status "Chocolatey not available, skipping this method" "Warning"
        }
    } catch {
        Write-Status "Chocolatey installation method failed: $($_.Exception.Message)" "Warning"
    }
    
    # Method 2: Windows Package Manager (winget)
    Write-Status "Attempting Google Cloud CLI installation via winget..." "Info"
    try {
        if (Test-CommandExists "winget") {
            & winget install -e --id Google.CloudSDK --silent --accept-package-agreements --accept-source-agreements
            
            if ($LASTEXITCODE -eq 0) {
                # Refresh environment
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                Start-Sleep -Seconds 10
                
                if (Test-CommandExists "gcloud") {
                    $installedVersion = & gcloud version --quiet 2>$null | Select-String "Google Cloud SDK"
                    Write-Status "Google Cloud CLI installed successfully via winget: $installedVersion" "Success"
                    return $true
                }
            }
        } else {
            Write-Status "Windows Package Manager (winget) not available, skipping this method" "Warning"
        }
    } catch {
        Write-Status "Winget installation method failed: $($_.Exception.Message)" "Warning"
    }
    
    # Method 3: Direct download from Google with SSL fallback
    Write-Status "Attempting Google Cloud CLI installation via direct download..." "Info"
    try {
        $gcloudDownloadUrl = "https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe"
        $installerPath = Join-Path $env:TEMP "GoogleCloudSDKInstaller.exe"
        
        # Try to download the installer using our enhanced web request function
        if (Invoke-WebRequestWithFallback -Uri $gcloudDownloadUrl -OutFile $installerPath) {
            Write-Status "Google Cloud SDK installer downloaded successfully" "Success"
            
            # Run the installer silently
            Write-Status "Running Google Cloud SDK installer..." "Info"
            $process = Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait -PassThru
            
            if ($process.ExitCode -eq 0) {
                # Refresh environment
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                Start-Sleep -Seconds 15
                
                if (Test-CommandExists "gcloud") {
                    $installedVersion = & gcloud version --quiet 2>$null | Select-String "Google Cloud SDK"
                    Write-Status "Google Cloud CLI installed successfully via direct download: $installedVersion" "Success"
                    
                    # Clean up installer
                    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                    return $true
                } else {
                    Write-Status "Installation completed but gcloud command not found in PATH" "Warning"
                    
                    # Try to find gcloud in common installation paths
                    $commonPaths = @(
                        "$env:USERPROFILE\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin",
                        "$env:ProgramFiles\Google\Cloud SDK\google-cloud-sdk\bin",
                        "${env:ProgramFiles(x86)}\Google\Cloud SDK\google-cloud-sdk\bin"
                    )
                    
                    foreach ($path in $commonPaths) {
                        if (Test-Path "$path\gcloud.cmd") {
                            Write-Status "Found gcloud at: $path" "Success"
                            # Add to PATH
                            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
                            if ($currentPath -notlike "*$path*") {
                                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$path", "User")
                                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                            }
                            
                            if (Test-CommandExists "gcloud") {
                                $installedVersion = & gcloud version --quiet 2>$null | Select-String "Google Cloud SDK"
                                Write-Status "Google Cloud CLI configured successfully: $installedVersion" "Success"
                                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
                                return $true
                            }
                            break
                        }
                    }
                }
            } else {
                Write-Status "Google Cloud SDK installer failed with exit code: $($process.ExitCode)" "Error"
            }
            
            # Clean up installer
            Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Status "Direct download method failed: $($_.Exception.Message)" "Warning"
    }
    
    # Method 4: Manual installation guidance
    Write-Status "All automated installation methods failed!" "Error"
    Write-Status "Please install Google Cloud CLI manually:" "Info"
    Write-Status "1. Visit: https://cloud.google.com/sdk/docs/install" "Info"
    Write-Status "2. Download the Windows x86_64 installer" "Info"
    Write-Status "3. Run the installer and follow the setup wizard" "Info"
    Write-Status "4. After installation, run 'gcloud init' to configure" "Info"
    
    if ($isCorporate) {
        Write-Status "Corporate environment detected - additional steps:" "Warning"
        Write-Status "1. You may need to configure proxy settings for gcloud" "Info"
        Write-Status "2. Run: gcloud config set proxy/type http" "Info"
        Write-Status "3. Run: gcloud config set proxy/address [your-proxy-host]" "Info"
        Write-Status "4. Run: gcloud config set proxy/port [your-proxy-port]" "Info"
    }
    
    return $false
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
    
    # Early environment detection for better user guidance
    Write-Status "Performing environment checks..." "Info"
    $isCorporate = Test-CorporateEnvironment
    
    if ($isCorporate) {
        Write-Host ""
        Write-Status "Corporate environment detected!" "Warning"
        Write-ColoredOutput "This script includes special handling for corporate networks:" "Yellow"
        Write-ColoredOutput "• SSL certificate bypass for downloads" "White"
        Write-ColoredOutput "• Trusted host configuration for pip/Poetry" "White"
        Write-ColoredOutput "• Multiple fallback installation methods" "White"
        Write-ColoredOutput "• Proxy-aware configurations" "White"
        Write-Host ""
    }
    
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
        # Execute phases with enhanced error tracking
        Write-Status "Starting Phase 1: Prerequisites Installation..." "Info"
        $phase1Success = Initialize-Prerequisites
        
        if ($phase1Success) {
            Write-Status "Starting Phase 2: Project Setup..." "Info"
            $phase2Success = Initialize-ProjectSetup
        } else {
            Write-Status "Phase 1 failed, skipping subsequent phases" "Error"
            $phase2Success = $false
        }
        
        if ($phase2Success) {
            Write-Status "Starting Phase 3: GCP Configuration..." "Info"
            $phase3Success = Initialize-GCPSetup
        } else {
            Write-Status "Phase 2 failed, skipping subsequent phases" "Error"
            $phase3Success = $false
        }
        
        if ($phase3Success) {
            Write-Status "Starting Phase 4: Testing and Verification..." "Info"
            $phase4Success = Test-ProjectSetup
        } else {
            Write-Status "Phase 3 failed, skipping final verification" "Error"
            $phase4Success = $false
        }
        
        Write-Host ""
        Write-Status "=== Setup Summary ===" "Highlight"
        
        if ($phase4Success) {
            $endTime = Get-Date
            $duration = $endTime - $startTime
            Write-Status "✓ Setup completed successfully in $($duration.TotalMinutes.ToString('F1')) minutes!" "Success"
            Show-NextSteps
        } else {
            $endTime = Get-Date
            $duration = $endTime - $startTime
            Write-Status "✗ Setup completed with some issues after $($duration.TotalMinutes.ToString('F1')) minutes." "Warning"
            Write-Status "Please review the errors above and see guidance below." "Info"
            
            # Provide specific guidance based on what failed
            Write-Host ""
            Write-Status "Troubleshooting guidance:" "Highlight"
            
            if (-not $phase1Success) {
                Write-Status "Prerequisites installation failed:" "Error"
                Write-Status "1. Check if you have administrator privileges" "Info"
                Write-Status "2. Verify internet connectivity" "Info"
                if ($isCorporate) {
                    Write-Status "3. Corporate environment detected - contact IT if downloads are blocked" "Info"
                    Write-Status "4. Consider manual installation of failed tools" "Info"
                }
            }
            
            if ($phase1Success -and -not $phase2Success) {
                Write-Status "Project setup failed:" "Error"
                Write-Status "1. Ensure you're in the correct project directory" "Info"
                Write-Status "2. Check that package.json and pyproject.toml exist" "Info"
                Write-Status "3. Verify Poetry installation is working: poetry --version" "Info"
            }
            
            if ($phase2Success -and -not $phase3Success) {
                Write-Status "GCP setup failed:" "Error"
                Write-Status "1. Check Google Cloud CLI installation: gcloud version" "Info"
                Write-Status "2. Verify you have a Google Cloud account" "Info"
                Write-Status "3. Run 'gcloud init' manually to configure authentication" "Info"
            }
            
            Write-Host ""
            Write-Status "For manual recovery steps, see the log file: $LogFile" "Info"
        }
        
    } catch {
        $endTime = Get-Date
        $duration = $endTime - $startTime
        Write-Status "Setup failed with critical error after $($duration.TotalMinutes.ToString('F1')) minutes:" "Error"
        Write-Status "$($_.Exception.Message)" "Error"
        Write-Host ""
        
        # Provide context-specific error guidance
        if ($isCorporate) {
            Write-Status "Corporate environment troubleshooting:" "Warning"
            Write-Status "1. SSL certificate errors may indicate corporate firewall interference" "Info"
            Write-Status "2. Contact your IT department for:" "Info"
            Write-Status "   - Proxy server settings" "Info"
            Write-Status "   - Certificate authority configuration" "Info"
            Write-Status "   - Whitelisting for development tool downloads" "Info"
        }
        
        Write-Status "General troubleshooting:" "Info"
        Write-Status "1. Run PowerShell as Administrator" "Info"
        Write-Status "2. Check internet connectivity" "Info"
        Write-Status "3. Temporarily disable antivirus if blocking downloads" "Info"
        Write-Status "4. Check the detailed log file: $LogFile" "Info"
        
    } finally {
        Write-Host ""
        Write-Status "Saving detailed log to: $LogFile" "Info"
        Save-LogFile
        
        if ($isCorporate) {
            Write-Host ""
            Write-Status "Corporate Environment Notes:" "Highlight"
            Write-Status "• This script attempted to work around common corporate restrictions" "Info"
            Write-Status "• If manual intervention is needed, the log contains specific commands to run" "Info"
            Write-Status "• Share the log file with your IT team if additional support is needed" "Info"
        }
    }
}

# Execute main function
if ($MyInvocation.InvocationName -ne '.') {
    Main
}

#endregion