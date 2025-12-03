# [CmdletBinding()]
# param(
#     [Parameter(Mandatory=$true)]
#     [string]$SpecFile,

#     [Parameter(Mandatory=$true)]
#     [string]$RulesetFile
# )

# $ErrorActionPreference = 'Stop'

# # --- Helpers ---
# $BT = [char]96
# $NL = [Environment]::NewLine

# # ---------------------------------------------------------------------
# # 1. SETUP & INSTALL
# # ---------------------------------------------------------------------
# Write-Host "Checking if Spectral is installed..."
# try {
#     # redirect stderr to null to avoid noisy error if not found
#     $specVer = & spectral --version 2>$null
#     if ($LASTEXITCODE -eq 0) {
#         Write-Host "Spectral present: $specVer"
#     } else {
#         throw "Not found"
#     }
# } catch {
#     Write-Host "Spectral not found - installing @stoplight/spectral-cli..."
#     npm install -g @stoplight/spectral-cli
#     $specVer = & spectral --version
#     Write-Host "Spectral installed: $specVer"
# }

# # Check Spec File
# if (-not (Test-Path $SpecFile)) {
#     Write-Host "ERROR: Spec file not found at: $SpecFile. Skipping."
#     Exit 0
# }

# Write-Host "--- Start of Spec File Content ($SpecFile) ---"
# Get-Content $SpecFile | Select-Object -First 20 | Write-Host 
# Write-Host "... (file content truncated in logs) ..."
# Write-Host "--- End of Spec File Content ---"

# # ---------------------------------------------------------------------
# # 2. RUN SPECTRAL (Pure PowerShell - Cross Platform)
# # ---------------------------------------------------------------------
# $resultsFile = "$($env:BUILD_ARTIFACTSTAGINGDIRECTORY)/spectral_results.json"
# Write-Host "Running Spectral on '$SpecFile' with ruleset '$RulesetFile'..."

# # We use the '&' operator to run the command natively.
# # We pipe the output directly to a file using UTF8 encoding.
# # Stderr (tool errors) will still print to the ADO Console Log automatically.
# try {
#     & spectral lint "$SpecFile" --ruleset "$RulesetFile" --format json | Set-Content -Path $resultsFile -Encoding UTF8
# } catch {
#     Write-Host "Warning: Spectral execution threw an exception, but might have still produced output: $($_.Exception.Message)"
# }

# if (-not (Test-Path $resultsFile)) {
#     Write-Host "No results file produced at: $resultsFile"
#     Exit 0
# }

# $jsonText = Get-Content $resultsFile -Raw
# if ([string]::IsNullOrWhiteSpace($jsonText)) {
#     Write-Host "Results file is empty. Assuming no findings."
#     Exit 0
# }

# # ---------------------------------------------------------------------
# # 3. PARSE JSON (Handling Root-Level Array)
# # ---------------------------------------------------------------------
# $findings = @()
# $trimmed = $jsonText.Trim()

# # Check for "No results" message (sometimes Spectral outputs text even with --format json)
# if ($trimmed -match "No results with a severity of") {
#     Write-Host "SUCCESS: Spectral indicated no error-level findings."
# }
# elseif ($trimmed.StartsWith('[') -or $trimmed.StartsWith('{')) {
#     try {
#         $parsed = $jsonText | ConvertFrom-Json
#     } catch {
#         Write-Host "ERROR: Failed to parse Spectral JSON: $($_.Exception.Message)"
#         Write-Host "Raw output snippet:"
#         Write-Host $trimmed.Substring(0, [Math]::Min($trimmed.Length, 500))
#         Exit 1
#     }

#     # Handle the structure: Array [] vs Object { results: [] }
#     if ($parsed -is [System.Array]) {
#         $findings = $parsed
#     } elseif ($parsed.PSObject.Properties.Name -contains 'results') {
#         $findings = $parsed.results
#     } else {
#         $findings = @($parsed)
#     }
# }
# else {
#     Write-Host "WARNING: Spectral returned unexpected text. Treating as no findings."
#     Write-Host $jsonText
# }

