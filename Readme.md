# API Governance: Hub & Spoke Linting Pipeline

> A comprehensive guide to the API Governance system for enforcing API standards while managing legacy code

![Status](https://img.shields.io/badge/status-active-success?style=flat-square)
![Architecture](https://img.shields.io/badge/architecture-hub%20%26%20spoke-blue?style=flat-square)
![Tool](https://img.shields.io/badge/tool-Spectral-orange?style=flat-square)
![Platform](https://img.shields.io/badge/platform-GitHub%20Actions-2088FF?style=flat-square)

> **🚀 Now Migrated to GitHub Actions!** This project has been converted from Azure DevOps to GitHub Actions. See [GITHUB_ACTIONS_MIGRATION.md](GITHUB_ACTIONS_MIGRATION.md) for the migration guide and updated usage instructions.

**Key Features:**
- ✅ **Centralized Rule Management** - Update once, apply everywhere
- ✅ **Zero Legacy Blockers** - New code enforced, legacy code warned
- ✅ **Automated PR Feedback** - Instant, actionable comments with detailed reports
- ✅ **Scalable** - Works for 1 project or 100+ microservices
- ✅ **Smart Commenting** - Concise PR comments with full details in Pipeline Summary tab

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Quick Start](#quick-start)
3. [Hub & Spoke Architecture](#hub--spoke-architecture)
4. [End-to-End Pull Request Flow](#end-to-end-pull-request-flow)
5. [Component Deep-Dive](#component-deep-dive)
6. [Onboarding a New Project](#onboarding-a-new-project)
7. [Maintenance & Benefits](#maintenance--benefits)
8. [Current API Standards](#current-api-standards)
9. [Troubleshooting](#troubleshooting)
10. [Architecture Diagram](#architecture-diagram)
11. [Key Concepts Explained](#key-concepts-explained)
12. [Frequently Asked Questions](#frequently-asked-questions-faq)
13. [File Structure Reference](#file-structure-reference)

---

## 1. Executive Summary

### The Problem
Our organization's APIs are inconsistent, creating:
- ❌ Friction for developer onboarding
- ❌ Poor experiences for API consumers
- ❌ Difficult maintenance
- ❌ Large amounts of legacy code that don't meet modern standards

### The Challenge
**How do we enforce new API standards *today* without blocking all development teams while they fix 5-10 years of legacy code?**

### The Strategy
We implement a **"Hub & Spoke"** model that splits validation into two distinct, parallel passes:

1. ✅ **Block New Violations:** `FAIL` a Pull Request if *any new or modified code* violates our strict ruleset
2. ⚠️ **Report Legacy Violations:** Only `WARN` developers about legacy code violations (build will *not* fail)
3. 🎯 **Centralize Logic:** All rules and pipeline logic are managed in a single "Hub" repository, making new rules instantly global

---

## 2. Quick Start

### For Governance Team (Setting up the Hub)
The Hub is already configured in this repository! Key files:
- ✅ `.spectral.yaml` - Strict rules (errors)
- ✅ `.spectral-warn.yaml` - Advisory rules (warnings)
- ✅ `templates/api-governance.yaml` - Master pipeline template
- ✅ `scripts/` - Python and PowerShell helper scripts

**To add/modify a rule:**
1. Edit `.spectral.yaml` (for blocking errors) or `.spectral-warn.yaml` (for warnings)
2. Commit and push to `main`
3. All projects automatically use the new rules on their next PR ✨

### For Development Teams (Onboarding a Project)
**5-Minute Checklist:**
1. ☑️ Generate your API's OpenAPI spec from the base branch
2. ☑️ Publish it to Azure Artifacts feed `api-baselines` (see [Onboarding](#onboarding-a-new-project))
3. ☑️ Add `generate-spec.ps1` to your repo root (or specify custom path)
4. ☑️ Add `api-governance.yaml` that references this Hub
5. ☑️ Enable Branch Policy for Build Validation

**Result:** Your next PR will automatically get API governance checks! 🎉

---

## 3. Hub & Spoke Architecture

This model is the key to maintainability. It consists of two types of projects:

### The "Hub" (Project: `API_Governance`)

The "brain" of the entire system. This is a single Azure DevOps project containing one repository that holds all master logic:

| File | Purpose |
|------|---------|
| **`templates/api-governance.yaml`** | Master pipeline template containing the entire 8-step process (build, diff, lint, post comments, etc.) |
| **`.spectral.yaml`** | **Strict ruleset** - All rules set to `severity: error` and will *fail the build* |
| **`.spectral-warn.yaml`** | **Advisory ruleset** - Same rules but downgraded to `severity: warn` |
| **`scripts/generate_partial_spec.py`** | Python script that filters the API diff to isolate *only* new, non-legacy changes |
| **`scripts/post_spectral_comments.ps1`** | PowerShell script that runs Spectral, posts concise findings to PR, and uploads detailed reports |
| **`baselines/`** | Directory containing baseline JSON files (e.g., `memberdomain-legacy.json`) |
| **`publish-baseline.yaml`** | Pipeline to publish baseline artifacts to Azure Artifacts feed |

### The "Spokes" (Your API Projects)

All your individual API microservice projects (`MemberDomain`, `PaymentService`, etc.). Their `api-governance.yaml` is intentionally minimal and contains no complex logic:

**Responsibilities:**
1. 🔗 **Connect** to the Hub repo as a `resource`
2. 📋 **Define** project-specific parameters (solution path, project name, baseline package, target branch)
3. 📞 **Call** the master `api-governance.yaml` template from the Hub
4. 📝 **Provide** a `generate-spec.ps1` script to generate OpenAPI specs

---

## 4. End-to-End Pull Request Flow

What happens when a developer opens a Pull Request in any "Spoke" API project:

### Step 1: Trigger 🎬
- Developer opens a PR in `MemberDomain`
- The `api-governance.yaml` is triggered by a Build Validation policy

### Step 2: Fetch Logic 🔗
- Pipeline calls the `api-governance.yaml` template from the `API_Governance` Hub
- All subsequent steps are defined *inside that template*

### Step 3: Generate Specs 📄
- Template calls the Spoke's `generate-spec.ps1` (using dynamic path `$(Build.Repository.Name)/generate-spec.ps1`) to build the **PR branch**
  - Creates **`swagger_head.json`** (the "After" snapshot)
- Intelligently checks out the **target branch** (handles both PR triggers and manual runs)
  - For PRs: Uses `System.PullRequest.TargetBranch`
  - For manual runs: Uses the `DefaultTargetBranch` parameter (configurable, defaults to `main`)
  - Creates **`swagger_main.json`** (the "Before" snapshot)

### Step 4: Calculate the Delta 🔍
1. **Diff Generation:** `openapi-diff` compares "Before" and "After" specs → creates **`diff.json`**
2. **Baseline Download:** Template downloads the project's baseline from Azure Artifacts (using `BaselinePackageName` parameter)
   - Artifact feed: `API_Governance/api-baselines`
   - Renames downloaded file to **`swagger_baseline.json`**
3. **Filter & Process Legacy:** `generate_partial_spec.py` runs with multiple steps:
   - Loads baseline operations (the "ignore list")
   - Filters `diff.json` to remove legacy changes
   - Syncs response/requestBody schemas from `swagger_head.json` (preserves `$ref`)
   - Builds minimal `components/schemas` with transitive closure
4. **Output:** Creates **`partial_spec.json`** and **`partial_spec.yaml`** - temporary specs containing *only* changes to new, non-legacy endpoints with proper schema references

### Step 5: Two-Pass Linting 🔬

#### **PASS 1: The "PR Blocker" (Errors) ⛔**
- Calls `post_spectral_comments.ps1` with:
  - `TaskID: "Strict"`
  - `TaskTitle: "NB Governance 🛑 Strict Checks (New Code)"`
- Lints the **SMALL** `partial_spec.json` (new code only)
- Uses the **STRICT** `.spectral.yaml` ruleset (all rules are `severity: error`)
- Posts **concise summary** to PR with error count and hint to view full report
- Uploads **detailed table** to Pipeline Summary tab (`Extensions/Summary`)
- If any errors exist → **Pipeline FAILS (`exit 1`)** → PR is **BLOCKED**

#### **PASS 2: The "Legacy Report" (Warnings) ⚠️**
- Calls `post_spectral_comments.ps1` *again* (runs even if Pass 1 fails via `condition: always()`)
  - `TaskID: "Advisory"`
  - `TaskTitle: "NB Governance ⚠️ Advisory Checks (Full Spec)"`
- Lints the **ENTIRE** `swagger_head.json` (new + legacy code)
- Uses the **ADVISORY** `.spectral-warn.yaml` ruleset (all rules are `severity: warn`)
- Posts **concise warning summary** to PR
- Uploads **detailed warning table** to Pipeline Summary tab
- All findings posted as warnings → Script **PASSES (`exit 0`)**

### Step 6: Complete ✅
Developer receives:
- **In PR Comments:** Concise summary with counts (e.g., "🛑 Issues Found: 5 Errors, 12 Warnings")
- **In Pipeline Summary Tab:** Full detailed tables with line numbers, paths, and rule codes
- ✅/❌ Clear red/green signal on whether their *new code* is compliant (Errors - blocks PR)
- ⚠️ Informational report on legacy technical debt

---

## 5. Component Deep-Dive

### Component 1: The "Spoke" Pipeline (`api-governance.yaml`)

**Role:** The "Client" or "Caller"

**Example from MemberDomain:**
```yaml
pr: none

pool:
  vmImage: ubuntu-latest

resources:
  repositories:
    - repository: rules
      type: git
      project: API_Governance
      name: API_Governance
      ref: refs/heads/main

stages: 
  - stage: APIGovernance
    displayName: 'API Governance Validation'
    jobs:
      - job: APIGovernance
        displayName: 'API Governance'
        steps:
          - checkout: self
            persistCredentials: true
            clean: true
            fetchDepth: 0

          - checkout: rules

          - task: NuGetAuthenticate@1
            displayName: 'NuGet Authenticate'
            inputs:
              forceReinstallCredentialProvider: true

          - template: templates/api-governance.yaml@rules
            parameters:
              SlnFile: 'NB.MemberDomain.API.sln'
              ProjectFile: 'NB.MemberDomain.API/NB.MemberDomain.API.csproj'
              ProjectAssemblyName: 'NB.MemberDomain.API'
              TargetFramework: 'net8.0'
              SwashbuckleVersion: '6.6.2'
              SwaggerDocName: 'v1'
              BaselinePackageName: 'memberdomain-legacy'
              DefaultTargetBranch: 'master_common'
```

**Key Elements:**
- **`resources:`** - Defines the connection to the `API_Governance` Hub project and repository (named `rules` in this example)
- **`parameters:`** - The "contract" - tells the Hub template *how* to build this project
  - `SlnFile` - Path to the solution file
  - `ProjectFile` - Path to the project file
  - `ProjectAssemblyName` - Assembly name
  - `TargetFramework` - .NET target framework
  - `SwashbuckleVersion` - Swashbuckle.AspNetCore.Cli version
  - `SwaggerDocName` - Swagger document name (usually 'v1')
  - **`BaselinePackageName`** - ⭐ Most important! Name of the baseline package in Azure Artifacts (e.g., `memberdomain-legacy`)
  - **`DefaultTargetBranch`** - 🆕 Fallback branch for manual runs (e.g., `master_common`, `main`, `develop`)
- **`template: ...@rules`** - The hand-off that transfers execution control to the Hub template

### Component 2: The "Hub" Template (`templates/api-governance.yaml`)

**Role:** The "Engine" or "Master Logic"

**Pipeline Structure:**

| Step | Action | Details |
|------|--------|---------|
| 1 | Generate PR Branch Spec | Calls Spoke's `generate-spec.ps1` → creates `swagger_head.json` |
| 2 | Checkout Target Branch | 🆕 Smart branch detection (PR target or default) → `swagger_main.json` |
| 3 | Install Tools | Installs `openapi-diff` (npm) and prepares Python environment |
| 4 | Run OpenAPI Diff | Compares `swagger_main.json` vs `swagger_head.json` → creates `diff.json` |
| 5 | Download Baseline | Uses Azure CLI to download baseline package from `api-baselines` feed → renames to `swagger_baseline.json` |
| 6 | Generate Partial Spec | Runs `generate_partial_spec.py`: filters diff, syncs schemas, builds components → creates `partial_spec.json` |
| 7 | **PASS 1: Strict Lint** | 🆕 Lints `partial_spec.json` with `.spectral.yaml` → Posts concise PR comment + detailed summary → **Can FAIL build** |
| 8 | **PASS 2: Advisory Lint** | 🆕 Lints `swagger_head.json` with `.spectral-warn.yaml` → Posts concise PR comment + detailed summary → Always passes |

**Key Improvements:**
- **Dynamic Paths:** Uses `$(Build.Repository.Name)` to automatically find the correct `generate-spec.ps1` location
- **Smart Branch Handling:** Detects PR context and falls back to `DefaultTargetBranch` for manual runs
- **Improved Commenting:** Generates two versions of each report (concise for PR, detailed for summary tab)

### Component 3: The "Legacy Filter" (`scripts/generate_partial_spec.py`)

**Role:** The "Brain" of the operation - executes the core "ignore legacy" strategy

**Execution Flow:**
```
1. Load diff.json
2. Load baseline (legacy operations)
3. Build filtered spec (skip legacy)
4. Sync responses/requestBodies (restore $refs)
5. Ensure responses exist
6. Build minimal components
7. Save partial_spec.json + partial_spec.yaml
```

**Key Functions:**

#### 1. `load_baseline_operations()`
- Reads the downloaded `swagger_baseline.json` from pipeline workspace
- Creates a Python `set` of all legacy operations in format: **`'METHOD@/path/string'`**
  - Example: `'GET@/v1/members-info/{id}'`
- This set becomes our "ignore list" for high-speed lookups
- Returns the set of legacy operation keys

#### 2. `build_new_spec()` - The "Sieve"
- Loops through *every change* in `diff.json`
- For each change:
  1. Determines which operation it belongs to (e.g., `'GET@/v1/new-endpoint'`)
  2. Looks up if operation is in baseline (legacy)
  3. If legacy operation → **SKIP** (will only trigger warnings, not errors)
  4. If new operation → **INCLUDE** (will be linted with strict rules)
- Handles three change types:
  - `add` - New endpoint/property (checks destination)
  - `change` - Modified endpoint/property (checks destination)
  - `remove` - Deleted endpoint/property (checks source)
- Prints detailed logging for each decision

#### 3. `sync_responses_from_base()` - Critical for Schema Integrity
- **Critical improvement** to preserve original schema structures
- Restores `$ref`-based response schemas from the base spec (`swagger_head.json`)
- Prevents inline schema expansion that can confuse Spectral
- Also syncs `requestBody` definitions with proper `$ref` references
- Ensures the partial spec uses the same schema references as the full spec

#### 4. `build_required_components()` - Minimal Schema Set
- Builds a minimal `components/schemas` section
- **Transitive closure** algorithm:
  1. Finds all `$ref` references in the paths
  2. For each reference, includes the schema definition
  3. Recursively finds and includes any schemas referenced by those schemas
  4. Continues until all dependencies are resolved
- Only includes schemas that are actually used
- Dramatically reduces partial spec size while maintaining validity
- Example: If you reference `UserResponse`, it automatically includes `User`, `Address`, etc.

#### 5. `ensure_operations_have_responses()`
- Fallback to ensure all operations have at least a default response
- Tries to copy responses from base specs first
- Falls back to a default response if needed
- Required for Spectral to run successfully

#### 6. Helper Functions
- `load_json()` - Safely loads JSON files with error handling
- `save_yaml()` - Saves YAML (or JSON fallback if PyYAML unavailable)
- `get_key_from_loc()` - Converts location strings to operation keys
- `set_by_tokens()` / `remove_by_tokens()` - Token-based spec manipulation
- `find_all_refs()` - Recursively finds all `$ref` values in spec

**Output:** Saves the filtered spec as **`partial_spec.json`** and **`partial_spec.yaml`**

**Recent Improvements:**
- ✅ Better schema reference preservation (no more inline expansion)
- ✅ Minimal components section (only includes what's needed)
- ✅ Improved response/requestBody handling
- ✅ More robust error handling and logging
- ✅ Support for both YAML and JSON output

### Component 4: The "Enforcer & Messenger" (`scripts/post_spectral_comments.ps1`)

**Role:** The "Gatekeeper" - runs Spectral, posts feedback, and controls build pass/fail

**Parameters:**
- `$SpecFile` - Path to OpenAPI spec to lint
- `$RulesetFile` - Path to Spectral ruleset to use
- **`$TaskID`** - 🆕 Unique identifier for this task (e.g., "Strict", "Advisory") - used for file naming
- **`$TaskTitle`** - 🆕 Display title for PR comments (e.g., "NB Governance 🛑 Strict Checks (New Code)")

**Execution Flow:**

```
1. Check Spectral Installation
   ↓ (Install if missing)
2. Validate Spec File Exists
   ↓ (Exit 0 if missing - not a failure)
3. Run Spectral Lint
   ↓ spectral lint $SpecFile --ruleset $RulesetFile --format json
4. Parse Results
   ↓ (Convert JSON output to PowerShell objects)
5. Log Issues to Console
   ↓ (Uses ADO logging commands for "Issues" tab)
6. Generate TWO Versions of Report
   ↓ Version 1: Concise (for PR comment)
   ↓ Version 2: Detailed table (for Pipeline Summary)
7. Post Concise Comment to PR
   ↓ (Includes hint: "See Extensions/Summary tab for details")
8. Upload Detailed Summary
   ↓ (Creates spectral_summary_${TaskID}.md and uploads)
9. The Verdict
   ↓
   if (errors found) { exit 0 } → SOFT MODE (Currently set to pass)
   else { exit 0 } → PASSES BUILD ✅
```

**Severity Mapping:**
- `0` = Error (blocks build in strict mode)
- `1` = Warning (informational)
- `2` = Info (informational)
- `3` = Hint (informational)

**Key Features:**
- ✅ **Dual Output System:** Concise PR comments + detailed pipeline summaries
- ✅ Formatted Markdown comments with severity badges (🛑 ⚠️ ℹ️)
- ✅ Supports both OAuth tokens and PAT authentication
- ✅ Graceful handling of missing files or non-PR contexts
- ✅ **No comment spam:** Each run creates a fresh, timestamped comment
- ✅ **Unique file naming:** Uses `TaskID` to prevent file overwrites when running multiple passes
- ✅ **Hint text:** Guides developers to the detailed report in Pipeline Summary tab

**Example PR Comment (Concise):**
```markdown
### NB Governance 🛑 Strict Checks (New Code)
🛑 **Issues Found:** 5 Errors, 0 Warnings

> _(See the **Extensions/Summary** tab in the pipeline for the detailed line-by-line report)_
```

**Example Pipeline Summary (Detailed):**
```markdown
### NB Governance 🛑 Strict Checks (New Code)
🛑 **Issues Found:** 5 Errors, 0 Warnings

| Status | Rule | Location | Line | Details |
| :---: | :--- | :--- | :---: | :--- |
| 🛑 | **path-versioning** | `paths > /members > get` | 15 | Path '/members' must start with /v<number>/ |
| 🛑 | **parameter-naming-camelCase** | `paths > /v1/users > get > parameters > 0` | 42 | Parameter name 'user_id' is not camelCase |
...
```

### Component 5: The "Spec Generator" (`generate-spec.ps1`)

**Role:** Project-specific script that builds and generates OpenAPI/Swagger specs

**Location:** Root of each Spoke repository (e.g., `MemberDomain/generate-spec.ps1`)

**Key Responsibilities:**
1. Restore NuGet packages (with smart config file detection)
2. Build the .NET solution
3. Install and use Swashbuckle.AspNetCore.Cli tool
4. Generate OpenAPI spec from compiled assembly
5. Validate output and provide clear error messages

**Parameters (passed from template):**
```powershell
-OutputFile           # Where to save the generated spec
-SlnFile             # Path to solution file
-ProjectFile         # Path to project file
-ProjectAssemblyName # Assembly name
-TargetFramework     # Target framework (e.g., net8.0)
-SwashbuckleVersion  # Swashbuckle CLI version
-SwaggerDocName      # Swagger document name (e.g., v1)
```

**Recent Improvements:**
- ✅ Smart NuGet config detection (checks solution dir, project dir, and root)
- ✅ Handles both `nuget.config` and `Nuget.config` (case-sensitive filesystems)
- ✅ Clear logging and error messages
- ✅ Automatic tool installation with version control

---

## 6. Onboarding a New Project

To add a new API project to this governance system, follow these steps:

### Step 1: Create Baseline 📸
Generate a full OpenAPI spec of the *current* base branch (typically `master`, `main`, or `master_common`):
```powershell
# Run your project's spec generator
./generate-spec.ps1 -OutputFile ./baselines/your-project-baseline.json `
  -SlnFile "YourSolution.sln" `
  -ProjectFile "YourProject/YourProject.csproj" `
  -ProjectAssemblyName "YourProject" `
  -TargetFramework "net8.0" `
  -SwashbuckleVersion "6.6.2" `
  -SwaggerDocName "v1"
```
This becomes your "legacy ignore list"

> **Important:** The baseline should represent the current production state of your API. Any endpoints in this baseline will only generate warnings, not errors.

### Step 2: Publish Baseline 📦
Publish the baseline to Azure Artifacts:
- **Feed:** `API_Governance/api-baselines`
- **Package Name:** Choose a unique name (e.g., `memberdomain-legacy`, `payment-service-baseline`)
- **Version:** `1.0.0`

You can use the `publish-baseline.yaml` pipeline as a template:
```yaml
trigger: none
pool:
  vmImage: 'windows-latest'

steps:
- task: UniversalPackages@0
  displayName: 'Publish Your Project Baseline'
  inputs:
    command: publish
    publishDirectory: '$(Build.SourcesDirectory)/baselines'
    vstsFeedPublish: 'API_Governance/api-baselines'
    vstsFeedPackagePublish: 'your-project-baseline'  # Change this
    versionOption: custom
    versionPublish: '1.0.0'
    packagePublishDescription: 'Your Project legacy baseline'
```

### Step 3: Add Spec Generator Script 📝
Add a `generate-spec.ps1` script to your repository root (or custom location) that:
- Builds your .NET project
- Generates the OpenAPI/Swagger specification
- Outputs to the specified file path

**Use the provided example from MemberDomain as a template** - it includes:
- Smart NuGet config detection
- Proper error handling
- Tool installation logic
- Clear logging

**Parameters it must accept:**
- `OutputFile` - Where to save the generated spec
- `SlnFile` - Path to solution file
- `ProjectFile` - Path to project file
- `ProjectAssemblyName` - Assembly name
- `TargetFramework` - Target framework
- `SwashbuckleVersion` - Swashbuckle version
- `SwaggerDocName` - Swagger document name

### Step 4: Add Pipeline Configuration 🔧
Create `api-governance.yaml` in your repository:
```yaml
pr: none  # Only run on PR via Build Validation policy

pool:
  vmImage: ubuntu-latest

resources:
  repositories:
    - repository: rules
      type: git
      project: API_Governance
      name: API_Governance
      ref: refs/heads/main

stages: 
  - stage: APIGovernance
    displayName: 'API Governance Validation'
    jobs:
      - job: APIGovernance
        displayName: 'API Governance'
        steps:
          - checkout: self
            persistCredentials: true
            clean: true
            fetchDepth: 0

          - checkout: rules

          - task: NuGetAuthenticate@1
            displayName: 'NuGet Authenticate'
            inputs:
              forceReinstallCredentialProvider: true

          - template: templates/api-governance.yaml@rules
            parameters:
              SlnFile: 'YourSolution.sln'
              ProjectFile: 'YourProject/YourProject.csproj'
              ProjectAssemblyName: 'YourProject'
              TargetFramework: 'net8.0'
              SwashbuckleVersion: '6.6.2'
              SwaggerDocName: 'v1'
              BaselinePackageName: 'your-project-baseline'
              DefaultTargetBranch: 'main'  # or 'master', 'master_common', etc.
```

> **Note:** Adjust `DefaultTargetBranch` to match your repository's main branch name.

### Step 5: Grant Pipeline Permissions 🔐
Ensure your pipeline has access to:
- ✅ The `API_Governance` repository (for templates/scripts)
- ✅ The `api-baselines` artifact feed (for downloading baselines)
- ✅ Pull Request comments (System.AccessToken permissions)

**To enable PR comment permissions:**
1. Go to **Project Settings** → **Repositories** → **Your Repository**
2. Navigate to **Security** tab
3. Find your build service account: `[Project Name] Build Service ([Org Name])`
4. Grant **"Contribute to pull requests"** permission

### Step 6: Activate Build Validation ✅
Configure a **Build Validation** policy on your main branch:
1. Go to **Branch Policies** for your main branch (e.g., `main`, `master`, `master_common`)
2. Add **Build Validation**
3. Select your new `api-governance.yaml` pipeline
4. Set **Trigger:** Automatic
5. Set **Policy requirement:** Required
6. **Display name:** "API Governance Check"
7. **Path filter (optional):** Limit to API-related paths if needed

> **Pro Tip:** You can also enable this for other long-lived branches (e.g., `develop`, `release/*`) to catch issues earlier in your workflow.

---

## 7. Maintenance & Benefits

### For the Governance Team 🎯

**Adding/Updating Rules:**
When a new API rule is required for the *entire organization*:
1. Edit **only** the `.spectral.yaml` file (for errors) or `.spectral-warn.yaml` file (for warnings) in the `API_Governance` Hub
2. Commit and push
3. ✨ **The change is instantly applied** to every project's pipeline on their very next PR

**No need to:**
- ❌ Update 20+ individual project pipelines
- ❌ Coordinate deployments across teams
- ❌ Train teams on new pipeline configurations

**Updating Baselines:**
When legacy code is fixed and meets current standards, update the baseline:
1. Generate a new OpenAPI spec from the updated base branch
2. Republish to Azure Artifacts with the same package name and version `1.0.0`
3. The next PR will use the updated baseline automatically

**Example Rules Currently Enforced:**
- ✅ Path segments must be camelCase
- ✅ Parameters must use camelCase
- ✅ Paths must include version (e.g., `/v1/`)
- ✅ Tags should be PascalCase (warning only)
- ✅ Responses must include `application/json`
- ✅ 2xx responses must define top-level `code` and `data` properties
- ✅ CommonResponse schemas must have `code` and `data` properties
- ✅ 204 responses must not have a body

### For Developers 👨‍💻👩‍💻

**Clear, Actionable Feedback:**
- ⛔ **Errors (Red)** - Issues in *new code* that **BLOCK** the PR
  - Must be fixed before merge
  - Only applies to new/modified endpoints
  - Shows in PR as concise summary
- ⚠️ **Warnings (Yellow)** - Issues in *legacy code* that are **INFORMATIONAL**
  - Build passes regardless
  - Helps identify technical debt
  - Can be fixed incrementally
- 📊 **Detailed Reports** - Full line-by-line breakdown in Pipeline Summary tab

**Benefits:**
- ✅ Know exactly what needs to be fixed (no guessing)
- ✅ Not blocked by years of legacy code
- ✅ Automatic PR comments with concise summaries
- ✅ Detailed reports available in Pipeline Summary tab
- ✅ Consistent API standards across the organization
- ✅ Clear guidance with rule codes and messages
- ✅ No comment spam - fresh report on each run

---

## 8. Current API Standards

The following rules are currently enforced (see `.spectral.yaml` and `.spectral-warn.yaml`):

| Rule | Description | Pass 1 (New Code) | Pass 2 (All Code) |
|------|-------------|-------------------|-------------------|
| `path-camel-case` | Path segments must be camelCase | ❌ Error | ⚠️ Warning |
| `parameter-naming-camelCase` | Parameters must use camelCase | ❌ Error | ⚠️ Warning |
| `path-versioning` | Paths must start with `/v<number>/` | ❌ Error | ⚠️ Warning |
| `tag-pascal-case` | Tags should be PascalCase | ⚠️ Warning | ⚠️ Warning |
| `require-json-body` | Responses must include `application/json` | ❌ Error | ⚠️ Warning |
| `response-envelope-has-code-and-data` | 2xx responses must have `code` and `data` properties | ❌ Error | ⚠️ Warning |
| `common-response-has-code` | `CommonResponse` must have `code` property | ❌ Error | ⚠️ Warning |
| `common-response-has-data` | `CommonResponse` must have `data` property | ❌ Error | ⚠️ Warning |
| `no-content-response-no-body` | 204 responses must not have body | ❌ Error | ⚠️ Warning |

---

## 9. Troubleshooting

### Issue: Baseline not found
**Error Message:** `Could not find a downloaded baseline JSON file`

**Solution:** 
- Verify the package exists in Azure Artifacts feed `api-baselines` with version `1.0.0`
- Check that `BaselinePackageName` parameter in your pipeline matches the published package name exactly
- Ensure the pipeline has permissions to access the artifact feed
- Run `az artifacts universal list --feed api-baselines` to verify package exists

### Issue: Pipeline can't access Hub repository
**Error Message:** Repository resource access errors

**Solution:** 
- Grant pipeline permission to access the `API_Governance` repository
- Go to Project Settings → Repositories → API_Governance → Security
- Add the build service account with Read permissions

### Issue: PR comments not being posted
**Error Message:** `Failed to post comment` or comments not appearing

**Solution:** 
- Ensure `System.AccessToken` has proper permissions
- Go to Project Settings → Repositories → [Your Repo] → Security
- Find: `[Project Name] Build Service ([Org Name])`
- Grant: **"Contribute to pull requests"** permission (set to Allow)
- Verify the pipeline is triggered in PR context (not manual run)

### Issue: False positives on legacy code
**Error:** New code is being flagged when it shouldn't be

**Solution:** 
- Regenerate and republish your baseline to include the current state of your API
- Ensure you generated the baseline from the correct base branch
- Check that the baseline file contains the operations you expect

### Issue: New endpoint flagged as legacy
**Error:** New endpoints are not being linted with strict rules

**Solution:** 
- Check that your baseline doesn't include the new endpoint
- You may need to regenerate the baseline from a clean base branch
- Verify the operation key format matches: `METHOD@/path` (e.g., `GET@/v1/users`)

### Issue: Spectral not finding rules
**Error Message:** `No results` or rules not being applied

**Solution:**
- Verify `.spectral.yaml` and `.spectral-warn.yaml` files exist in the Hub repository
- Check that the `RulesetFile` parameter path is correct
- Ensure Spectral CLI is properly installed (script auto-installs if missing)

### Issue: swagger_head.json or swagger_main.json not found
**Error Message:** `swagger_head.json not found!` or `swagger_main.json not found!`

**Solution:**
- Verify the `generate-spec.ps1` script exists in your Spoke repository root
- Check that all required parameters are being passed correctly
- Ensure the script has proper error handling and actually generates output
- Check the script is executable and not failing silently
- Review NuGet config file location (should be in solution or project directory)

### Issue: Branch checkout fails
**Error Message:** `pathspec 'master' did not match any file(s)` or similar

**Solution:**
- Set `DefaultTargetBranch` parameter to match your repository's main branch
- Common values: `main`, `master`, `master_common`, `develop`
- The template now intelligently handles both PR and manual runs
- For PRs: Uses `System.PullRequest.TargetBranch`
- For manual runs: Uses `DefaultTargetBranch` parameter

### Issue: openapi-diff produces empty output
**Error Message:** `No changes found` but you know there are changes

**Solution:**
- Verify both `swagger_head.json` and `swagger_main.json` are valid OpenAPI specs
- Check that the specs are in OpenAPI 3.0 format (not Swagger 2.0)
- Ensure the diff tool is capturing structural changes, not just formatting differences

### Issue: Spectral reports "Could not find schema definition"
**Error Message:** Schema references are broken or missing

**Solution:**
- This should be automatically fixed by the `build_required_components()` function
- Verify `swagger_head.json` contains all the schemas your endpoints reference
- Check that the Python script completed successfully (look for "Step 4: Building minimal components")
- If the issue persists, the base spec may have broken `$ref` references

### Issue: Partial spec is too large or includes unnecessary schemas
**Symptom:** The partial spec includes schemas not directly used by new endpoints

**Solution:**
- The script uses transitive closure - if schema A references schema B, both are included
- This is expected and necessary for Spectral validation
- If truly unnecessary schemas appear, check for stray `$ref` references in your new endpoints
- The script logs which schemas are kept: look for "Pruned components. Kept X referenced schemas"

### Issue: Comments are too verbose / cluttering PR
**Good News:** This has been fixed in the latest version!

**Current Behavior:**
- PR comments now show only concise summaries with counts
- Full detailed tables appear in the Pipeline Summary tab (Extensions/Summary)
- Developers are guided to the detailed report via hint text
- No more cluttered PR comment sections

### Issue: Multiple tasks overwriting summary files
**Good News:** This has been fixed with TaskID parameter!

**Current Behavior:**
- Each task (Strict, Advisory) creates unique files: `spectral_Strict_results.json`, `spectral_Advisory_results.json`
- Summary files are also unique: `spectral_summary_Strict.md`, `spectral_summary_Advisory.md`
- Both reports appear in the Pipeline Summary tab without overwriting each other

---

## 10. Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    AZURE DEVOPS ORGANIZATION                   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │          PROJECT: API_Governance (The Hub)               │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │  REPOSITORY: API_Governance                        │  │ │
│  │  │  ┌──────────────────────────────────────────────┐  │  │ │
│  │  │  │  📄 .spectral.yaml (Strict Rules)            │  │  │ │
│  │  │  │  📄 .spectral-warn.yaml (Advisory Rules)     │  │  │ │
│  │  │  │  📄 templates/api-governance.yaml            │  │  │ │
│  │  │  │     (Master Pipeline Template)               │  │  │ │
│  │  │  │  📄 scripts/generate_partial_spec.py         │  │  │ │
│  │  │  │  📄 scripts/post_spectral_comments.ps1       │  │  │ │
│  │  │  └──────────────────────────────────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │  ARTIFACT FEED: api-baselines                      │  │ │
│  │  │  - memberdomain-legacy@1.0.0                       │  │ │
│  │  │  - payment-service-baseline@1.0.0                  │  │ │
│  │  │  - ... (other baselines)                           │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │       PROJECT: MemberDomain (Spoke 1)                    │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │  REPOSITORY: MemberDomain                          │  │ │
│  │  │  ┌──────────────────────────────────────────────┐  │  │ │
│  │  │  │  📄 api-governance.yaml                      │  │  │ │
│  │  │  │     - Calls Hub template                     │  │  │ │
│  │  │  │     - Defines parameters                     │  │  │ │
│  │  │  │  📄 generate-spec.ps1                        │  │  │ │
│  │  │  │     - Generates OpenAPI spec                 │  │  │ │
│  │  │  │  📁 Source Code (.NET API)                   │  │  │ │
│  │  │  └──────────────────────────────────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │       PROJECT: PaymentService (Spoke 2)                  │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │  REPOSITORY: PaymentService                        │  │ │
│  │  │  ┌──────────────────────────────────────────────┐  │  │ │
│  │  │  │  📄 api-governance.yaml                      │  │  │ │
│  │  │  │  📄 generate-spec.ps1                        │  │  │ │
│  │  │  │  📁 Source Code (.NET API)                   │  │  │ │
│  │  │  └──────────────────────────────────────────────┘  │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ... (More Spoke Projects)                                     │
└────────────────────────────────────────────────────────────────┘

PULL REQUEST EXECUTION FLOW:
┌─────────────────────────────────────┐
│ Developer Opens PR in MemberDomain  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Build Validation Policy Triggers    │
│ Spoke: api-governance.yaml          │
│  - Calls Hub template               │
│  - Provides parameters              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Hub Template Executes (8 Steps):    │
│  1. Generate swagger_head.json      │
│  2. Smart checkout target branch    │
│     (PR target or DefaultTargetBranch)
│  3. Generate swagger_main.json      │
│  4. Install diff tools              │
│  5. Run openapi-diff                │
│  6. Download baseline from feed     │
│  7. Generate partial_spec.json      │
│  8a. PASS 1: Lint partial_spec.json │
│      - Lint with .spectral.yaml     │
│      - Post concise PR comment      │
│      - Upload detailed summary      │
│  8b. PASS 2: Lint swagger_head.json │
│      - Lint with .spectral-warn.yaml│
│      - Post concise PR comment      │
│      - Upload detailed summary      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Developer Receives:                 │
│  ✅ Concise PR comments (summaries) │
│  📊 Detailed reports (Summary tab)  │
│  🛑 Build pass/fail status          │
└─────────────────────────────────────┘
```

---

## 11. Key Concepts Explained

### What is a "Baseline"?
A baseline is a snapshot of your API's OpenAPI specification at a specific point in time (typically when you onboard to the governance system). It represents your "legacy" code. Any endpoints present in the baseline will:
- ✅ Still be linted, but only produce **warnings**
- ✅ Not block Pull Requests
- ✅ Allow you to adopt API standards without fixing years of technical debt first

### What is a "Partial Spec"?
The partial spec (`partial_spec.json`) is a dynamically generated, temporary OpenAPI specification that contains **only** the changes to non-legacy endpoints. It's created by:
1. Taking the diff between PR branch and base branch
2. Filtering out any changes to operations listed in the baseline
3. Building a new, minimal spec with just the new/modified endpoints
4. **Restoring `$ref` references** from the original spec (prevents schema expansion)
5. **Building a minimal components section** with only referenced schemas

This is what gets linted with strict rules in Pass 1.

**Why restore `$ref` references?**
- The diff tool may inline schemas, making the spec harder to read
- Restoring `$ref` references keeps the spec clean and maintainable
- Ensures Spectral rules that check schema references work correctly
- The transitive closure algorithm ensures all dependent schemas are included

**Example:**
If your new endpoint returns `UserResponse` which references `User` and `Address`, the partial spec will automatically include all three schemas in the `components/schemas` section.

### Operation Key Format
Operations are identified using the format: `METHOD@/path`

**Examples:**
- `GET@/v1/users` - A GET endpoint at `/v1/users`
- `POST@/v1/members-info` - A POST endpoint at `/v1/members-info`
- `DELETE@/v1/users/{id}` - A DELETE endpoint with path parameter

The path is preserved exactly as it appears in the OpenAPI spec, including path parameters like `{id}`.

### Severity Levels in Spectral
| Severity | Value | Impact | Used In |
|----------|-------|--------|---------|
| Error | `0` | Blocks PR, fails build | `.spectral.yaml` (Pass 1) |
| Warning | `1` | Informational only, passes build | `.spectral-warn.yaml` (Pass 2) |
| Info | `2` | Informational only, passes build | Optional |
| Hint | `3` | Informational only, passes build | Optional |

### Why Two Passes?
**Pass 1 (Strict)** ensures new code meets standards right away, preventing technical debt from growing.

**Pass 2 (Advisory)** provides visibility into existing technical debt without blocking progress, allowing teams to plan remediation work.

---

## 12. Frequently Asked Questions (FAQ)

### Q: Can I customize rules for specific projects?
**A:** The current architecture enforces consistent rules across all projects (by design). However, you can:
- Use Spectral's `except` feature to exclude specific paths/operations
- Create project-specific rulesets by adding conditional logic in the template
- Use custom functions in Spectral rules to implement project-specific logic

### Q: What happens if I modify a legacy endpoint?
**A:** If you modify an endpoint that exists in the baseline:
- **Pass 1** will **NOT** lint it (it's filtered out of the partial spec)
- **Pass 2** will lint it and post **warnings** (not errors)
- **Result:** Your PR will pass, but you'll see warnings

### Q: Can I have different baselines for different environments?
**A:** Yes, but you'll need to modify the template to accept an environment parameter and download different baseline packages accordingly.

### Q: How do I add a new rule that doesn't break existing projects?
**A:** 
1. Add the rule to `.spectral-warn.yaml` first (as a warning)
2. Let teams see the warnings and fix their code
3. After a grace period, move the rule to `.spectral.yaml` (as an error)
4. Update all baselines to reflect the fixed state

### Q: What if my project doesn't use .NET/Swashbuckle?
**A:** The Hub template is tool-agnostic. You just need to:
- Create a `generate-spec.ps1` script that generates OpenAPI specs for your technology
- Ensure the script accepts the same parameters
- The rest of the pipeline (diff, lint, post comments) works with any OpenAPI 3.0 spec

### Q: Can I run this locally before pushing?
**A:** Yes! You can:
1. Generate your spec: `./generate-spec.ps1 -OutputFile spec.json ...`
2. Run Spectral: `spectral lint spec.json --ruleset path/to/.spectral.yaml`

### Q: What if my repository uses `main` instead of `master`?
**A:** Set the `DefaultTargetBranch` parameter in your `api-governance.yaml`:
```yaml
parameters:
  DefaultTargetBranch: 'main'  # or 'develop', 'master_common', etc.
```

### Q: Can I customize rules per project?
**A:** Not currently. The system is designed for **centralized governance** where all projects follow the same rules. If you need project-specific rules, you'll need to fork the Hub repository or implement a custom solution.

### Q: How do I update my baseline after fixing legacy code?
**A:** 
1. Generate a new spec from your base branch
2. Republish to Azure Artifacts with the same package name and version `1.0.0`
3. The next PR will automatically use the updated baseline

### Q: Why do I see two sets of comments on my PR?
**A:** This is expected! You receive:
1. **Strict Check Results** - Errors in new code (blocks PR)
2. **Advisory Check Results** - Warnings in all code (informational)

Each provides a concise summary with a link to the detailed report in the Pipeline Summary tab.

### Q: What's the difference between the PR comments and Pipeline Summary?
**A:**
- **PR Comments:** Concise summaries showing counts and severity
  - Quick overview without cluttering the PR
  - Includes hint to view full report
- **Pipeline Summary:** Detailed tables with line numbers, paths, and messages
  - Full line-by-line breakdown
  - Available in Extensions/Summary tab

### Q: Can I use this with non-.NET projects?
**A:** Yes, but you'll need to provide your own `generate-spec.ps1` script that:
- Builds your project
- Generates an OpenAPI 3.0 spec
- Outputs to the specified file path

The rest of the system (diff, filter, lint) is language-agnostic.

### Q: What if openapi-diff finds no changes?
**A:** The system gracefully handles this:
1. `generate_partial_spec.py` creates an empty spec
2. Spectral reports "No issues found"
3. Pipeline passes ✅

### Q: How do I see what rules are being applied?
**A:** View the rule files in the Hub repository:
- Strict rules: `.spectral.yaml`
- Advisory rules: `.spectral-warn.yaml`

Each rule includes a `description` and `message` field explaining what it checks.

---

## 13. File Structure Reference

```
API_Governance/                    # Hub Repository
├── .spectral.yaml                 # Strict ruleset (errors)
├── .spectral-warn.yaml            # Advisory ruleset (warnings)
├── Readme.md                      # This file
├── publish-baseline.yaml          # Pipeline to publish baselines
├── templates/
│   └── api-governance.yaml        # Master pipeline template
├── scripts/
│   ├── generate_partial_spec.py   # Python script to filter diff
│   └── post_spectral_comments.ps1 # PowerShell script to lint and comment
├── baselines/
│   └── memberdomain-legacy.json   # Example baseline file
└── available-baselines/
    └── backend-baseline.json      # Example baseline file

MemberDomain/                      # Example Spoke Repository
├── api-governance.yaml            # Pipeline configuration
├── generate-spec.ps1              # Spec generator script
├── NB.MemberDomain.API.sln        # Solution file
├── NB.MemberDomain.API/
│   ├── NB.MemberDomain.API.csproj # Project file
│   ├── Controllers/               # API controllers
│   └── ... (other source files)
└── ... (other project files)
```

---

**Last Updated:** December 2024

**Maintained By:** API Governance Team

**Questions?** Contact the API Governance Team or create an issue in the `API_Governance` repository.

---

## Future Enhancements (Roadmap)

### Planned Features
- 🔄 **SARIF Output Support** - Generate SARIF files for better Azure DevOps integration
  - Beautiful interactive dashboards in Azure DevOps
  - Direct links to problematic code lines
  - Rich metadata and fix suggestions
- 📊 **Baseline Comparison Reports** - Show progress over time
- 🎨 **Custom Rule Severity Override** - Per-project rule severity customization
- 📈 **Metrics Dashboard** - Track governance compliance across all projects
- 🔍 **Advanced Diff Analysis** - Smarter detection of breaking changes

### Under Consideration
- Support for AsyncAPI specifications
- Automated baseline updates when PRs merge
- Integration with API documentation generators
- Custom rule marketplace

---

*This system is built with ❤️ to make our APIs better, one PR at a time.*

```
API_GOVERNANCE/
├── .spectral.yaml                 # Strict rules (severity: error)
├── .spectral-warn.yaml            # Advisory rules (severity: warn)
├── publish-baseline.yaml          # Pipeline to publish baselines
├── Readme.md                      # This document
├── templates/
│   └── api-governance.yaml        # Master pipeline template
├── scripts/
│   ├── generate_partial_spec.py   # Legacy filter script
│   └── post_spectral_comments.ps1 # Spectral runner & PR commenter
└── baselines/
    └── backend-baseline.json      # Example baseline file
```

---

## Summary

This **Hub & Spoke** architecture enables:

### For Organizations 🏢
- 🎯 **Centralized governance** - One place to manage all API rules across the entire organization
- 🚀 **Zero-downtime adoption** - Doesn't block development on legacy code
- � **Scalable** - Add unlimited projects without duplicating logic
- 📊 **Consistent standards** - Every API follows the same guidelines

### For Developers 👨‍💻👩‍💻
- 📊 **Clear feedback** - Know exactly what to fix, no ambiguity
- ✅ **Not blocked by legacy** - Old technical debt doesn't prevent new features
- 🤖 **Automated** - No manual checks, everything happens in the PR
- 📈 **Visibility into debt** - Warnings show what can be improved over time

### For Governance Teams 🛡️
- 🛡️ **Enforce standards immediately** - New violations are prevented from day one
- 📈 **Gradual improvement** - Legacy code can be fixed incrementally
- 🔧 **Low maintenance** - Update one file to change rules for everyone
- 📉 **Reduced tech debt** - Stops the bleeding while allowing cleanup

### Real-World Impact
**Before:**
- ❌ Inconsistent APIs across 20+ microservices
- ❌ No way to enforce new standards without massive refactoring
- ❌ Developers unsure what "good" looks like
- ❌ Technical debt growing with every new feature

**After:**
- ✅ All new code meets API standards automatically
- ✅ PRs get actionable feedback in seconds
- ✅ Technical debt is visible and can be tracked
- ✅ Standards evolve and propagate instantly

**The result:** Consistent, high-quality APIs across your entire organization without blocking development teams.

---

## Need Help?

- 📧 **Contact:** Reach out to the API Governance team
- 📝 **Issues:** Report problems or suggest improvements
- 🤝 **Contributing:** Want to improve the pipeline? Submit a PR!
- 📚 **Learn More:** Check out [Spectral Documentation](https://docs.stoplight.io/docs/spectral/) for advanced rule authoring

---

*Last Updated: December 2025*