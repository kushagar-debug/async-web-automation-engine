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

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/YOUR_USERNAME/infosys-automation.git
cd infosys-automation
pip install -r requirements.txt
```

---

### 2. Configure Authentication

Choose **Method A** (Automatic) or **Method B** (Manual):

#### **Method A: Automatic Token Extraction via Browser (Recommended)**

1. Launch Chrome or Edge with Remote Debugging enabled:

   **Windows (Chrome):**
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\chrome-debug
   ```

   **Mac / Linux (Chrome):**
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
   ```

2. In the opened browser window, log into [Infosys Springboard](https://infyspringboard.onwingspan.com) and navigate to any course page.

3. Run the token sync utility:
   ```bash
   python sync_token.py
   ```
   *This automatically extracts your active JWT token and `wid` into `~/.infosys-course/config.json`.*

---

#### **Method B: Manual Configuration**

1. Copy `config.example.json` to your home directory or project root:
   - File path: `~/.infosys-course/config.json`

2. Open the file and insert your authentication credentials:
   ```json
   {
     "base_url": "https://infyspringboard.onwingspan.com",
     "root_org": "infosysheadstart",
     "org": "infosysheadstart",
     "auth": {
       "auth-token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIs...",
       "wid": "your-uuid-wid-here"
     }
   }
   ```
   > **How to get your credentials manually:**
   > - Open DevTools (`F12`) on Springboard → **Application** tab → **Local Storage** → search for `kc` (token) and `wid`.

---

### 3. Run Course Completion

Run the completer using a **full course URL** or **course ID**:

```bash
# Using full course URL:
python run.py "https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_012760837643722752345_shared/overview"

# Using bare course ID:
python run.py lex_auth_012760837643722752345_shared
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