# Write-Host "Total Findings: $($findings.Count)"

# # ---------------------------------------------------------------------
# # 4. GENERATE MARKDOWN SUMMARY (The "Beautiful" Table)
# # ---------------------------------------------------------------------
# if ($findings.Count -gt 0) {
#     Write-Host "Generating Markdown Summary..."
    
#     $mdLines = @()
#     $mdLines += "# 🔍 Spectral API Governance Report"
#     $mdLines += ""
#     $mdLines += "| Status | Rule Code | Location | Line | Message |"
#     $mdLines += "| :---: | :--- | :--- | :---: | :--- |"

#     $errCount = 0
#     $warnCount = 0

#     foreach ($f in $findings) {
#         # Map Severity: 0=Error, 1=Warn, 2=Info, 3=Hint
#         $icon = "ℹ️"
#         if ($f.severity -eq 0) { $icon = "🛑"; $errCount++ }
#         elseif ($f.severity -eq 1) { $icon = "⚠️"; $warnCount++ }
#         elseif ($f.severity -eq 3) { $icon = "💡" }

#         # Format Path (Breadcrumbs)
#         $crumbPath = ""
#         if ($f.path -is [System.Array]) {
#             $crumbPath = $f.path -join " > "
#         } else {
#             $crumbPath = [string]$f.path
#         }
        
#         # Format Line Number (Human readable 1-based)
#         $lineNum = ""
#         if ($f.range -and $f.range.start) {
#             $lineNum = [int]$f.range.start.line + 1
#         }

#         # Sanitize Message for Markdown Table (pipe | breaks tables)
#         $safeMsg = $f.message -replace "\|", "&#124;" -replace "`r`n", " " -replace "`n", " "

#         # Add Row
#         $mdLines += "| $icon | **$($f.code)** | ``$crumbPath`` | $lineNum | $safeMsg |"
#     }

#     $mdLines += ""
#     $mdLines += "---"
#     $mdLines += "**Total:** $($findings.Count) | **Errors:** $errCount 🛑 | **Warnings:** $warnCount ⚠️"
    
#     # Save and Upload to ADO Summary Tab
#     $mdFileName = "spectral_summary.md"
#     $mdFilePath = Join-Path $env:BUILD_ARTIFACTSTAGINGDIRECTORY $mdFileName
#     $mdLines -join $NL | Set-Content -Path $mdFilePath -Encoding utf8
    
#     Write-Host "##vso[task.uploadsummary]$mdFilePath"
# }

# # ---------------------------------------------------------------------
# # 5. POST COMMENTS TO PR
# # ---------------------------------------------------------------------
# if (-not $findings -or $findings.Count -eq 0) {
#     Write-Host "No findings. Exiting successfully."
#     Exit 0
# }

# # Setup Auth
# $token = $env:SYSTEM_ACCESSTOKEN
# $useOauth = $true
# if (-not $token) {
#     $token = $env:AZURE_DEVOPS_EXT_PAT
#     $useOauth = $false
# }
# $canPost = [bool]$token

# $orgUrl = $env:SYSTEM_TEAMFOUNDATIONCOLLECTIONURI.TrimEnd('/')
# $project = $env:SYSTEM_TEAMPROJECT
# $repoId = $env:BUILD_REPOSITORY_ID
# $prId = $env:SYSTEM_PULLREQUEST_PULLREQUESTID
# if (-not $prId) { $prId = $env:SYSTEM_PULLREQUEST_PULLREQUESTNUMBER }

# if ($canPost -and -not $prId) {
#     Write-Host "No PR ID found. Will only preview comments."
#     $canPost = $false
# }

# $existingThreads = @()
# if ($canPost) {
#     Write-Host "Fetching existing threads to avoid duplicates..."
#     $threadsUrl = "$orgUrl/$project/_apis/git/repositories/$repoId/pullRequests/$prId/threads?api-version=7.1"
#     try {
#         if ($useOauth) { $hdr = @{ Authorization = "Bearer $token" } } 
#         else { $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$token")); $hdr = @{ Authorization = "Basic $b64" } }
        
