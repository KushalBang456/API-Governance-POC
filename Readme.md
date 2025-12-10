# API Governance: Hub & Spoke Linting Pipeline

> Enforce API standards in GitHub Actions while gracefully managing legacy code

![Status](https://img.shields.io/badge/status-active-success?style=flat-square)
![Architecture](https://img.shields.io/badge/architecture-hub%20%26%20spoke-blue?style=flat-square)
![Tool](https://img.shields.io/badge/tool-Spectral-orange?style=flat-square)
![Platform](https://img.shields.io/badge/platform-GitHub%20Actions-2088FF?style=flat-square)

**Key Features:**
- ✅ **Centralized Rule Management** - Update once, apply everywhere via reusable workflows
- ✅ **Zero Legacy Blockers** - Strict checks on new/modified code, warnings only on legacy
- ✅ **Automated PR Feedback** - Smart PR comments with detailed Job Summary reports
- ✅ **Scalable** - Works for 1 project or 100+ microservices
- ✅ **GitHub Native** - Leverages Actions, Releases, annotations, and PR comments

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
10. [Repository Structure](#repository-structure)

---

## 1. Executive Summary

### The Problem
Organizations face inconsistent API standards creating:
- ❌ Developer onboarding friction
- ❌ Poor consumer experiences
- ❌ Maintenance nightmares
- ❌ Years of legacy code that violates modern standards

### The Challenge
**How do we enforce new API standards *today* without blocking development while teams gradually fix legacy code?**

### The Solution
A **"Hub & Spoke"** GitHub Actions workflow that:

1. ✅ **Blocks New Violations:** PRs fail if *new or modified* code violates strict rules
2. ⚠️ **Reports Legacy Issues:** Legacy code violations generate warnings only (non-blocking)
3. 🎯 **Centralizes Rules:** Single hub repository manages all rules via reusable workflows
4. 🔄 **Smart Diffing:** Compares PR branch vs base branch, filters legacy ops via baseline
5. 📊 **Rich Feedback:** PR comments + GitHub Job Summary with detailed tables

---

## 2. Quick Start

### For Governance Team (Hub Setup)
The Hub is configured in this repository (`KushalBang456/API-Governance-POC`):

| File/Folder | Purpose |
|------------|---------|
| `.spectral.yaml` | Strict rules (severity: `error`) - blocks PRs |
| `.spectral-warn.yaml` | Advisory rules (severity: `warn`) - informational only |
| `.github/workflows/api-governance.yaml` | **Reusable workflow** called by spoke repos (the engine) |
| `.github/workflows/meta-test.yaml` | **Self-test workflow** - validates 8 governance scenarios on every push/PR |
| `scripts/generate_partial_spec.py` | Core filter logic: processes diff + deep comparison, removes legacy ops |
| `baselines/` | Example baseline files (javatest-legacy.yaml, memberdomain-legacy.json) |
| `tests/` | Test fixtures: baseline.yaml (legacy list), main.yaml (base), pr_robust_mix.yaml (8 test scenarios) |

**To add/modify rules:**
1. Edit `.spectral.yaml` (errors) or `.spectral-warn.yaml` (warnings)
2. Commit to `main`
3. All spoke repos automatically use new rules on next run ✨

### For Development Teams (Onboarding a Spoke)
**5-Minute Checklist:**
1. ☑️ Generate baseline OpenAPI spec from your main branch
2. ☑️ Publish baseline to GitHub Release (e.g., tag `baselines-v1`)
3. ☑️ Create `.github/workflows/api-governance.yaml` in your repo (see [example](#spoke-workflow-example))
4. ☑️ Ensure your repo generates `swagger.yaml` (or similar) in CI
5. ☑️ Set up PR branch protection to require the governance check

**Result:** Next PR gets automatic governance validation! 🎉

---

## 3. Hub & Spoke Architecture

### The "Hub" (This Repository: `API-Governance-POC`)

Central governance repository hosting:

| Component | Purpose |
|-----------|---------|
| **`.github/workflows/api-governance.yaml`** | Reusable workflow (`workflow_call`) - the engine |
| **`.spectral.yaml`** | Strict ruleset - all rules set to `severity: error` |
| **`.spectral-warn.yaml`** | Advisory ruleset - same rules, `severity: warn` |
| **`scripts/generate_partial_spec.py`** | Python filter: removes legacy ops, builds minimal spec |
| **`baselines/`** | Example baseline files (YAML/JSON) |
| **Releases** | Stores baseline artifacts (e.g., `javatest-legacy.yaml` under tag `baselines-v1`) |

### The "Spokes" (Your API Projects)

Individual microservice repos call the hub's reusable workflow:

**Spoke Responsibilities:**
1. 🔗 **Call** the hub's reusable workflow via `uses:`
2. 📋 **Pass** parameters: swagger path, baseline filename, release tag
3. 📄 **Generate** OpenAPI spec in CI (e.g., via Swashbuckle, Spring Doc, etc.)
4. 📊 **Receive** PR comments and Job Summary with governance results

**Example Spoke Workflow:** See [Section 6: Onboarding](#spoke-workflow-example)

---

## 4. End-to-End Pull Request Flow

When a developer opens a PR in a spoke repo:

### Step 1: Trigger 🎬
- Developer opens PR modifying an OpenAPI spec (e.g., `swagger.yaml`)
- GitHub triggers the spoke's workflow (on: `pull_request`)

### Step 2: Call Hub Workflow 🔗
```yaml
uses: KushalBang456/API-Governance-POC/.github/workflows/api-governance.yaml@main
```
Control passes to the hub's reusable workflow

### Step 3: Generate Specs 📄
**Hub workflow performs:**
1. **Checkout spoke repo** (with full history)
2. **Extract HEAD version**: Copy `swagger.yaml` → `swagger_head.yaml`
3. **Extract BASE version**: `git show origin/$TARGET_BRANCH:swagger.yaml` → `swagger_main.yaml`
   - Dynamically detects target: `github.base_ref` (PR) or fallback to `main`

### Step 4: Download Baseline 📦
```bash
gh release download baselines-v1 \
  --repo KushalBang456/API-Governance-POC \
  --pattern "javatest-legacy.yaml"
```
Downloads the baseline (legacy operation list) from GitHub Releases

### Step 5: Calculate Delta 🔍
1. **Generate Diff:**
   ```javascript
   // Uses openapi-diff npm package
   diff.diffSpecs({
     sourceSpec: swagger_main.yaml,  // "Before"
     destinationSpec: swagger_head.yaml  // "After"
   }) → diff.json
   ```

2. **Filter Legacy Operations:**
   ```bash
   python governance-hub/scripts/generate_partial_spec.py javatest-legacy.yaml
   ```
   - Loads baseline operations (e.g., `GET@/pet`, `POST@/pet/findByStatus`)
   - **Two-Phase Detection:**
     1. **Diff Processing:** Parses `diff.json` from openapi-diff (structural changes)
     2. **Deep Comparison:** Manual JSON comparison of ALL operations (catches cosmetic changes like descriptions/summaries that diff tools miss)
   - **Decision Logic:**
     - **Ignores** changes to legacy operations (in baseline)
     - **Includes** changes to:
       - New operations on modern paths
       - New methods added to legacy paths (e.g., `PATCH /pet` where `GET /pet` is legacy)
       - Modifications to modern operations
   - **$ref Restoration:** Prevents schema inline expansion by restoring original `$ref` links
   - **Component Pruning:** Rebuilds minimal `components/schemas` via transitive closure (only includes referenced schemas)
   - **Output:** `partial_spec.json` + `partial_spec.yaml` (plus debug output with operation counts)

### Step 6: Two-Pass Linting 🔬

#### **PASS 1: Strict Checks (Errors) ⛔**
```bash
spectral lint partial_spec.json \
  --ruleset governance-hub/.spectral.yaml \
  --output strict.json
```
- Lints **only new/modified code** (partial spec)
- Uses **strict** ruleset (all rules are `severity: error`)
- Violations **block the PR**

#### **PASS 2: Advisory Checks (Warnings) ⚠️**
```bash
spectral lint swagger_head.yaml \
  --ruleset governance-hub/.spectral-warn.yaml \
  --output advisory.json
```
- Lints **entire spec** (including legacy)
- Uses **advisory** ruleset (all rules are `severity: warn`)
- Violations are **informational only** (non-blocking)

### Step 7: Report & Comment 📊
**GitHub Script action processes results:**

1. **Generate Job Summary** (Actions tab):
   - Beautiful markdown tables with severity icons
   - Logical path display (e.g., `paths > /admin/health > get`)
   - Line numbers shown for advisory (hidden for strict)
   
2. **Post PR Comments** (smart update logic):
   - **Strict Check Comment:** "🛑 API Governance: Strict Checks"
     - Shows error/warning counts
     - Links to Job Summary
     - **Updates** existing comment if found (title-based matching)
     - **Creates** new comment only if issues exist
   - **Advisory Check Comment:** "⚠️ API Governance: Advisory Checks"
     - Same smart update logic

3. **GitHub Annotations** (Files Changed tab):
   - Red/yellow indicators on changed files
   - Click to see inline issue details

### Step 8: Pass/Fail Decision ✅❌
- ✅ **Pass:** If strict checks = 0 errors (warnings don't block)
- ❌ **Fail:** If strict checks > 0 errors (PR blocked)

Developer sees:
- **PR Comment:** Concise summary with counts
- **Job Summary:** Detailed tables with rules, locations, messages
- **Files Changed:** Inline annotations
- **Clear Signal:** Whether new code meets standards

---

## 5. Component Deep-Dive

### Component 1: The Reusable Workflow (`.github/workflows/api-governance.yaml`)

**Location:** `KushalBang456/API-Governance-POC/.github/workflows/api-governance.yaml`

**Trigger:** `workflow_call` (reusable workflow pattern)

**Inputs:**
```yaml
inputs:
  swagger_path:
    required: true
    type: string
    description: "Path to swagger file in spoke repo (e.g. swagger.yaml)"
  baseline_filename:
    required: true
    type: string
    description: "Name of baseline file in Release (e.g. javatest-legacy.yaml)"
  baseline_version:
    required: false
    type: string
    default: 'baselines-v1'
    description: "The Release Tag to download from"
```

**Permissions:**
```yaml
permissions:
  contents: read        # Download releases
  pull-requests: write  # Post PR comments
```

**Workflow Steps:**

| Step | Action | Purpose |
|------|--------|---------|
| 1 | Checkout Spoke Repo | Clone the calling repo with full history (`fetch-depth: 0`) |
| 2 | Checkout Hub Repo | Clone governance hub to `governance-hub/` path |
| 3 | Setup Node & Python | Install Node 18, Python 3.x |
| 4 | Install Dependencies | `npm install openapi-diff`, `npm install -g @stoplight/spectral-cli`, `pip install PyYAML` |
| 5 | Prepare Specs | Copy HEAD spec, extract BASE spec via `git show origin/$TARGET_BRANCH` |
| 6 | Download Baseline | `gh release download` from hub repo releases |
| 7 | Generate Diff | Run `openapi-diff` inline Node script → `diff.json` |
| 8 | Generate Partial Spec | `python governance-hub/scripts/generate_partial_spec.py baseline.yaml` → `partial_spec.json` |
| 9 | Strict Lint | `spectral lint partial_spec.json --ruleset .spectral.yaml` → `strict.json` |
| 10 | Advisory Lint | `spectral lint swagger_head.yaml --ruleset .spectral-warn.yaml` → `advisory.json` |
| 11 | Generate Report & PR Comments | GitHub Script: build tables, post/update PR comments, create annotations |

**Key Features:**
- **Dynamic Target Detection:** Uses `github.base_ref` for PRs, falls back to `main` for manual runs
- **Smart PR Comments:** Title-based matching to update existing comments vs. create new ones
- **Dual Reporting:** Job Summary (Actions tab) + PR Comments + File annotations
- **Debug Mode:** Optional steps print diff.json and partial_spec.json to workflow logs

---

### Component 1b: The Meta-Test Workflow (`.github/workflows/meta-test.yaml`)

**Purpose:** Self-validating test suite that runs on every push/PR to verify governance logic

**Trigger:** `push`, `pull_request`, `workflow_dispatch` (manual)

**Test Strategy: 8 Robust Scenarios**

The meta-test uses three fixture files to validate all governance edge cases:

| Fixture | Purpose |
|---------|--------|
| `tests/baseline.yaml` | Legacy operation list (3 operations: `PUT@/pet`, `POST@/pet`, `GET@/pet/findByStatus`) |
| `tests/main.yaml` | "Before" state (base branch) - includes legacy + some modern APIs |
| `tests/pr_robust_mix.yaml` | "After" state (PR branch) - includes 8 specific test scenarios |

**The 8 Test Scenarios:**

```python
# TC1: Legacy API Unchanged
check('/pet', 'get', False, 1)
# GET /pet exists in baseline, no changes → ABSENT from partial spec

# TC2: Legacy API Modified  
check('/pet/findByStatus', 'get', False, 2)
# GET /pet/findByStatus in baseline, description modified → ABSENT (ignored)

# TC3: Legacy Path, New Method
check('/pet/findByStatus', 'patch', True, 3)
# PATCH /pet/findByStatus is NEW method on legacy path → PRESENT

# TC4: Modern API Unchanged
check('/store/inventory', 'get', False, 4)
# GET /store/inventory exists in main.yaml, no changes → ABSENT

# TC5: Modern API, New Method
check('/store/order', 'put', True, 5)
# PUT /store/order is NEW method on modern path → PRESENT

# TC6: Modern API Modified
check('/store/order/{orderId}', 'delete', True, 6)
# DELETE /store/order/{orderId} was modified → PRESENT

# TC7: Completely New API
check('/products', 'post', True, 7)
# POST /products doesn't exist in main.yaml → PRESENT

# TC8: Deep-Ref Test
check('/inventory/check', 'get', True, 8)
# GET /inventory/check uses complex nested schemas → PRESENT
# Validates transitive closure (component pruning) works
```

**Workflow Steps:**

1. **Setup Environment** - Checkout hub, setup Node/Python, install dependencies
2. **Generate Test Diff** - Run openapi-diff on `main.yaml` vs `pr_robust_mix.yaml`
3. **Run Generator Script** - Execute `generate_partial_spec.py` with `tests/baseline.yaml`
4. **Python Assertions** - Built-in Python script validates ALL 8 test cases:
   ```python
   def check(path, method, should_exist, test_case):
       exists = path in paths and method in paths[path]
       if exists != should_exist:
           print(f'❌ FAILED: Test Case {test_case} failed!')
           sys.exit(1)  # Fail the workflow
   ```
5. **Spectral Validation** - Run Spectral on partial spec to ensure it's valid OpenAPI
6. **Process Results** - Python script generates Job Summary with results table (no line numbers shown for temp spec)

**What Gets Validated:**
- ✅ Legacy operations are correctly ignored (TC1, TC2)
- ✅ New methods on legacy paths are included (TC3)
- ✅ Unchanged modern operations are absent (TC4)
- ✅ New methods on modern paths are included (TC5)
- ✅ Modified modern operations are included (TC6)
- ✅ Completely new operations are included (TC7)
- ✅ Deep schema references work correctly (TC8)
- ✅ Partial spec is valid OpenAPI 3.0
- ✅ Component pruning includes all required schemas

**Success Criteria:**
```
=== LEGACY API CHECKS (in baseline.yaml) ===
✅ TC1: GET    /pet                         ABSENT   (Expected: ABSENT)
✅ TC2: GET    /pet/findByStatus            ABSENT   (Expected: ABSENT)
✅ TC3: PATCH  /pet/findByStatus            PRESENT  (Expected: PRESENT)

=== MODERN API CHECKS (added after baseline) ===
✅ TC4: GET    /store/inventory             ABSENT   (Expected: ABSENT)
✅ TC5: PUT    /store/order                 PRESENT  (Expected: PRESENT)
✅ TC6: DELETE /store/order/{orderId}       PRESENT  (Expected: PRESENT)

=== NEW API CHECKS (not in main.yaml) ===
✅ TC7: POST   /products                    PRESENT  (Expected: PRESENT)
✅ TC8: GET    /inventory/check             PRESENT  (Expected: PRESENT)

✅ ALL TEST CASES PASSED!
```

**Why This Matters:**
- Validates governance logic on every code change
- Prevents regressions in filter logic
- Documents expected behavior through executable tests
- Builds confidence in the system
- Serves as living documentation of edge cases

---

### Component 2: The Python Filter (`scripts/generate_partial_spec.py`)

**Purpose:** Core logic to separate new/modern code from legacy code using **dual-phase detection**

**How It Works:**

1. **Load Baseline Operations:**
   ```python
   def load_baseline_operations(baseline_path: Path) -> set:
       # Reads baseline file (YAML/JSON via smart loader)
       # Extracts all HTTP methods: get, put, post, delete, patch, options, head, trace
       # Returns: {'GET@/pet', 'POST@/pet', 'GET@/pet/findByStatus', ...}
   ```
   - Builds a `set` of legacy operation keys: `METHOD@/path`
   - Example: `{'GET@/pet', 'POST@/pet/findByStatus', 'PUT@/pet'}`
   - Prints each legacy operation for debugging

2. **Dual-Phase Change Detection:**

   **PHASE 1: Trust the Diff Tool (Fast)**
   ```python
   # Parses diff.json structure:
   # - breakingDifferences
   # - nonBreakingDifferences  
   # - unclassifiedDifferences
   # Extracts operation keys from sourceSpecEntityDetails/destinationSpecEntityDetails
   ```
   - Processes structural changes detected by openapi-diff
   - Captures path modifications, new endpoints, schema changes
   - Fast but may miss cosmetic changes

   **PHASE 2: Manual Deep Comparison (Comprehensive)**
   ```python
   def detect_manual_changes(source_spec: dict, dest_spec: dict, affected_ops: set):
       # Compares Source (main) vs Destination (head) operation-by-operation
       # Converts to JSON strings for stable comparison
       # Catches: description changes, summary changes, example changes, etc.
       if json.dumps(op, sort_keys=True) != json.dumps(source_op, sort_keys=True):
           affected_ops.add(op_key)  # Detected MODIFIED
   ```
   - Compares ALL operations in destination vs source
   - Uses JSON string comparison (catches ANY difference)
   - Detects description/summary changes that diff tools miss
   - Identifies completely new operations not in source

3. **Governance Decision Logic:**
   ```python
   for key in sorted(affected_ops):
       if key in legacy_operations:
           print(f"❌ IGNORE: {key} - Legacy operation (in baseline)")
           # Skip - will only generate warnings in Pass 2
       else:
           print(f"✅ INCLUDE: {key} - Modern/new operation")
           copy_operation_from_dest(new_spec, dest_spec, key)
   ```

4. **Build Partial Spec:**
   - Starts with empty OpenAPI 3.0 skeleton
   - Copies **only non-legacy operations** to `paths`
   - **Critical:** Restores original `$ref` responses/requestBodies from HEAD spec
     - Prevents inline schema expansion (keeps spec clean)
     - Ensures schemas remain reusable
     - Example: `$ref: '#/components/schemas/User'` instead of inline `{type: object, properties: {...}}`

5. **Component Pruning (Transitive Closure):**
   ```python
   def build_required_components(new_spec: dict, base_spec: dict):
       # Finds all $ref references in included paths
       # Recursively resolves schema dependencies
       # Example: UserResponse → User → Address → Country
       # Builds minimal components/schemas with ONLY what's referenced
   ```
   - Scans all included operations for `$ref` strings
   - Queue-based algorithm: follow refs → find nested refs → repeat
   - Copies schemas from base spec only if referenced
   - Handles circular references gracefully
   - Prints final count: "Pruned components. Kept X total referenced components"

6. **Output Files:**
   - `partial_spec.json` - For Spectral strict linting (Pass 1)
   - `partial_spec.yaml` - Human-readable format
   - Console logs with statistics:
     ```
     ✅ SUCCESS!
        Output: partial_spec.json
        Paths: 5
        Operations: 8
     ```

**Key Algorithm:**
```python
if operation_key in legacy_operations:
    print("❌ IGNORE: {key} - Legacy operation")
    # Skip - will only get warnings in Pass 2, not errors
else:
    print("✅ INCLUDE: {key} - Modern/new operation")
    copy_operation_to_partial_spec()
    # Will get strict error checking in Pass 1
```

**Special Cases Handled:**
- **New method on legacy path:** `PATCH /pet` where `GET /pet` exists in baseline → **INCLUDED** (different method)
- **Modified legacy operation:** `GET /pet` with description change → **IGNORED** (in baseline)
- **New operation:** `POST /products` not in baseline → **INCLUDED**
- **Deep-ref schemas:** Product → Category → Tag → Metadata all included automatically via transitive closure
- **Unchanged operations:** Not in diff, not in deep compare → **ABSENT** from partial spec

**Why This Matters:**
- **Phase 1 (Diff)** catches structural API changes quickly
- **Phase 2 (Deep Compare)** catches documentation/cosmetic changes that diff tools miss
- **Combined approach** ensures comprehensive governance coverage
- **$ref restoration** keeps specs maintainable and prevents Spectral false positives
- **Transitive closure** ensures valid partial specs with all required schemas

---
### Component 3: GitHub Script Reporting (`.github/workflows/api-governance.yaml` step 11)

**Purpose:** Process Spectral results and create beautiful reports + PR comments

**Features:**

#### 1. **Load Results:**
```javascript
const strictResults = loadResults('strict.json');
const advisoryResults = loadResults('advisory.json');
```

#### 2. **Generate Job Summary Table:**
- Markdown table with severity icons (🛑 ⚠️)
- Logical path display: `paths > /admin/health > get`
- Line numbers hidden for strict (temp spec), shown for advisory (real spec)
- Automatically posted to Actions tab

**Example:**
```markdown
### 🛑 Strict Checks (New Code) (5 issues)

| Severity | Rule | Location | Message |
| :---: | :--- | :--- | :--- |
| 🛑 | **path-versioning** | `paths > /members > get` | Path '/members' must start with /v<number>/ |
```

#### 3. **Smart PR Comment Logic:**
```javascript
const STRICT_TITLE = "🛑 API Governance: Strict Checks";
const ADVISORY_TITLE = "⚠️ API Governance: Advisory Checks";

// Find existing comments by TITLE (body contains title)
const existingComment = comments.find(c => c.body.includes(TITLE));

if (existingComment) {
  github.rest.issues.updateComment(...);  // UPDATE
} else if (issuesFound > 0) {
  github.rest.issues.createComment(...);  // CREATE
} else {
  // Stay silent on success if no previous comment
}
```

**Benefits:**
- ✅ No comment spam (updates existing)
- ✅ Shows green status when issues fixed
- ✅ Silent on first success
- ✅ Two distinct comments (strict vs advisory)

#### 4. **GitHub Annotations:**
```javascript
if (isError) {
  core.error(message, { title: ruleCode, file: 'swagger.yaml', startLine: line });
} else {
  core.warning(message, { title: ruleCode, file: 'swagger.yaml', startLine: line });
}
```
- Shows inline on "Files Changed" tab
- Red for errors, yellow for warnings

---

### Component 4: Spectral Rulesets

**`.spectral.yaml` (Strict - Blocks PRs):**
```yaml
rules:
  path-camel-case:
    severity: error  # ❌ BLOCKS
  path-versioning:
    severity: error
  require-json-body:
    severity: error
```

**`.spectral-warn.yaml` (Advisory - Informational):**
```yaml
rules:
  path-camel-case:
    severity: warn  # ⚠️ INFORMS
  path-versioning:
    severity: warn
  require-json-body:
    severity: warn
```

**Rule Examples:**
- `path-camel-case`: Paths must be camelCase (e.g., `/userProfile` not `/user_profile`)
- `parameter-naming-camelCase`: Params match `^[a-z][a-zA-Z0-9]*$`
- `path-versioning`: Paths start with `/v[0-9]+/`
- `response-envelope-has-code-and-data`: 2xx responses have top-level `code` and `data` properties
- `no-content-response-no-body`: 204 responses must not have body

---

## 6. Onboarding a New Project

### Step 1: Generate Baseline 📸

Create a baseline from your **current main/master branch**:

```bash
# Example for Java/Spring Boot
./mvnw spring-boot:run -Dspring-boot.run.arguments="--springdoc.api-docs.enabled=true"
curl http://localhost:8080/v3/api-docs.yaml > javatest-legacy.yaml

# Example for .NET
dotnet swagger tofile --output swagger-baseline.yaml bin/Debug/net8.0/MyAPI.dll v1
```

This baseline represents your "legacy" operations that will only generate warnings.

---

### Step 2: Publish Baseline to GitHub Release 📦

Create a release in the **Hub repository** (API-Governance-POC):

```bash
# Tag and create release
git tag baselines-v1
git push origin baselines-v1

# Upload baseline file via GitHub UI or CLI
gh release create baselines-v1 javatest-legacy.yaml \
  --repo KushalBang456/API-Governance-POC \
  --title "Baselines v1" \
  --notes "Initial baseline files for legacy operations"
```

**Tip:** You can add multiple baseline files to the same release (one per project).

---

### Step 3: Create Spoke Workflow 🔧

<a name="spoke-workflow-example"></a>

In your project repo, create `.github/workflows/api-governance.yaml`:

```yaml
name: API Governance

on:
  pull_request:
    paths:
      - 'swagger.yaml'  # Or wherever your OpenAPI spec lives
      - 'src/**'        # Trigger on source changes too

jobs:
  validate-api:
    name: \ud83d\uded1 API Governance Check
    uses: KushalBang456/API-Governance-POC/.github/workflows/api-governance.yaml@main
    with:
      swagger_path: 'swagger.yaml'           # Path in YOUR repo
      baseline_filename: 'javatest-legacy.yaml'  # Filename in Release
      baseline_version: 'baselines-v1'       # Release tag
    permissions:
      contents: read
      pull-requests: write
```

**Parameters:**
- `swagger_path`: Path to OpenAPI spec in your repo (e.g., `api/swagger.yaml`, `openapi.json`)
- `baseline_filename`: Exact filename from the GitHub Release
- `baseline_version`: Release tag (default: `baselines-v1`)

---

### Step 4: Generate OpenAPI Spec in CI \ud83d\udce1

Ensure your build process generates the OpenAPI spec **before** the governance workflow runs.

**Important:** The workflow expects the spec file to already exist at `swagger_path` when it starts.

**Option A: Spec Already Committed** - If `swagger.yaml` is version-controlled, no extra steps needed.

**Option B: Generate in CI** - Create the spec before calling the governance workflow.

**Example for Spring Boot:**
```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
      
      # Build and generate spec
      - run: ./mvnw clean package spring-boot:run &
      - run: sleep 10  # Wait for startup
      - run: curl http://localhost:8080/v3/api-docs.yaml > swagger.yaml
```

**Example for .NET:**
```yaml
      - run: dotnet build
      - run: dotnet swagger tofile --output swagger.yaml bin/Debug/net8.0/MyAPI.dll v1
      # Spec now exists at swagger.yaml, ready for governance workflow
```

**Note:** You don't need to commit the generated spec back to the repo. The workflow reads it from the workspace filesystem.

---

### Step 5: Enable Branch Protection \ud83d\udd12

Configure branch protection on your main branch:

1. Go to **Settings** → **Branches** → **Branch protection rules**
2. Add rule for `main` (or your default branch)
3. **Require status checks to pass:**
   - Check: "\ud83d\uded1 API Governance Check"
4. **Save**

Now PRs cannot merge until governance checks pass!

---

### Step 6: Test It! \ud83e\uddea

1. Create a branch with an API change
2. Open a PR
3. Watch the governance workflow run
4. See PR comments, Job Summary, and annotations

**Expected Behavior:**
- \u2705 **Pass:** If your new code meets standards
- \u274c **Fail:** If new code violates rules (legacy violations only warn)
- \ud83d\udcac **PR Comments:** Two comments (strict + advisory)
- \ud83d\udcc4 **Job Summary:** Detailed tables in Actions tab
- \ud83d\udccd **Annotations:** Inline on Files Changed tab

---

## 7. Maintenance & Benefits

### For the Governance Team 🎯

**Adding/Updating Rules:**
1. Edit `.spectral.yaml` (strict) or `.spectral-warn.yaml` (advisory) in hub repo
2. Commit to `main`
3. ✨ **Instantly applied** to all spoke repos on next workflow run

**No need to:**
- ❌ Update dozens of spoke repos
- ❌ Coordinate deployments
- ❌ Train teams on changes

**Updating Baselines:**
1. Generate new spec from updated base branch
2. Upload to existing GitHub Release (or create new version tag)
3. Next PR uses updated baseline automatically

### For Developers 👨‍💻👩‍💻

**Clear Feedback:**
- ⛔ **Errors:** Issues in *new code* that **BLOCK** merge
- ⚠️ **Warnings:** Issues in *legacy code* (informational only)
- 📊 **Three report locations:**
  1. PR comments (concise)
  2. Job Summary (Actions tab - detailed tables)
  3. Files Changed (inline annotations)

**Benefits:**
- ✅ Know exactly what to fix
- ✅ Not blocked by legacy tech debt
- ✅ Consistent standards org-wide
- ✅ No comment spam (updates existing)

---

## 8. Current API Standards

| Rule | Description | Strict (New Code) | Advisory (All Code) |
|------|-------------|-------------------|---------------------|
| `path-camel-case` | Path segments must be camelCase | ❌ Error | ⚠️ Warning |
| `parameter-naming-camelCase` | Parameters match `^[a-z][a-zA-Z0-9]*$` | ❌ Error | ⚠️ Warning |
| `path-versioning` | Paths start with `/v[0-9]+/` | ❌ Error | ⚠️ Warning |
| `tag-pascal-case` | Tags should be PascalCase | ⚠️ Warning | ⚠️ Warning |
| `require-json-body` | Responses include `application/json` | ❌ Error | ⚠️ Warning |
| `response-envelope-has-code-and-data` | 2xx responses have `code` and `data` | ❌ Error | ⚠️ Warning |
| `common-response-has-code` | CommonResponse has `code` property | ❌ Error | ⚠️ Warning |
| `common-response-has-data` | CommonResponse has `data` property | ❌ Error | ⚠️ Warning |
| `no-content-response-no-body` | 204 responses must not have body | ❌ Error | ⚠️ Warning |

---

## 9. Troubleshooting

### GitHub Release not found
**Error:** `Release not found` or baseline download fails

**Solution:**
```bash
# Verify release exists
gh release list --repo KushalBang456/API-Governance-POC

# Verify file in release
gh release view baselines-v1 --repo KushalBang456/API-Governance-POC

# Check permissions
# Ensure GITHUB_TOKEN has read access to releases
```

### Workflow permission denied
**Error:** `Resource not accessible by integration`

**Solution:**
- Add `permissions:` block to spoke workflow:
  ```yaml
  permissions:
    contents: read
    pull-requests: write
  ```

### PR comments not posting
**Symptom:** Workflow runs but no comments appear

**Solution:**
- Check PR context: `if (!context.issue.number)` fails on non-PR runs
- Verify `pull-requests: write` permission exists
- Check GitHub Script logs for API errors

### Baseline operations not being ignored
**Error:** Legacy endpoints triggering strict errors

**Solution:**
- Verify baseline file format (YAML/JSON valid)
- Check operation keys match: `METHOD@/path` (case-sensitive)
- Review Python script logs: "IGNORE: GET@/pet"
- Ensure `baseline_filename` parameter matches exactly

### openapi-diff produces no changes
**Symptom:** `diff.json` is empty but changes exist

**Solution:**
- Verify specs are valid OpenAPI 3.0
- Check `swagger_main.yaml` and `swagger_head.yaml` both exist
- Ensure changes are structural (not just whitespace/comments)
- Add new param/response to trigger diff reliably

### Spectral errors on valid spec
**Error:** Schema validation fails on partial spec

**Solution:**
- Check `build_required_components()` ran successfully
- Verify all `$ref` schemas copied from HEAD spec
- Look for "Pruned components. Kept X schemas" in logs
- Ensure original spec has valid `components/schemas` section

### Branch protection not triggered
**Symptom:** Governance workflow doesn't block merge

**Solution:**
1. Settings → Branches → Branch protection rules
2. Add rule for base branch
3. **Require status checks:**
   - Select "🛑 API Governance Check" (exact job name)
4. **Save changes**

---

## 10. Repository Structure

```
API-Governance-POC/  (Hub Repo)
├── .github/
│   └── workflows/
│       ├── api-governance.yaml       # Reusable workflow (the engine)
│       └── meta-test.yaml            # Self-test workflow
├── scripts/
│   ├── generate_partial_spec.py      # Python filter (core logic)
│   └── post_spectral_comments.ps1    # Legacy PowerShell script (reference)
├── tests/                             # Test fixtures
│   ├── baseline.yaml                  # Example legacy operations list
│   ├── main.yaml                      # Source spec (base)
│   └── pr_robust_mix.yaml            # PR spec (head) - 8 test scenarios
├── baselines/                         # Example baselines
│   ├── javatest-legacy.yaml
│   └── memberdomain-legacy.json
├── available-baselines/               # More examples
│   └── backend-baseline.json
├── .spectral.yaml                     # Strict rules (severity: error)
├── .spectral-warn.yaml                # Advisory rules (severity: warn)
├── publish-baseline.yaml              # **LEGACY:** Azure DevOps pipeline example (reference only)
└── Readme.md                          # This file

GitHub Releases (baselines-v1):
├── javatest-legacy.yaml
├── memberdomain-legacy.json
└── ... (other baseline files)
```

**Spoke Repo Structure:**
```
Your-API-Project/  (Spoke Repo)
├── .github/
│   └── workflows/
│       └── api-governance.yaml       # Calls hub workflow
├── src/                               # Your API source code
├── swagger.yaml                       # Generated OpenAPI spec
└── ... (other project files)
```

---

## Key Concepts

### Baseline
Snapshot of API operations at a point in time (legacy list). Operations in baseline only generate warnings, never errors.

**Format:** OpenAPI 3.0 spec (YAML/JSON) with `paths` section.

### Partial Spec
Dynamically generated OpenAPI containing **only non-legacy operations**. Created by:
1. Diff between base and head
2. Filter out legacy operations
3. Rebuild minimal components

**Purpose:** Lint new/modified code without legacy noise.

### Reusable Workflow
GitHub Actions feature (`workflow_call`) allowing spokes to call hub logic:
```yaml
uses: KushalBang456/API-Governance-POC/.github/workflows/api-governance.yaml@main
```

### Two-Pass Linting
1. **Strict:** Partial spec + `.spectral.yaml` → **errors block PR**
2. **Advisory:** Full spec + `.spectral-warn.yaml` → **warnings only**

---

*Last Updated: December 2024*
*Platform: GitHub Actions*
*Hub Repository: [`KushalBang456/API-Governance-POC`](https://github.com/KushalBang456/API-Governance-POC)*
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
2. Re-upload to GitHub Release with the same asset name (tag: `baselines-v1`)
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
- 🔄 **SARIF Output Support** - Generate SARIF files for better GitHub integration
  - Code scanning integration with GitHub Security
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
