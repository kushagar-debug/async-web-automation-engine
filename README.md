# 🚀 Infosys Springboard Course Auto-Completer

A fast, automated course completer for **Infosys Springboard** (Wingspan learning platform). It automatically parses course hierarchies, marks all learning modules as completed via Wingspan's native progress API, and triggers course-level recalculation in real time.

---

## ✨ Features

- ⚡ **Direct Progress Calculation**: Uses native Wingspan progress calculate endpoints (`/progress/v1/progress/calculate`) for fast execution (~0.02s per item).
- 🔑 **Automated Token Sync**: Auto-extracts authentication JWT tokens and user IDs (`wid`) directly from your active browser session using Chrome/Edge Remote Debugging (CDP).
- 📚 **Full Tree Traversal**: Recursively traverses complex course tracks, sub-modules, videos, web modules, PDFs, practice exercises, and demos.
- 🔄 **Real-Time Recalculation**: Automatically triggers course-level progress aggregators (`/progress/v1/progress/recalculate`) so changes immediately reflect on your official platform profile.

---

## 🛠️ Quick Start

### 1. Install Dependencies

```powershell
py -m pip install -r requirements.txt
```

---

### 2. Configure Authentication

1. Close all Chrome windows, then launch Chrome with remote debugging:
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\chrome-debug
   ```

2. Log into [Infosys Springboard](https://infyspringboard.onwingspan.com) in the new browser window.

3. Sync your token:
   ```powershell
   py sync_token.py
   ```

---

### 3. Run Course Completion

Run the auto-completer by pasting your course URL:

```powershell
py run.py "https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_012760837643722752345_shared/overview"
```

---

## 📊 How It Works

1. **Hierarchy Resolution**: Reads the complete node hierarchy tree of the course using `hierarchy-service/level/{course_id}/2`.
2. **Leaf Node Extraction**: Gathers all completable learning resources (videos, documents, web modules, exercises, steps).
3. **Progress Calculation**: Sends POST requests to `/api-gw/wn-apis/infosysheadstart/progress/v1/progress/calculate` with required caller headers (`x-wingspan-caller: wingspan`).
4. **Backend Recalculation**: Calls `/progress/v1/progress/recalculate` to trigger background aggregation, updating overall progress percentage on your account profile.

---

## 📁 Repository Structure

```
infosys-automation/
├── infosys/
│   ├── __init__.py
│   ├── client.py          # HTTP client session & auth verification
│   ├── config.py          # Configuration loader & header builders
│   ├── course_reader.py   # Hierarchy tree parser & leaf collector
│   ├── completer.py       # Wingspan progress calculation engine
│   └── main.py            # CLI entry point
├── run.py                 # User entry script
├── sync_token.py          # Chrome/Edge CDP token extractor
├── config.example.json    # Example configuration file
├── requirements.txt       # Project dependencies
├── LICENSE                # MIT License
└── README.md              # Documentation
```

---

## 📜 License

Distributed under the [MIT License](LICENSE).