#         $resp = Invoke-RestMethod -Uri $threadsUrl -Method Get -Headers $hdr
#         if ($resp.value) { $existingThreads = $resp.value }
#     } catch {
#         Write-Host "Warning: Could not fetch threads: $($_.Exception.Message)"
#     }
# }

# function AlreadyPosted($code, $pathDisplay) {
#     foreach ($t in $existingThreads) {
#         foreach ($c in $t.comments) {
#             if ($c.content -and $c.content.Contains($code) -and $c.content.Contains($pathDisplay)) { return $true }
#         }
#     }
#     return $false
# }

# $hasErrors = $false

# foreach ($f in $findings) {
#     # Extract Data for Commenting
#     $code = $f.code
#     $msg = $f.message
#     $pathDisplay = if ($f.path -is [System.Array]) { $f.path -join "/" } else { $f.path }
    
#     # 0=Error, 1=Warn
#     $sevNum = 2
#     if ($f.severity -ne $null) { $sevNum = [int]$f.severity }
    
#     if ($sevNum -eq 0) { $hasErrors = $true }

#     # ADO UI Log Issue (The "Red Text" in Console Logs)
#     $adoType = if ($sevNum -eq 0) { 'error' } else { 'warning' }
    
#     # Calc Line for ADO
#     $line = 1; $col = 1
#     if ($f.range -and $f.range.start) {
#         $line = [int]$f.range.start.line + 1
#         if ($f.range.start.character) { $col = [int]$f.range.start.character + 1 }
#     }

#     Write-Host "##vso[task.logissue type=$adoType;sourcepath=$pathDisplay;linenumber=$line;columnnumber=$col;code=$code] [$code] $msg"

#     # Skip posting comment if already posted
#     if (AlreadyPosted $code $pathDisplay) { continue }

#     # Post Comment
#     $sevLabel = switch ($sevNum) { 0 {'Error'} 1 {'Warning'} default {'Info'} }
#     $commentContent = "**Spectral** [$sevLabel] $BT$code$BT -- $msg$NL> Path: $BT$pathDisplay$BT (Line $line)"

#     $body = @{ comments = @(@{ parentCommentId = 0; content = $commentContent; commentType = 1 }); status = 1 }
    
#     if ($canPost) {
#         $postUrl = "$orgUrl/$project/_apis/git/repositories/$repoId/pullRequests/$prId/threads?api-version=7.1"
#         try {
#             Invoke-RestMethod -Uri $postUrl -Method Post -Headers $hdr -Body ($body | ConvertTo-Json -Depth 5) -ContentType "application/json" | Out-Null
#             Write-Host "Posted comment for $code"
#         } catch {
#              Write-Host "Failed to post comment: $($_.Exception.Message)"
#         }
#     }
# }

# # ---------------------------------------------------------------------
# # 6. FINAL STATUS (Soft Mode)
# # ---------------------------------------------------------------------
# if ($hasErrors) {
#     Write-Warning "Spectral found errors (Severity 0). Pipeline is in Soft Mode, so we are exiting with Success."
#     # Use Exit 0 to pass the build despite findings
#     Exit 0
# } else {
#     Write-Host "No errors found."
#     Exit 0
# }



























# [CmdletBinding()]
# param(
#     [Parameter(Mandatory=$true)]
#     [string]$SpecFile,

#     [Parameter(Mandatory=$true)]
#     [string]$RulesetFile,

#     # Used for file naming to prevent overwrites in the Build Summary tab
#     [Parameter(Mandatory=$true)]
#     [string]$TaskID,

#     # The Title shown in the PR Comment Header
#     [Parameter(Mandatory=$true)]
#     [string]$TaskTitle
# )

# $ErrorActionPreference = 'Stop'
# $BT = [char]96
# $NL = [Environment]::NewLine

# # ---------------------------------------------------------------------
# # 1. SETUP & CHECK INSTALL
# # ---------------------------------------------------------------------
# Write-Host "Checking for Spectral..."
# try {
#     $specVer = & spectral --version 2>$null
#     if ($LASTEXITCODE -eq 0) { Write-Host "Spectral present: $specVer" } else { throw "Not found" }
# } catch {
#     Write-Host "Installing @stoplight/spectral-cli..."
#     npm install -g @stoplight/spectral-cli
# }

