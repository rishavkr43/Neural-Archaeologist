# 🧠 Neural Archaeologist v2

> **AI-powered codebase intelligence for every audience.**  
> Dig into any GitHub repository and get a deeply contextual report — tailored to whether you are a solo developer, a startup evaluating acquisition, an enterprise architect, or an open-source maintainer.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.20-blue)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/LLM-Groq%20llama--3.3--70b-orange)](https://groq.com)
[![React](https://img.shields.io/badge/Frontend-React%2018-61dafb)](https://react.dev)

---

## Table of Contents

1. [What it Does](#what-it-does)
2. [Architecture Overview](#architecture-overview)
3. [The 6-Agent Pipeline](#the-6-agent-pipeline)
4. [Persona Modes](#persona-modes)
5. [CUI v2 Formula](#cui-v2-formula)
6. [Onboarding Graph (DAG)](#onboarding-graph-dag)
7. [Tech Stack](#tech-stack)
8. [Project Structure](#project-structure)
9. [Setup & Installation](#setup--installation)
10. [Environment Variables](#environment-variables)
11. [Running Locally](#running-locally)
12. [API Reference](#api-reference)
13. [Frontend Guide](#frontend-guide)
14. [Demo Walkthrough](#demo-walkthrough)
15. [Roadmap](#roadmap)

---

## What it Does

Neural Archaeologist analyses any GitHub repository and answers questions like:

- **Why was this abandoned?** — git pattern analysis + web evidence
- **Can I onboard in a week?** — Onboarding Complexity Score + DAG learning path
- **What is the bus factor?** — file-level ownership mapping
- **Is this safe to inherit?** — static security scan + business risk score
- **Where do I start?** — Day 1 / Day 3 / Week 1 learning tiers

The system runs a **6-agent multi-source pipeline** and adapts its output to one of **4 persona modes**, so a startup CEO and a solo developer get completely different, purpose-built reports on the same repo.

---

## Architecture Overview

```
User Request
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     COORDINATOR (LangGraph)                      │
│                                                                  │
│  Scout ──► PersonaRouter ──► Planner ──► Analyst ──► Evaluator ──► Narrator │
│     ▲                                        │                    │
│     └─ (loop if confidence < 70%) ──────────┘                    │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
Persona-Aware Markdown Report  +  JSON Metadata
```

---

## The 6-Agent Pipeline

### 1. 🔍 Scout (Multi-Source, 4 Modules)

Runs first to gather real repository intelligence across 4 parallel extraction modules:

| Module | What it gathers |
|--------|----------------|
| **Git Intelligence** | Commit history, patterns (spikes, decay, halt), contributor data, bus factor |
| **AST Structural Analysis** | Functions, imports, entry points, cyclomatic complexity, doc coverage (Python/JS/TS/Java/Go) |
| **Static Risk Scan** | Security patterns (SQLi, hardcoded secrets, eval, OS commands), tech debt signals |
| **Issue & PR Mining** | Open issues, stale PRs, good-first-issues, community health percentage |

Optionally runs a **Web Search** pass (SerpAPI + BeautifulSoup) when confidence is below threshold.

**Confidence Output**: 15% (baseline after completion)

---

### 2. 🎭 Persona Router
Classifies the investigation intent using **real repository data** from Scout.

- **Method:** Heuristic scoring (fast, no LLM call if confidence ≥ 0.80) with LLM fallback for ambiguous cases
- **Input:** Scout's GitHub metadata (stars, forks, contributors, file count, community health)
- **Output:** `persona_mode`, `confidence`

```
SOLO_DEV | STARTUP | ENTERPRISE | OSS_MAINTAINER
```

**Confidence Output**: 25%

---

### 3. 📋 Planner
Generates an explicit JSON task graph with real file counts from Scout. Inspired by CodeR and CrewAI.

- **Strategies:** `shallow_first` (>5000 files), `standard` (>500 files), `deep` (small repos)
- **Output:** Ordered step list with 4 phases: Scout gathering → Analysis → Evaluation → Reporting
- **Persona customisation:** Enterprise gets compliance steps; OSS_MAINTAINER gets community health steps

**Confidence Output**: 35%

---

### 4. 🧪 Analyst (CUI v2 + OCS + Business Risk + LLM)

Four computation steps:

1. **CUI v2** — 8-component Codebase Understanding Index (see formula below)
2. **Onboarding Graph** — imports → DAG → topological sort → Day 1/Week 1/Week 2 tiers  
3. **OCS** — Onboarding Complexity Score (0–100)
4. **Business Risk** — 4 risk rules (CRITICAL / HIGH / MEDIUM)
5. **LLM Hypothesis** — Groq `qwen/qwen3.8-27b` forms a narrative hypothesis with confidence score

**Confidence Output**: Real computed confidence (typically 60-90%)

---

### 5. ✅ Evaluator (Quality Gate)

Runs 4 verification checks before any report is published:

| Check | What it verifies |
|-------|-----------------|
| Entry point validation | Cross-checks fan-in against import graph |
| Critical file verification | Ensures risk claims are consistent |
| Bus factor sanity | Checks that bus-factor-critical files have no companion tests |
| Onboarding graph cycles | Detects circular imports that invalidate the DAG |

Also runs a **pattern-based risk scan** (Semgrep if available, regex fallback otherwise).  
Adjusts overall confidence by ±N points based on findings.

**Confidence Output**: Adjusted final confidence

---

### 6. 📖 Narrator (Persona-Aware Reports)

Generates **concise, data-driven reports** tailored for each persona. Reports are optimized for brevity while retaining all critical information:

- **3-Act Story**: Birth → Golden Age → Decline (1 paragraph each, 3-5 sentences max)
- **Key Findings**: 3-5 bullet points of critical discoveries
- **Salvageability**: One-line verdict with brief justification
- **Persona Sections**: 1-2 focused paragraphs per section

| Persona | Report Sections |
|---------|----------------|
| **SOLO_DEV** | Quick summary, Day-1 learning path, key files, bus factor warnings, safe first PR, tech debt, recommendations |
| **STARTUP** | Executive summary, business risk, tech debt cost, onboarding timeline, team acquisition risk, build vs buy verdict |
| **ENTERPRISE** | Executive summary, security/compliance scan, architectural complexity, scalability, migration effort, vendor dependency risk |
| **OSS_MAINTAINER** | Project health, contributor diversity, issue/PR velocity, onboarding experience, docs gaps, good-first-issue candidates |

---

## Persona Modes

| Mode | Target User | CUI Weight Focus |
|------|-------------|-----------------|
| `SOLO_DEV` | Individual developer inheriting a codebase | Complexity, documentation |
| `STARTUP` | Technical co-founder or CTO evaluating a repo | Bus factor, history, risk |
| `ENTERPRISE` | Enterprise architect or security team | Risk, compliance, scalability |
| `OSS_MAINTAINER` | Open source project owner | Community, test coverage, documentation |

Each persona applies different **PERSONA_WEIGHTS** to the 8 CUI components, producing a weighted score optimised for that audience's concerns.

---

## CUI v2 Formula

**Codebase Understanding Index** — measures how easy it is to understand, onboard, and contribute to a codebase.

$$\text{CUI} = w_C \cdot C + w_F \cdot F + w_H \cdot H + w_I \cdot I + w_T \cdot T + w_R \cdot R + w_B \cdot B + w_D \cdot D$$

| Symbol | Component | Default Weight | Description |
|--------|-----------|---------------|-------------|
| C | Cyclomatic Complexity | 0.20 | Inverse of average function complexity |
| F | File Count | 0.15 | Penalises repos with >2000 files |
| H | History | 0.15 | Recency of last commit (decays over 60 months) |
| I | Import Complexity | 0.15 | Inverse of average fan-in depth |
| T | Test Coverage Signal | 0.10 | Ratio of test files to total files |
| R | Risk Score | 0.10 | Inverse of security risk density |
| B | Bus Factor | 0.10 | Percentage of non-critical-ownership files |
| D | Documentation | 0.05 | Docstring coverage percentage |

Score range: **0–100**

| Range | Label |
|-------|-------|
| 80–100 | Very Easy |
| 60–79 | Easy |
| 40–59 | Moderate |
| 20–39 | Complex |
| 0–19 | Very Complex |

---

## Onboarding Graph (DAG)

The **OnboardingGraphBuilder** constructs a directed acyclic graph from the import dependency tree:

```
Entry Point (main.py)
    └── core/config.py          ← Day 1
        └── core/database.py    ← Day 1
            ├── models/user.py  ← Day 3
            └── models/repo.py  ← Day 3
                └── utils/...   ← Week 1
```

Learning tiers:
- **Day 1** — up to 5 files: entry points + their direct dependencies
- **Week 1** — up to 10 more files: second-level dependencies  
- **Week 2** — up to 20 more files: deeper graph

The **Onboarding Complexity Score (OCS)** aggregates graph depth, breadth, cyclomatic complexity, and bus-factor-critical files into a 0–100 score.

**Note**: Learning path generation has been fully debugged and now correctly populates for all repository types.

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.104 |
| Agent Orchestration | LangGraph 0.0.20 |
| LLM | Groq `qwen/qwen3.8-27b` |
| Git Analysis | GitPython 3.1.40 |
| Web Search | SerpAPI + BeautifulSoup4 |
| Database | PostgreSQL via SQLAlchemy 2.0 |
| WebSockets | python-socketio 5.10 |
| Auth | JWT (python-jose) + bcrypt |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 18 + Vite |
| Styling | TailwindCSS |
| State | Zustand |
| Charts | Recharts |
| WebSocket | Socket.IO Client |

---

## Project Structure

```
Neural-Archaeologist/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── persona_router.py   # Stage 1: Persona classification
│   │   │   ├── planner.py          # Stage 2: Task graph generation
│   │   │   ├── scout.py            # Stage 3: Multi-source intelligence (4 modules)
│   │   │   ├── analyst.py          # Stage 4: CUI v2 + LLM hypothesis
│   │   │   ├── evaluator.py        # Stage 5: Quality gate / verification
│   │   │   ├── narrator.py         # Stage 6: Persona-aware report
│   │   │   └── coordinator.py      # LangGraph orchestrator
│   │   ├── utils/
│   │   │   ├── ast_parser.py       # Multi-language AST scanning (Python/JS/TS/Java/Go)
│   │   │   ├── cui_calculator.py   # CUI v2, Bus Factor, Onboarding Graph, Business Risk
│   │   │   ├── git_analyzer.py     # Git clone + commit analysis + GitHub API
│   │   │   ├── web_search.py       # SerpAPI + scraping
│   │   │   ├── auth.py             # JWT helpers
│   │   │   └── websocket.py        # Socket.IO event helpers
│   │   ├── routes/
│   │   │   ├── auth.py             # /auth/register, /auth/login
│   │   │   └── investigations.py   # /investigations/* CRUD + trigger
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── config.py               # Pydantic settings
│   │   ├── database.py             # DB session factory
│   │   └── main.py                 # FastAPI app + Socket.IO mount
│   ├── requirements.txt
│   └── ARCHITECTURE.md
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Landing.jsx         # Hero page
│   │   │   ├── Dashboard.jsx       # Investigation trigger + live log feed
│   │   │   ├── Report.jsx          # Full report viewer
│   │   │   ├── History.jsx         # Past investigations
│   │   │   ├── Login.jsx
│   │   │   └── Register.jsx
│   │   ├── components/
│   │   │   ├── AgentStatusPanel.jsx
│   │   │   ├── AnimatedLogFeed.jsx
│   │   │   ├── AdvancedTimelineGraph.jsx
│   │   │   ├── ConfidenceScore.jsx
│   │   │   ├── AnimatedHypothesis.jsx
│   │   │   ├── ProgressMetrics.jsx
│   │   │   └── AgentLogEntry.jsx
│   │   ├── services/
│   │   │   ├── api.js              # Axios REST client
│   │   │   └── socket.js           # Socket.IO client
│   │   └── store/
│   │       └── useStore.js         # Zustand global store
│   └── package.json
└── README.md
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/your-username/Neural-Archaeologist.git
cd Neural-Archaeologist
```

### 2. Backend setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)
```

### 3. Database setup
```bash
# Create PostgreSQL database
createdb neural_archaeologist

# Run migrations
alembic upgrade head
```

### 4. Frontend setup
```bash
cd frontend
npm install
```

---

## Environment Variables

Create `backend/.env`:

```env
# ─── Required ──────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@localhost:5432/neural_archaeologist
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=qwen/qwen3.8-27b
SERPAPI_API_KEY=your_serpapi_key
SECRET_KEY=your-super-secret-jwt-key-min-32-chars

# ─── Optional but recommended ──────────────────────────────────────────────
GITHUB_TOKEN=ghp_your_github_pat     # Raises rate limit from 60 to 5000 req/hr

# ─── v2 Configuration (all have defaults) ──────────────────────────────────
CONFIDENCE_THRESHOLD=70              # Min confidence to skip web search
SEMGREP_ENABLED=false                # Enable Semgrep CLI (install separately)
MAX_AST_FILES=800                    # Max files for AST parsing
MAX_AST_FILE_SIZE_KB=200             # Skip large files
DEFAULT_PERSONA=SOLO_DEV             # Fallback persona
DEBUG=true
```

API key acquisition:
- **Groq:** [console.groq.com](https://console.groq.com) — free tier, 30 req/min
- **SerpAPI:** [serpapi.com](https://serpapi.com) — 100 free searches/month
- **GitHub PAT:** GitHub → Settings → Developer Settings → Personal Access Tokens (read:repo scope)

---

## Running Locally

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Backend available at: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

### Frontend
```bash
cd frontend
npm run dev
```

Frontend available at: `http://localhost:5173`

---

## API Reference

### Authentication
```
POST   /auth/register          Create account
POST   /auth/login             Get JWT token
GET    /auth/me                Current user info
```

### Investigations
```
POST   /investigations/        Start a new investigation
GET    /investigations/        List all investigations
GET    /investigations/{id}    Get investigation result
DELETE /investigations/{id}    Delete investigation
```

**Start investigation payload:**
```json
{
  "repo_url": "https://github.com/owner/repo",
  "user_context": "I want to fork this and use it for my startup",
  "persona_mode": "STARTUP",     // optional — auto-detected if omitted
  "include_web_search": true,
  "max_rounds": 3
}
```

**Investigation result shape:**
```json
{
  "report": {
    "narrative": "## Markdown report...",
    "timeline": [...],
    "executive_summary": {...},
    "learning_path": {"day_1": [...], "week_1": [...], "week_2": [...]},
    "safe_first_pr": {...},
    "bus_factor_summary": "..."
  },
  "confidence": 85,
  "persona_mode": "STARTUP",
  "cui_scores": {"cui_score": 72.3, "understanding_label": "Easy", "components": {...}},
  "ocs_score": 45,
  "business_risk": {"risk_items": [...]},
  "onboarding_graph": {"learning_tiers": {...}, "total_nodes": 42},
  "verified_claims": {...},
  "task_graph": {...}
}
```

### WebSocket Events (Socket.IO)
Connect to `http://localhost:8000` with Socket.IO.

```javascript
socket.emit("join_investigation", { investigation_id: "uuid" });

socket.on("agent_progress", (data) => {
  // data: { agent, message, data, timestamp }
});

socket.on("investigation_complete", (data) => {
  // data: { investigation_id, result }
});
```

---

## Frontend Guide

### Dashboard
1. Enter a GitHub repository URL
2. (Optional) Choose a persona mode, or let the system auto-detect based on repository characteristics
3. Click **Investigate** — watch the live agent log feed update in real-time
4. View the confidence score build gradually: 15% → 25% → 35% → final score as each agent completes

### Report Page
- **Story tab** — concise 3-act narrative with key findings and salvageability assessment
- **Timeline** — interactive Recharts timeline of key events
- **Analysis tab** — CUI breakdown, OCS score, business risk assessment
- **Onboarding tab** — Learning path (Day 1/Week 1/Week 2), safe first PR suggestions, bus factor analysis  
- **Contributors** — contributor profiles and activity patterns
- **GitHub Insights** — community health, issue/PR metrics
- **Sources** — web evidence and citations (when available)

### History
Browse past investigations, filter by repo or persona mode, re-open full reports.

---

## Demo Walkthrough

```bash
# 1. Start the backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# 2. Start the frontend
cd frontend && npm run dev

# 3. Register & login at http://localhost:5173

# 4. Try these repos for interesting results:
#    - https://github.com/rails/rails          (large, active, enterprise)
#    - https://github.com/pypa/pip             (OSS maintainer demo)
#    - https://github.com/jakevdp/mpld3        (abandoned, good solo-dev demo)
#    - https://github.com/mperham/sidekiq      (startup acquisition scenario)
```

---

## Roadmap

| Feature | Status |
|---------|--------|
| 4 Persona Modes | ✅ v2 |
| CUI v2 Formula | ✅ v2 |
| AST Parsing (regex MVP) | ✅ v2 |
| Onboarding Graph (DAG) | ✅ v2 |
| Learning Path Generation | ✅ v2 (Fixed) |
| Staged Confidence Updates | ✅ v2 |
| Shortened Narrative Reports | ✅ v2 |
| Bus Factor Extraction | ✅ v2 |
| Evaluator / Quality Gate | ✅ v2 |
| Static Risk Scan | ✅ v2 |
| Issue & PR Mining | ✅ v2 |
| Business Risk Scorer | ✅ v2 |
| Safe First PR detection | ✅ v2 |
| Persona-aware reports | ✅ v2 |
| tree-sitter AST (production) | 🔜 v3 |
| Semgrep deep scan | 🔜 v3 |
| Vector DB (repo memory) | 🔜 v3 |
| Incremental re-analysis | 🔜 v3 |
| Auto-PR suggestions | 🔜 v3 |
| Monorepo support | 🔜 v3 |
| CI/CD integration | 🔜 v3 |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'feat: add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Built with ❤️ as a demonstration of multi-agent AI for software intelligence.*
