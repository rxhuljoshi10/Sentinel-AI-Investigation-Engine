# Sentinel AI 🛡️

An Autonomous Incident Investigation Platform powered by a multi-agent AI pipeline. Paste a log file and incident description — Sentinel investigates it like a senior engineer would, producing a structured Root Cause Analysis report in minutes.

**Live demo:** `http://localhost:3000` · **API docs:** `http://localhost:8000/docs`

---

## What it does

When a production incident happens, developers manually check logs, cross-reference GitHub commits, query databases, and search past incidents — all while the system is down. Sentinel automates this entire process.

**Input:** incident description + log content  
**Output:** severity, root cause, evidence, immediate actions, confidence score

---

## Architecture

The system runs five specialized agents coordinated by LangGraph:

| Agent | Role |
|---|---|
| Planner | Uses function calling to select the right tools for this specific incident |
| Log Analyzer | Extracts structured findings from raw log content |
| RAG Searcher | Finds semantically similar past incidents in ChromaDB |
| Memory | Retrieves service-level patterns and proven runbooks from PostgreSQL |
| Reasoner | Synthesizes all evidence into a structured RCA report |

Log Analyzer and Memory run in parallel. RAG Searcher runs after Log Analyzer (needs structured findings for better embeddings). All three feed into Reasoner.

---

## Tech stack

**Frontend:** Next.js · React · Tailwind CSS  
**Backend:** FastAPI · Python 3.13  
**AI:** Ollama (llama3.2:3b) · LangGraph · LangChain · nomic-embed-text  
**Storage:** PostgreSQL (structured incidents) · ChromaDB (vector embeddings) · Redis (LLM response cache)  
**Infra:** Docker Compose · GitHub Actions CI  

---

## Key technical decisions

**Two-pass RAG** — To search ChromaDB meaningfully, we need a structured embedding (service name, cause, severity). But we don't have that from a raw log. So we run a first-pass analysis to extract structure, embed that, search for similar incidents, then re-analyze with historical context included.

**Evidence source labeling** — Early evaluation (avg 0.627) revealed memory contamination: the model was copying past incident conclusions instead of reasoning from current logs. Fixed by labeling all evidence with source tags (`[CURRENT LOG]`, `[PAST INCIDENT]`, `[MEMORY]`) and restructuring the Reasoner prompt to explicitly prioritize current evidence. Score improved to 0.786.

**PostgreSQL + ChromaDB serve different purposes** — ChromaDB handles semantic similarity ("find incidents that mean the same thing"). PostgreSQL handles structured queries ("show all critical incidents from last week"). Neither can replace the other.

---

## Evaluation

Built a custom evaluation framework with four scoring dimensions:

| Dimension | Method |
|---|---|
| Rule-based | Severity match, service match, keyword presence |
| Evidence grounding | Are evidence items traceable to actual log lines? |
| Semantic similarity | Embedding-based comparison vs expected root cause |
| LLM-as-judge | Separate LLM scores accuracy, completeness, actionability |

**Current scores:** 3/3 test cases passing · avg score 0.786

---

## Getting started

**Prerequisites:** Docker Desktop · Ollama · Python 3.11+ · Node.js 18+

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/sentinel-ai.git
cd sentinel-ai

# 2. Pull models
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# 3. Start infrastructure
docker-compose up -d

# 4. Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# 5. Frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`  
Login: `rahul` / `sentinel123`

---

## Project structure

```
sentinel-ai/
├── backend/
│   ├── agents/          # LangGraph nodes and graph definition
│   ├── core/            # Config, database, auth, cache
│   ├── evaluation/      # Test cases and scoring framework
│   ├── routers/         # FastAPI route handlers
│   ├── services/        # LLM, vector, memory, function calling
│   └── tools/           # GitHub, PostgreSQL, filesystem tools
├── frontend/
│   ├── app/             # Next.js app router pages
│   ├── components/      # React components
│   └── lib/             # API client
└── docker-compose.yml
```

---

## Roadmap

- [x] v0.1 — FastAPI + Ollama streaming chat
- [x] v0.2 — Structured log analysis with Pydantic validation
- [x] v0.3 — RAG pipeline with ChromaDB
- [x] v0.4 — Multi-agent LangGraph investigation
- [x] v0.5 — Function calling + real GitHub/PostgreSQL tools
- [x] v0.6 — Long-term memory + runbook generation
- [x] v0.7 — Evaluation framework
- [x] v0.8 — Next.js dashboard + JWT auth + Redis + Docker
- [ ] v0.9 — Kubernetes + AWS deployment

---

Built by [Rahul Joshi](https://github.com/YOUR_USERNAME) · MCA @ MIT ADT University