# if (-not (Test-Path $SpecFile)) {
#     Write-Host "ERROR: Spec file not found at: $SpecFile"
#     Exit 0
# }

# # ---------------------------------------------------------------------
# # 2. RUN SPECTRAL (Cross-Platform)
# # ---------------------------------------------------------------------
# $resultsFile = "$($env:BUILD_ARTIFACTSTAGINGDIRECTORY)/spectral_${TaskID}_results.json"
# Write-Host "Running Spectral..."

# try {
#     # Run Spectral -> Pipe to File (Cross-platform safe)
#     & spectral lint "$SpecFile" --ruleset "$RulesetFile" --format json 2>$null | Out-File -FilePath $resultsFile -Encoding utf8
# } catch {
#     Write-Host "Execution Warning: $($_.Exception.Message)"
# }

# # ---------------------------------------------------------------------
# # 3. PARSE JSON
# # ---------------------------------------------------------------------
# $findings = @()
# if (Test-Path $resultsFile) {
#     $jsonText = Get-Content $resultsFile -Raw
#     if (-not [string]::IsNullOrWhiteSpace($jsonText)) {
#         $trimmed = $jsonText.Trim()
#         if ($trimmed.StartsWith('[') -or $trimmed.StartsWith('{')) {
#             try {
#                 $parsed = $jsonText | ConvertFrom-Json
#                 if ($parsed -is [System.Array]) { $findings = $parsed } 
#                 elseif ($parsed.PSObject.Properties.Name -contains 'results') { $findings = $parsed.results }
#                 else { $findings = @($parsed) }
#             } catch { Write-Host "Error parsing JSON." }
#         }
#     }
# }

# # Sort: Errors (0) first, then Warnings (1)
# $findings = $findings | Sort-Object severity
# $errCount = ($findings | Where-Object { $_.severity -eq 0 }).Count
# $warnCount = ($findings | Where-Object { $_.severity -eq 1 }).Count

# # ---------------------------------------------------------------------
# # 4. LOG ISSUES TO CONSOLE (Red/Yellow Text in Logs)
# # ---------------------------------------------------------------------
# foreach ($f in $findings) {
#     $type = if ($f.severity -eq 0) { 'error' } else { 'warning' }
#     $pathDisp = if ($f.path -is [System.Array]) { $f.path -join "/" } else { $f.path }
#     $line = if ($f.range -and $f.range.start) { [int]$f.range.start.line + 1 } else { 1 }
    
#     # ADO Logging Command (Populates "Issues" tab)
#     Write-Host "##vso[task.logissue type=$type;sourcepath=$pathDisp;linenumber=$line;code=$($f.code)] $($f.message)"
# }

# # ---------------------------------------------------------------------
# # 5. GENERATE MARKDOWN CONTENT
# # ---------------------------------------------------------------------
# $timestamp = Get-Date -Format "HH:mm UTC"

# # No "Section" tags needed anymore, just the content
# $md = "### $TaskTitle$NL"

# if ($findings.Count -eq 0) {
#     $md += "✅ **Passed** (No issues found as of $timestamp)$NL"
# } else {
#     $icon = if ($errCount -gt 0) { "🛑" } else { "⚠️" }
#     $md += "$icon **Issues Found:** $errCount Errors, $warnCount Warnings (Run: $timestamp)$NL$NL"
    
#     $md += "| Status | Rule | Location | Line | Details |$NL"
#     $md += "| :---: | :--- | :--- | :---: | :--- |$NL"

#     foreach ($f in $findings) {
#         $fIcon = if ($f.severity -eq 0) { "🛑" } elseif ($f.severity -eq 1) { "⚠️" } else { "ℹ️" }
#         $crumb = if ($f.path -is [System.Array]) { $f.path -join " > " } else { [string]$f.path }
#         $ln = if ($f.range) { [int]$f.range.start.line + 1 } else { "-" }
#         $msg = $f.message -replace "\|", "&#124;" -replace "`r`n", " " -replace "`n", " "
        
