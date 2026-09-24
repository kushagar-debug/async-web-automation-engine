# 🚀 Project Master Guide & Session Handoff

> **Saved Date**: September 25, 2026  
> **Repository**: [github.com/kushagar-debug/async-web-automation-engine](https://github.com/kushagar-debug/async-web-automation-engine)  
> **Author**: Kushagar Rayat ([@kushagar-debug](https://github.com/kushagar-debug))  
> **Status**: 🟢 Production Ready & GitHub Actions CI Passing

---

## 📑 Table of Contents

1. [Session Summary & What We Achieved](#1-session-summary--what-we-achieved)
2. [Architecture of `async-web-automation-engine`](#2-architecture-of-async-web-automation-engine)
3. [Your Interview Cheatsheet (DevOps & Backend)](#3-your-interview-cheatsheet-devops--backend)
4. [Git & GitHub Commands Reference](#4-git--github-commands-reference)
5. [The Real CI/CD Debugging Story (STAR Method)](#5-the-real-cicd-debugging-story-star-method)
6. [Tomorrow's Blueprint: LinkedIn-to-Telegram Job Sentinel](#6-tomorrows-blueprint-linkedin-to-telegram-job-sentinel)

---

## 1. Session Summary & What We Achieved

Tonight we transformed a local script into an **enterprise-grade, production-ready open-source engine**:

* **Sanitized & Decoupled Secrets**: Completely purged all hardcoded URLs, platform names, and tokens. Abstracted everything into a 12-factor `pydantic-settings` module (`config/settings.py`) with a documented `.env.example`.
* **AsyncIO & Playwright Core**: Rebuilt the automation pipeline around `asyncio` and `httpx.AsyncClient` with connection pooling, bounded concurrency (`asyncio.Semaphore`), and Playwright async APIs.
* **Resilient Retries**: Implemented `@async_exponential_backoff` with randomized jitter and a stateful circuit breaker to eliminate thundering herds.
* **SPA DOM Stabilization**: Created `DOMStateListener` injecting in-browser `MutationObserver` scripts to monitor layout shifts and route transitions before executing actions.
* **CDP Session Persistence**: Built `core/session.py` to extract authentication tokens from Chrome DevTools Protocol (port `9222`), decode JWT claims (`exp`), and serialize sessions to disk.
* **Structured Logging**: Replaced raw `print()` statements with standard `logging` configured with microsecond-timestamped ANSI colored stdout and rotating file logging.
* **Docker Containerization**: Authored a multi-stage `Dockerfile` with non-root security (`USER appuser`) and pre-installed headless Chromium dependencies.
* **Automated CI/CD**: Set up `.github/workflows/ci.yml` running a Python 3.11/3.12 test matrix, `pytest` unit tests, CLI smoke tests, and Docker container verification.
* **100% Green CI**: Debugged Ubuntu runner pathing and action namespaces live to achieve a verified green badge on GitHub.

---

## 2. Architecture of `async-web-automation-engine`

```text
async-web-automation-engine/
├── config/
│   ├── __init__.py
│   └── settings.py          # 12-Factor Pydantic BaseSettings & .env schema
├── core/
│   ├── __init__.py
│   ├── models.py            # Pydantic schemas (WorkflowNode, SessionState, ExecutionReport)
│   ├── session.py           # SessionManager: CDP bridge, JWT parser, disk serialization
│   ├── browser.py           # Playwright async engine: resilient clicks, layout shift waits
│   └── telemetry_client.py  # Pooled Async HTTP client with backoff & circuit breaker
├── handlers/
│   ├── __init__.py
│   ├── dom_listener.py      # In-page MutationObserver & SPA routing listener
│   └── workflow_engine.py   # Bounded concurrency task orchestrator (Semaphore pool)
├── utils/
│   ├── __init__.py
│   ├── logger.py            # Structured ANSI color & rotating file logging
│   └── retry.py             # Asynchronous exponential backoff decorator with jitter
├── tests/
│   ├── conftest.py          # Pytest root path resolution fixture
│   └── test_engine.py       # 5 automated test cases (100% passing)
├── .env.example             # Clean environment configuration template
├── .gitignore               # Tailored for Python, Playwright, sessions, logs, and secrets
├── .dockerignore            # Excludes build context overhead & secrets
├── Dockerfile               # Multi-stage non-root container image
├── pytest.ini               # Pytest path and asyncio configuration
├── requirements.txt         # Pinned production dependencies
├── main.py                  # High-performance Click CLI with execution telemetry
├── run.py                   # Canonical convenience entry point
└── sync_token.py            # Standalone CDP session synchronizer
```

---

## 3. Your Interview Cheatsheet (DevOps & Backend)

### The 30-Second Pitch
> *"I built `async-web-automation-engine`, an asynchronous Python engine designed for reliable web automation and backend telemetry synchronization.  
> Most scrapers break on modern Single Page Applications (SPAs) due to race conditions, rigid sleeps, and plain-text credentials. I engineered this like a distributed system: using **AsyncIO** for non-blocking I/O, **exponential backoff with jitter** to prevent thundering-herd issues, dynamic **DOM MutationObservers** for SPA stability, and **Chrome DevTools Protocol (CDP)** for token persistence."*

### Key Concepts to Know by Heart

| Concept | Why We Used It | Interview Explanation |
| :--- | :--- | :--- |
| **`asyncio.Semaphore`** | Caps concurrent tasks | *"Prevents overwhelming target servers or triggering 429 rate limits while keeping I/O non-blocking."* |
| **Exponential Backoff + Jitter** | Resilient retries | *"Spreads retry attempts with randomized noise so failed requests don't hit the server at the exact same second."* |
| **`MutationObserver`** | Replaces `time.sleep()` | *"Listens to browser virtual DOM additions/removals and layout bounding boxes; only clicks when the page has settled."* |
| **Chrome DevTools Protocol (CDP)** | Zero-password auth | *"Connects to port 9222 of an active browser to extract the JWT from localStorage and validates its expiration claim."* |
| **Multi-Stage Dockerfile** | Minimal container image | *"Runs as non-root `appuser` for security compliance; pre-installs Chromium dependencies."* |
| **GitHub Actions Matrix** | Automated testing | *"Tests across Python 3.11 and 3.12, verifying linting, pytest, and container builds on every push."* |

---

## 4. Git & GitHub Commands Reference

```bash
# Check current repository status
git status

# Stage all modified/new files
git add -A

# Commit staged changes with a descriptive message
git commit -m "feat: description of work"

# Download latest remote commits without touching local files
git fetch origin

# Replay local commits on top of remote branch (clean linear history)
git rebase origin/main

# Push commits to GitHub
git push origin main

# Switch to a new feature branch
git checkout -b feature/my-new-feature

# Stash uncommitted work temporarily
git stash
git stash pop

# Inspect GitHub Actions CI runs via CLI
gh run list
gh run view <run-id> --log-failed
```

---

## 5. The Real CI/CD Debugging Story (STAR Method)

When asked: *"Tell me about a time a build failed in CI and how you resolved it."*

* **Situation**: Pushed the test suite to GitHub Actions. Tests passed locally on Windows, but failed on the Ubuntu CI runner with `ModuleNotFoundError: No module named 'config'`.
* **Task**: Debug why module resolution failed in the Linux runner without breaking local workflows.
* **Action**:
  1. Ran `gh run view <id> --log-failed` to view the runner traceback.
  2. Identified that Linux pytest does not implicitly put `.` on `sys.path`.
  3. Added `pytest.ini` with `pythonpath = .` and `tests/conftest.py` with dynamic path resolution.
  4. Fixed a Docker action namespace typo (`docker/setup-buildx-action@v3`).
* **Result**: Pipeline passed 100% green across Python 3.11, 3.12, and Docker verification in 1m 42s.

---

## 6. Tomorrow's Blueprint: LinkedIn-to-Telegram Job Sentinel

### Project Overview
* **Name**: `cloud-job-sentinel`
* **What it does**: Event-driven cloud pipeline that scrapes/monitors LinkedIn for new DevOps and Cloud internship postings, deduplicates them using hash indexing, filters keywords, and sends real-time Telegram alerts with 1-click apply buttons within 90 seconds of posting.
* **Why it's incredible**: You can literally tell recruiters: *"I found this job opening through the automated pipeline I built!"*

### Tomorrow's Action Plan:
1. **Telegram Bot Setup**: Create a Telegram bot via `@BotFather` and retrieve the Bot Token and Chat ID.
2. **Ingestion Engine**: Build a lightweight, headless Playwright / async HTTP scraper for LinkedIn job search feeds.
3. **Filtering & Deduplication**: Filter for keywords (`Cloud`, `DevOps`, `Intern`, `Junior`), reject (`Senior`, `10+ years`), and hash `company + title + location` to avoid duplicate notifications.
4. **Cloud Scheduling**: Deploy it as a **free 24/7 GitHub Actions Cron job** (`cron: '*/30 * * * *'`).
5. **Portfolio Packaging**: Add badges, architecture diagrams, Dockerfile, and push to `kushagar-debug/cloud-job-sentinel`.

---

> **Note**: Rest well! All your code is committed, tested, pushed, and documented. See you tomorrow to build the Job Sentinel! 🚀
