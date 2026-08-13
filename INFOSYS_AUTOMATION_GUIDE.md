# 📘 Infosys Springboard Automation — Complete Technical & User Guide

A comprehensive architectural overview, installation guide, API reference, and usage guide for the **Infosys Springboard Course Automation Toolkit**.

---

## 📑 Table of Contents
1. [Overview & Core Architecture](#-overview--core-architecture)
2. [Directory & File Structure](#-directory--file-structure)
3. [Authentication & Token Sync](#-authentication--token-sync)
4. [Deep-Dive into Components](#-deep-dive-into-components)
   - [1. Configuration & Headers (`infosys/config.py`)](#1-configuration--headers-infosysconfigpy)
   - [2. Authenticated HTTP Client (`infosys/client.py`)](#2-authenticated-http-client-infosysclientpy)
   - [3. Course Hierarchy Reader (`infosys/course_reader.py`)](#3-course-hierarchy-reader-infosyscoursereaderpy)
   - [4. Completion Engine (`infosys/completer.py`)](#4-completion-engine-infosyscompleterpy)
   - [5. Automated Token Scraper (`sync_token.py`)](#5-automated-token-scraper-synctokenpy)
5. [Step-by-Step Usage Guide](#-step-by-step-usage-guide)
6. [API & Telemetry Reference](#-api--telemetry-reference)
7. [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🚀 Overview & Core Architecture

**Infosys Springboard** (powered by Infosys Wingspan / EkStep platform) tracks learner progress across complex nested course hierarchies. 

This automation tool bypasses heavy web UI rendering and communicates directly with Wingspan's underlying microservice APIs to:
1. **Fetch & Parse** full learning paths (modules, videos, web pages, documents, assessments).
2. **Execute Progress Calculations** directly in the backend database (`/progress/v1/progress/calculate`) at high speed (~0.02s per item).
3. **Trigger Real-Time Aggregation** (`/progress/v1/progress/recalculate`) to instantly reflect 100% completion on your official user profile.

```
       ┌────────────────────────┐
       │   Springboard UI       │
       │ (infyspringboard...)   │
       └───────────┬────────────┘
                   │ Chrome CDP Debugging (Port 9222)
                   ▼
       ┌────────────────────────┐
       │     sync_token.py      │
       │ (Extracts JWT & WID)   │
       └───────────┬────────────┘
                   │ Writes credentials
                   ▼
       ┌────────────────────────┐
       │ ~/.infosys-course/     │
       │       config.json      │
       └───────────┬────────────┘
                   │ Loaded by
                   ▼
┌──────────────────────────────────────┐
│        Infosys Automation CLI        │
│          (run.py / main.py)          │
└─────┬──────────────────────────┬─────┘
      │                          │
      ▼ Hierarchy API            ▼ Progress API
┌──────────────────┐       ┌──────────────────────┐
│  Course Reader   │       │  Completer Engine    │
│  (/level/{id}/2) │       │ (/progress/calculate)│
└──────────────────┘       └──────────────────────┘
```

---

## 📁 Directory & File Structure

```
infosys-automation/
├── INFOSYS_AUTOMATION_GUIDE.md # Master Technical & User Guide (this file)
├── README.md                   # Concise quickstart overview
├── config.example.json         # Template configuration file
├── requirements.txt            # Python dependencies (httpx, loguru, click, websocket-client)
├── run.py                      # Primary CLI entry point
├── sync_token.py               # Chrome/Edge CDP token extraction utility
└── infosys/                    # Core Python package
    ├── __init__.py             # Package initializer
    ├── client.py               # Authenticated HTTP client & telemetry validator
    ├── completer.py            # Progress calculation & course recalculation engine
    ├── config.py               # Configuration loader & request header generator
    ├── course_reader.py        # Hierarchy tree builder & URL parser
    └── main.py                 # CLI interface & command orchestrator
```

---

## 🔑 Authentication & Token Sync

Infosys Springboard uses Keycloak JWT tokens for authentication. The token and user identifier (`wid`) must be passed in HTTP request headers.

### Method A: Automated Token Sync (Recommended)

1. **Start Chrome or Edge with Remote Debugging Enabled**:
   - **Windows (Chrome)**:
     ```powershell
     & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\chrome-debug
     ```
   - **Windows (Edge)**:
     ```powershell
     & "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir=C:\edge-debug
     ```
   - **Mac / Linux (Chrome)**:
     ```bash
     google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
     ```

2. **Log in to Springboard**:
   Open `https://infyspringboard.onwingspan.com` in the newly launched browser window and log in.

3. **Run the Sync Command**:
   ```bash
   python sync_token.py
   ```
   *The script connects via WebSocket (CDP) on port 9222, reads `localStorage`, decodes the JWT payload, extracts your `wid`, and writes everything to `~/.infosys-course/config.json`.*

---

### Method B: Manual Configuration

Create or edit `~/.infosys-course/config.json`:

```json
{
  "base_url": "https://infyspringboard.onwingspan.com",
  "root_org": "infosysheadstart",
  "org": "infosysheadstart",
  "auth": {
    "auth-token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIs...",
    "wid": "your-user-uuid-wid-here"
  }
}
```

> **Where to find manual values**:
> - Open DevTools (`F12`) on Springboard → **Application** tab → **Local Storage** → search for `kc` (token) and `wid`.

---

## 🛠️ Deep-Dive into Components

### 1. Configuration & Headers ([`infosys/config.py`](file:///c:/infosys-automation/infosys/config.py))

- **Config Path**: Stores configuration at `Path.home() / ".infosys-course" / "config.json"`.
- **Header Generation**:
  - `get_headers(auth)`: Configures essential headers required by the backend API:
    - `Authorization`: `Bearer <auth-token>`
    - `wid`: User WID
    - `rootOrg` / `org`: `infosysheadstart` (critical routing identifier)
    - `hostpath`: `infyspringboard.onwingspan.com`
  - `get_telemetry_headers(auth)`: Supplies specialized camelCase headers (`rootOrg`, `dataType`, `origin`) for telemetry heartbeats.

---

### 2. Authenticated HTTP Client ([`infosys/client.py`](file:///c:/infosys-automation/infosys/client.py))

- `InfosysClient`: Wraps `httpx.Client` with automatic retries, custom headers, and status code handling (200/201/204 success, 401 token expiration warning, 403 authorization error).
- `verify_auth()`: Dual-stage validation:
  1. Decodes JWT payload locally to verify signature format and expiration timestamp (`exp`).
  2. Sends an online heartbeat ping to `/api-gw/wn-apis/infosysheadstart/lex-sb-telemetry/v1/telemetry`.

---

### 3. Course Hierarchy Reader ([`infosys/course_reader.py`](file:///c:/infosys-automation/infosys/course_reader.py))

- `ContentNode`: Dataclass modeling each node in the course graph (`identifier`, `name`, `content_type`, `mime_type`, `children`).
- `collect_leaves(node)`: Recursive function extracting all non-collection leaf nodes (actual learnable items).
- `CourseReader`:
  - Primary API: `/api-gw/wn-apis/infosysheadstart/hierarchy-service/level/{course_id}/2`
  - Fallback API: `/apis/proxies/v8/content/v3/hierarchy/{course_id}`
  - `resolve_id_from_url(url)`: Extracts `lex_auth_...` identifiers from full URLs (handling `/toc/`, `/viewer/`, and `collectionId=` query params).

---

### 4. Completion Engine ([`infosys/completer.py`](file:///c:/infosys-automation/infosys/completer.py))

- **Filtering**: Skips proctored exams and interactive quiz archives (`application/vnd.ekstep.quiz-archive`, `application/iap-assessment`, etc.) to prevent invalid submission calls.
- **Progress Calculation**:
  - Endpoint: `POST /api-gw/wn-apis/infosysheadstart/progress/v1/progress/calculate`
  - Header: `x-wingspan-caller: wingspan`
  - Payload:
    ```json
    {
      "contentId": "<leaf_identifier>",
      "userId": "<wid>",
      "maxSize": 1,
      "visited": [1],
      "progress": 100,
      "completionPercentage": 100
    }
    ```
- **Course Progress Recalculation**:
  - Endpoint: `POST /api-gw/wn-apis/infosysheadstart/progress/v1/progress/recalculate`
  - Payload: `{"contentId": "<course_id>", "userId": "<wid>"}`
  - Recalculates aggregate percentage for the course root.

---

### 5. Automated Token Scraper ([`sync_token.py`](file:///c:/infosys-automation/sync_token.py))

- Connects to Chrome DevTools Protocol at `http://127.0.0.1:9222/json`.
- Locates active `infyspringboard.onwingspan.com` tab.
- Evaluates JavaScript via WebSocket (`Runtime.evaluate`) across standard Keycloak storage keys (`kc`, `keycloak`, `user-token`).
- Extracts token, decodes JWT claims, and updates `~/.infosys-course/config.json`.

---

## 💻 Step-by-Step Usage Guide

### Step 1: Install Dependencies
```powershell
py -m pip install -r requirements.txt
```

### Step 2: Open Chrome & Sync Token
1. Close all open Chrome windows, then run this command to start Chrome with remote debugging:
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\chrome-debug
   ```
2. Log into [Infosys Springboard](https://infyspringboard.onwingspan.com) in the new Chrome window.
3. Sync your token:
   ```powershell
   py sync_token.py
   ```

### Step 3: Run Course Completion
Run the auto-completer by pasting your course URL:
```powershell
py run.py "https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_012760837643722752345_shared/overview"
```

---

## 📡 API & Telemetry Reference

| Operation | Method | Endpoint Path | Description |
|---|---|---|---|
| **Telemetry Heartbeat** | `POST` | `/api-gw/wn-apis/infosysheadstart/lex-sb-telemetry/v1/telemetry` | Auth verification ping |
| **Fetch Hierarchy** | `GET` | `/api-gw/wn-apis/infosysheadstart/hierarchy-service/level/{id}/2` | Parses course tree & modules |
| **Calculate Item Progress** | `POST` | `/api-gw/wn-apis/infosysheadstart/progress/v1/progress/calculate` | Marks individual leaf node as 100% complete |
| **Recalculate Course** | `POST` | `/api-gw/wn-apis/infosysheadstart/progress/v1/progress/recalculate` | Aggregates progress for full course |

---

## ❓ Troubleshooting & FAQs

### 1. `401 Unauthorized` Error
- **Cause**: JWT token has expired (tokens typically expire after a few hours).
- **Fix**: Open Springboard in Chrome and re-run `py sync_token.py`.

### 2. `Cannot connect to browser debugger at http://127.0.0.1:9222/json`
- **Cause**: Chrome is not running with `--remote-debugging-port=9222`.
- **Fix**: Close all Chrome instances and launch Chrome using the command provided in [Step 2](#step-2-open-chrome--sync-token).

### 3. `403 Forbidden` Error
- **Cause**: Missing or incorrect `rootOrg` / `org` headers.
- **Fix**: Ensure `config.json` contains `"root_org": "infosysheadstart"` and `"org": "infosysheadstart"`.

---
*Created for Infosys Springboard Automation Toolkit.*