#         $md += "| $fIcon | **$($f.code)** | ``$crumb`` | $ln | $msg |$NL"
#     }
# }

# # ---------------------------------------------------------------------
# # 6. POST NEW PR COMMENT (Fire and Forget)
# # ---------------------------------------------------------------------
# $token = $env:SYSTEM_ACCESSTOKEN
# if (-not $token) { $token = $env:AZURE_DEVOPS_EXT_PAT }
# $prId = $env:SYSTEM_PULLREQUEST_PULLREQUESTID
# if (-not $prId) { $prId = $env:SYSTEM_PULLREQUEST_PULLREQUESTNUMBER }

# if ($prId -and $token) {
#     Write-Host "Posting new comment to PR #$prId..."
#     $orgUrl = $env:SYSTEM_TEAMFOUNDATIONCOLLECTIONURI.TrimEnd('/')
#     $project = $env:SYSTEM_TEAMPROJECT
#     $repoId = $env:BUILD_REPOSITORY_ID
    
#     $threadsUrl = "$orgUrl/$project/_apis/git/repositories/$repoId/pullRequests/$prId/threads?api-version=7.1"
#     $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$token"))
#     $headers = @{ Authorization = "Basic $b64" }
    
#     # Create the Body Object
#     $body = @{ 
#         comments = @( @{ content = $md; commentType = 1 } )
#         status = 1 
#     } | ConvertTo-Json -Depth 5

#     try {
#         # Simple POST - creates a new thread every time
#         Invoke-RestMethod -Uri $threadsUrl -Method Post -Headers $headers -Body $body -ContentType "application/json" | Out-Null
#         Write-Host "✅ Comment posted successfully."
#     } catch {
#         Write-Host "❌ Failed to post comment: $($_.Exception.Message)"
#         Write-Host "NOTE: Ensure 'Contribute to pull requests' is ALLOWED for the Build Service User."
#     }
# } else {
#     Write-Host "Skipping comment (Not a PR or no token)."
# }

# # ---------------------------------------------------------------------
# # 7. UPLOAD SUMMARY (For Build Tab)
# # ---------------------------------------------------------------------
# # We save and upload the markdown so it also appears in the Pipeline Summary tab
# $summaryPath = "$($env:BUILD_ARTIFACTSTAGINGDIRECTORY)/spectral_summary_${TaskID}.md"
# Set-Content -Path $summaryPath -Value $md -Encoding UTF8
# Write-Host "##vso[task.uploadsummary]$summaryPath"

# # ---------------------------------------------------------------------
# # 8. EXIT STATUS
# # ---------------------------------------------------------------------
# if ($errCount -gt 0) {
#     Write-Warning "Spectral found $errCount errors in '$TaskTitle'."
#     # Exit 0 = Soft Mode (Green Build). Change to Exit 1 to Fail.
#     Exit 0 
# } else {
#     Exit 0
# }





[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$SpecFile,

    [Parameter(Mandatory=$true)]
    [string]$RulesetFile,

    # Used for file naming to prevent overwrites in the Build Summary tab
    [Parameter(Mandatory=$false)]
    [string]$TaskID = "General",

    # The Title shown in the PR Comment Header
    [Parameter(Mandatory=$false)]
    [string]$TaskTitle = "API Linting Report"
)

$ErrorActionPreference = 'Stop'
$BT = [char]96
$NL = [Environment]::NewLine

# ---------------------------------------------------------------------
# 1. SETUP & CHECK INSTALL
# ---------------------------------------------------------------------
Write-Host "Checking for Spectral..."
try {
    $specVer = & spectral --version 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "Spectral present: $specVer" } else { throw "Not found" }
} catch {
    Write-Host "Installing @stoplight/spectral-cli..."
    npm install -g @stoplight/spectral-cli
}

if (-not (Test-Path $SpecFile)) {
    Write-Host "ERROR: Spec file not found at: $SpecFile"
    Exit 0
}

# ---------------------------------------------------------------------
# 2. RUN SPECTRAL
# ---------------------------------------------------------------------
# Use RUNNER_TEMP for GitHub Actions, fallback to BUILD_ARTIFACTSTAGINGDIRECTORY for Azure DevOps
$artifactDir = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:BUILD_ARTIFACTSTAGINGDIRECTORY }
$resultsFile = "$artifactDir/spectral_${TaskID}_results.json"
Write-Host "Running Spectral..."

try {
    & spectral lint "$SpecFile" --ruleset "$RulesetFile" --format json 2>$null | Out-File -FilePath $resultsFile -Encoding utf8
} catch {
    Write-Host "Execution Warning: $($_.Exception.Message)"
}

# ---------------------------------------------------------------------
# 3. PARSE JSON
# ---------------------------------------------------------------------
$findings = @()
if (Test-Path $resultsFile) {
    $jsonText = Get-Content $resultsFile -Raw
    if (-not [string]::IsNullOrWhiteSpace($jsonText)) {
        $trimmed = $jsonText.Trim()
        if ($trimmed.StartsWith('[') -or $trimmed.StartsWith('{')) {
            try {
                $parsed = $jsonText | ConvertFrom-Json
                if ($parsed -is [System.Array]) { $findings = $parsed } 
                elseif ($parsed.PSObject.Properties.Name -contains 'results') { $findings = $parsed.results }
                else { $findings = @($parsed) }
            } catch { Write-Host "Error parsing JSON." }
        }
    }
}

$findings = $findings | Sort-Object severity
$errCount = ($findings | Where-Object { $_.severity -eq 0 }).Count
$warnCount = ($findings | Where-Object { $_.severity -eq 1 }).Count

# ---------------------------------------------------------------------
# 4. LOG ISSUES TO CONSOLE
# ---------------------------------------------------------------------
foreach ($f in $findings) {
    $type = if ($f.severity -eq 0) { 'error' } else { 'warning' }
    $pathDisp = if ($f.path -is [System.Array]) { $f.path -join "/" } else { $f.path }
    $line = if ($f.range -and $f.range.start) { [int]$f.range.start.line + 1 } else { 1 }
    
    # GitHub Actions workflow command format
    if ($env:GITHUB_ACTIONS) {
        Write-Host "::$type file=$pathDisp,line=$line::[$($f.code)] $($f.message)"
    } else {
        # Azure DevOps format
        Write-Host "##vso[task.logissue type=$type;sourcepath=$pathDisp;linenumber=$line;code=$($f.code)] $($f.message)"
    }
}

# ---------------------------------------------------------------------
# 5. GENERATE CONTENT (SPLIT LOGIC FIXED)
# ---------------------------------------------------------------------
# $timestamp = Get-Date -Format "HH:mm UTC"

# Common Header
$header = "### $TaskTitle$NL"
$stats = ""
$table = ""

if ($findings.Count -eq 0) {
    $stats += "✅ **Passed** (No issues found)$NL"
} else {
    $icon = if ($errCount -gt 0) { "🛑" } else { "⚠️" }
    # Just the counts here. No "See Summary" text yet.
    $stats += "$icon **Issues Found:** $errCount Errors, $warnCount Warnings$NL"

    # Build the table
    $table += "$NL| Status | Rule | Location | Line | Details |$NL"
    $table += "| :---: | :--- | :--- | :---: | :--- |$NL"

    foreach ($f in $findings) {
        $fIcon = if ($f.severity -eq 0) { "🛑" } elseif ($f.severity -eq 1) { "⚠️" } else { "ℹ️" }
        $crumb = if ($f.path -is [System.Array]) { $f.path -join " > " } else { [string]$f.path }
        $ln = if ($f.range) { [int]$f.range.start.line + 1 } else { "-" }
        $msg = $f.message -replace "\|", "&#124;" -replace "`r`n", " " -replace "`n", " "
        
        $table += "| $fIcon | **$($f.code)** | ``$crumb`` | $ln | $msg |$NL"
    }
}

# --- CREATE TWO VERSIONS ---

# 1. PR Comment: Header + Stats + HINT TEXT
# ---------------------------------------------------------------------
# 6. POST SHORT PR COMMENT
# ---------------------------------------------------------------------
# Detect platform and set variables accordingly
if ($env:GITHUB_ACTIONS) {
    # GitHub Actions
    $token = $env:GITHUB_TOKEN
    $prId = $env:GITHUB_PR_NUMBER
    
    if ($prId -and $token) {
        Write-Host "Posting summary stats to PR #$prId (GitHub)..."
        
        # Parse repository owner and name
        $repo = $env:GITHUB_REPOSITORY
        $apiUrl = if ($env:GITHUB_API_URL) { $env:GITHUB_API_URL } else { "https://api.github.com" }
        
        $commentsUrl = "$apiUrl/repos/$repo/issues/$prId/comments"
        $headers = @{
            Authorization = "Bearer $token"
            Accept = "application/vnd.github+json"
        }
        
        $body = @{ body = $prMsg } | ConvertTo-Json -Depth 5

        try {
            Invoke-RestMethod -Uri $commentsUrl -Method Post -Headers $headers -Body $body -ContentType "application/json" | Out-Null
            Write-Host "✅ Comment posted successfully."
        } catch {
            Write-Host "❌ Failed to post comment: $($_.Exception.Message)"
        }
    }
} else {
    # Azure DevOps
    $token = $env:SYSTEM_ACCESSTOKEN
    if (-not $token) { $token = $env:AZURE_DEVOPS_EXT_PAT }
    $prId = $env:SYSTEM_PULLREQUEST_PULLREQUESTID
    if (-not $prId) { $prId = $env:SYSTEM_PULLREQUEST_PULLREQUESTNUMBER }

# ---------------------------------------------------------------------
# 7. UPLOAD FULL SUMMARY
# ---------------------------------------------------------------------
# Use $fullReport (Long Version with Table, NO Hint)
$summaryPath = "$artifactDir/spectral_summary_${TaskID}.md"
Set-Content -Path $summaryPath -Value $fullReport -Encoding UTF8

if ($env:GITHUB_ACTIONS) {
    # GitHub Actions: Append to job summary
    Add-Content -Path $env:GITHUB_STEP_SUMMARY -Value $fullReport
    Write-Host "✅ Summary appended to GitHub Actions job summary"
} else {
    # Azure DevOps: Upload summary
    Write-Host "##vso[task.uploadsummary]$summaryPath"
}repositories/$repoId/pullRequests/$prId/threads?api-version=7.1"
        $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$token"))
        $headers = @{ Authorization = "Basic $b64" }
        
        # Use $prMsg (Short Version with Hint)
        $body = @{ 
            comments = @( @{ content = $prMsg; commentType = 1 } )
            status = 1 
        } | ConvertTo-Json -Depth 5

        try {
            Invoke-RestMethod -Uri $threadsUrl -Method Post -Headers $headers -Body $body -ContentType "application/json" | Out-Null
            Write-Host "✅ Comment posted successfully."
        } catch {
            Write-Host "❌ Failed to post comment: $($_.Exception.Message)"
        }
    }
}   try {
        Invoke-RestMethod -Uri $threadsUrl -Method Post -Headers $headers -Body $body -ContentType "application/json" | Out-Null
        Write-Host "✅ Comment posted successfully."
    } catch {
        Write-Host "❌ Failed to post comment: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------------
# 7. UPLOAD FULL SUMMARY
# ---------------------------------------------------------------------
# Use $fullReport (Long Version with Table, NO Hint)
$summaryPath = "$($env:BUILD_ARTIFACTSTAGINGDIRECTORY)/spectral_summary_${TaskID}.md"
Set-Content -Path $summaryPath -Value $fullReport -Encoding UTF8
Write-Host "##vso[task.uploadsummary]$summaryPath"

# ---------------------------------------------------------------------
# 8. EXIT STATUS
# ---------------------------------------------------------------------
if ($errCount -gt 0) {
    Write-Warning "Spectral found $errCount errors in '$TaskTitle'."
    Exit 0 
} else {
    Exit 0
}