# Job Application Agent Suite — Master Build Plan

## Project Overview
A CLI-based AI agent suite that automates the entire software engineering job application process.
Built with Python, Claude API, LangGraph, Playwright, and SQLite.

---

## Framework Explainers
> Plain-English descriptions of every tool used in this project — no prior experience assumed.

### Python
The programming language the entire project is written in. Think of it as the glue holding everything together. Every file ends in `.py`.

### Typer
Turns Python functions into terminal commands. Without it, you'd have to write a lot of boilerplate to parse flags like `--job-id 5`. With it, you just write a normal function and decorate it with `@app.command()` — Typer handles the rest, including `--help` output automatically.

### Pydantic + pydantic-settings
Pydantic is a data validation library. If a function says it expects an integer and you give it a string, Pydantic catches it immediately with a clear error. `pydantic-settings` extends this to reading from `.env` files — so `config.py` can load `ANTHROPIC_API_KEY` from your `.env` and expose it as a typed Python attribute.

### SQLite
A database that lives in a single file (`data/jobs.db`) on your machine. No server, no account, no cost. Perfect for local tools. Think of it as a spreadsheet that your code can read and write to using structured queries.

### SQLAlchemy
A Python library that lets you talk to SQLite (and other databases) using Python classes instead of raw SQL. Instead of writing `INSERT INTO jobs (title, company) VALUES (...)`, you write `db.add(Job(title="...", company="..."))`. It also handles relationships — so `job.applications` automatically loads all applications linked to that job.

### Alembic
Handles database migrations. If you add a new column to a model in Phase 3, Alembic generates a migration script that safely updates the existing database without wiping it. Think of it as version control for your database schema.

### Anthropic Claude API
The AI brain of the project. You send it a prompt (text instructions + context), and it sends back a response — either plain text or structured JSON. All the intelligent tasks (scoring fit, writing cover letters, generating interview questions) go through this.

### LangGraph
A framework for building multi-step AI agent workflows. Instead of one big Claude call, you can define a graph of steps — e.g. "scrape job → score it → if score > 6, tailor resume → generate cover letter" — and LangGraph manages the flow, state, and branching logic between steps. Used in Phase 2+ for the orchestrator.

### JobSpy
A Python library that scrapes job listings from LinkedIn, Indeed, and Glassdoor. You give it keywords and locations, it returns a list of job postings. Saves us from having to write scrapers for each site ourselves.

### Playwright + Chromium
Playwright is a browser automation library. It controls a real Chrome browser (headlessly, in the background) so the code can visit websites, click buttons, fill forms, and read page content — just like a human would. Used for: scraping sites that block simple HTTP requests, auto-filling job applications on Greenhouse/Lever/Workday, and scraping LinkedIn.

### SerpAPI (google-search-results)
A paid API that wraps Google Search results in a clean JSON format. Used when we need to search the web programmatically — e.g. "find the LinkedIn page for this hiring manager" or "find recent news about this company."

### python-docx
Reads and writes `.docx` (Microsoft Word) files. Used to parse your base resume and write tailored resume versions per job.

### pypdf
Reads `.pdf` files. Used as a fallback if your resume is in PDF format rather than `.docx`.

### Gmail API + google-auth
Lets the app send emails from your Gmail account programmatically. Used in Phase 5 for outreach sequences. OAuth-based — your credentials never leave your machine.

### APScheduler
A background job scheduler. Lets you run functions on a timer — e.g. "run the job scraper every morning at 8am" — without needing a separate process or cron job.

### Rich
Makes terminal output look good. Tables, colors, progress bars, and formatted panels instead of plain `print()` statements.

### pytest + pytest-asyncio
The standard Python testing framework. You write test functions, run `pytest`, and it tells you which pass and which fail. `pytest-asyncio` adds support for testing async functions.

---

## Tech Stack
- **Language:** Python 3.11+
- **AI:** Anthropic Claude API (`claude-sonnet-4-6`) ✅ corrected from original
- **Agent Orchestration:** LangGraph
- **CLI:** Typer
- **Browser Automation:** Playwright + Chromium
- **Database:** SQLite + SQLAlchemy
- **Job Scraping:** JobSpy
- **Search:** SerpAPI (`google-search-results` package) ✅ corrected from original
- **Email:** Gmail API + smtplib
- **Resume/Doc editing:** python-docx + pypdf ✅ corrected from pypdf2
- **Scheduling:** APScheduler

---

## Folder Structure
```
JobX/
├── main.py                        # Typer CLI entry point
├── config.py                      # API keys, user prefs, .env loader
├── requirements.txt
├── .env.example
├── .gitignore
├── alembic.ini                    # Alembic migration config
├── alembic/                       # Migration scripts (auto-generated)
├── db/
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy ORM models
│   └── session.py                 # DB session factory + init_db()
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py            # LangGraph master agent
│   ├── scorer.py                  # Fit score + ATS check + gap analysis
│   ├── resume_tailor.py           # Resume rewriting per JD
│   ├── cover_letter.py            # Cover letter generator
│   ├── interview_prep.py          # Full interview prep agent
│   ├── company_research.py        # Company intel agent
│   ├── salary_intel.py            # Salary data agent
│   ├── hiring_signals.py          # Hiring velocity detector
│   ├── contact_finder.py          # Find hiring managers
│   ├── outreach.py                # Message gen + sequence manager
│   ├── applicator.py              # ATS autofill (Greenhouse/Lever/Workday)
│   └── tracker.py                 # Analytics + feedback loop
├── tools/
│   ├── __init__.py
│   ├── llm.py                     # Claude API wrapper + prompt templates
│   ├── scraper.py                 # JobSpy wrapper
│   ├── browser.py                 # Playwright session manager
│   ├── search.py                  # SerpAPI wrapper
│   └── gmail.py                   # Gmail API wrapper
├── tools/prompts/                 # Prompt templates as .txt files
├── tests/                         # pytest test files
└── data/
    ├── base_resume.docx           # User's master resume (user provides)
    ├── resume_versions/           # Tailored resumes per job (auto-generated)
    ├── cover_letters/             # Cover letters per job (auto-generated)
    └── jobs.db                    # SQLite database (auto-generated)
```

---

## Database Models (db/models.py)
- `Job` — id, title, company, url, description, source, posted_date, fit_score, ats_score, gap_analysis (JSON), status, created_at
- `Application` — id, job_id, applied_date, resume_version_path, cover_letter_path, status, notes
- `Contact` — id, job_id, name, title, linkedin_url, email, company
- `OutreachSequence` — id, contact_id, message_type (linkedin/email), sent_at, follow_up_due, response_received, status
- `ResumeVersion` — id, job_id, file_path, changes_summary, ats_score, created_at
- `CompanyResearch` — id, company_name, glassdoor_rating, funding_stage, recent_news, tech_stack, layoff_history, created_at
- `SalaryData` — id, company_name, role_level, salary_min, salary_max, equity, source, created_at
- `InterviewPrep` — id, job_id, technical_questions, behavioral_questions, company_questions, study_plan, mock_sessions, created_at
- `InterviewOutcome` — id, job_id, stage_reached, rejection_reason, feedback, created_at

---

## Build Phases

---

### PHASE 1 — Foundation ✅ COMPLETE — 20 tests passing
**Goal:** Scaffolding, DB, Claude wrapper, job scraper. Everything else depends on this.

#### Task 1.1 — Project Scaffolding & Config ✅ COMPLETE
- [x] Initialize project folder structure
- [x] Create `requirements.txt` with all dependencies (corrected: pypdf, google-search-results, pydantic-settings, removed linkedin-api)
- [x] Create `.env.example` with required keys
- [x] Create `config.py` using pydantic-settings — typed config, singleton `settings` object
- [x] Create `main.py` Typer CLI skeleton with all commands stubbed out
- [x] Create `.gitignore` (excludes .env, *.db, token.json, generated .docx files)

**What was built:**
`config.py` reads your `.env` file and exposes everything as typed Python attributes (e.g. `settings.anthropic_api_key`). `main.py` is the CLI entry point — all commands are wired up but most print "coming in Phase X" until their phase is implemented.

#### Task 1.2 — Database Schema ✅ COMPLETE
- [x] Create all SQLAlchemy models in `db/models.py` (9 models, all relationships defined)
- [x] Create `db/session.py` with `SessionLocal`, `get_session()` context manager, and `init_db()`
- [x] Initialize Alembic and wire `alembic/env.py` to use our engine and models
- [x] `python main.py db init` creates `data/jobs.db` with all 9 tables

**What was built:**
`db/models.py` defines every table as a Python class. `db/session.py` provides `get_session()` — a context manager used like `with get_session() as db:` that auto-commits on success and auto-rolls back on error. `init_db()` creates all tables safely (won't overwrite existing data). Alembic is wired up for schema migrations in future phases.

#### Task 1.3 — Claude Wrapper / LLM Core ✅ COMPLETE
- [x] Create `tools/llm.py` with a reusable `ClaudeClient` class
- [x] Support `chat()`, `chat_json()` (forces JSON response), and `chat_with_system()` methods
- [x] Add prompt template loader — `load_prompt(template_name, **kwargs)` reads `.txt` files from `tools/prompts/` and substitutes `{variables}`
- [x] Add retry logic — exponential backoff (1s, 2s, 4s) on rate limit and 5xx server errors, max 3 retries
- [x] `chat_json()` strips markdown fences if Claude adds them anyway, retries once with a stricter nudge if JSON parse fails
- [x] 10 pytest tests in `tests/test_llm.py` — all passing, no real API calls (mocked)

**What was built:**
`tools/llm.py` is the single entry point for all Claude API calls in the project. `ClaudeClient.chat()` returns a plain string. `chat_json()` appends a JSON instruction to the system prompt, strips any markdown fences from the response, and parses the result into a Python dict — if parsing fails it retries once with a clearer prompt. `load_prompt()` reads `.txt` template files from `tools/prompts/` and fills in `{variables}` like a string format. All agents in Phase 2+ will import `ClaudeClient` and `load_prompt` from here.

#### Task 1.4 — Job Scraper ✅ COMPLETE
- [x] Create `tools/scraper.py` wrapping JobSpy for LinkedIn, Indeed, Glassdoor
- [x] Filter by `settings.target_roles` — skips any listing whose title doesn't match a configured keyword
- [x] Deduplication by URL — checks existing DB rows before inserting, also dedupes within the same batch
- [x] `data/scraper_state.json` tracks `last_scraped_at` — subsequent runs pass `hours_old` to JobSpy so only new listings are fetched
- [x] `python main.py search` calls `run_scraper()`, prints a Rich table of new jobs found
- [x] Fixed `expire_on_commit=False` on `SessionLocal` so ORM objects stay readable after their session closes
- [x] 10 pytest tests in `tests/test_scraper.py` — all passing, no real network calls

**What was built:**
`tools/scraper.py` loops through every combination of `target_roles × target_locations` from `config.py`, calls JobSpy for each pair, then bulk-deduplicates the results against the `jobs` table before inserting. `data/scraper_state.json` records when the last scrape ran; on the next run it calculates how many hours have passed and only asks JobSpy for listings newer than that — so re-running `search` throughout the day won't pull the same jobs twice. Results are printed as a Rich table with title, company, source, and post date.

---

### PHASE 2 — Scoring & Prioritization ✅ COMPLETE — 18 tests passing
**Goal:** Rank jobs before spending time on any of them.
**Depends on:** Phase 1 complete

#### Task 2.1 — Resume Parser ✅ COMPLETE
- [x] `_extract_resume_text()` reads `data/base_resume.docx` via python-docx, strips blank lines
- [x] `parse_resume()` sends resume text to Claude using `tools/prompts/parse_resume.txt` and returns a structured dict with: name, contact, skills, experience (with bullets), education, projects
- [x] Results cached to `data/resume_parsed.json` — Claude only called once. Pass `force=True` to re-parse after updating your resume.
- [x] Fixed `config.py` — `TARGET_ROLES` and `TARGET_LOCATIONS` in `.env` must now be JSON arrays (e.g. `["Remote","New York"]`) so pydantic-settings v2 can parse them correctly
- [x] 5 pytest tests in `tests/test_resume_parser.py` — all passing

**What was built:**
`parse_resume()` in `tools/llm.py` is the single function all Phase 2+ agents call to get your resume data. It reads `data/base_resume.docx`, sends the full text to Claude with a structured prompt, and returns a Python dict with skills as a flat list (pulled from everywhere in the resume), plus structured experience/education/projects. Results are cached so repeated runs don't cost extra API calls. Re-run with `force=True` whenever you update your resume.

#### Task 2.2 — Fit Scorer ✅ COMPLETE
- [x] `agents/scorer.py` — `score_fit(job, resume_data)` calls Claude with JD + resume, returns `fit_score` (1-10), `matching_skills`, `missing_skills`, `reasoning`
- [x] Score is clamped to 1–10 and persisted to `Job.fit_score` in DB, status set to `scored`
- [x] `run_scorer()` scores all unscored jobs in DB, prints color-coded ranked table (green ≥7, yellow ≥5, red <5)
- [x] `python main.py score` wired up with `--min-score` and `--show-reasoning` flags
- [x] Job descriptions truncated to 4000 chars to stay within token limits
- [x] 7 pytest tests in `tests/test_scorer.py` — all passing, no real API calls

**What was built:**
`score_fit()` in `agents/scorer.py` builds a compact experience summary from your parsed resume, loads the `score_fit.txt` prompt template, and asks Claude to return structured JSON. `run_scorer()` fetches all unscored jobs from the DB, scores each one, saves the score, and prints a ranked table. Tested live against 5 real scraped jobs — correctly ranked Robinhood (Go/backend) highest and DraftKings (games stack) lowest.

#### Task 2.3 — ATS Keyword Checker ✅ COMPLETE
- [x] `check_ats(job, resume_data)` in `agents/scorer.py` — Claude extracts 10-20 technical keywords from the JD, cross-references against resume skills, returns `ats_score` (0-100%), `matched_keywords`, `missing_keywords`
- [x] Score clamped to 0-100 and persisted to `Job.ats_score` in DB
- [x] 3 pytest tests — all passing

**What was built:**
`check_ats()` sends the JD and candidate skills to Claude with a focused prompt that ignores soft skills and targets technical terms only. Returns a percentage score representing ATS keyword coverage, plus the full matched/missing keyword lists which feed directly into the gap analyzer.

#### Task 2.4 — Gap Analyzer ✅ COMPLETE
- [x] `analyze_gaps(fit_result, ats_result, resume_data)` in `agents/scorer.py` — classifies gaps as hard (can't reframe) or soft (can reframe using existing experience)
- [x] Skips Claude call entirely if no gaps detected — saves API cost
- [x] `reframe_suggestions` tied to candidate's actual experience, not hypothetical
- [x] Result persisted to `Job.gap_analysis` JSON field in DB
- [x] `run_scorer()` updated to run all three steps (fit → ATS → gaps) per job in one `python main.py score` call
- [x] Score table now shows Fit score, ATS%, matching skills, and hard gaps columns
- [x] 3 pytest tests — all passing (38/38 total)

**What was built:**
`analyze_gaps()` takes the missing skills list from the fit scorer and the missing keywords list from the ATS checker, then asks Claude to classify each as a hard gap (genuinely missing, can't be reframed) or soft gap (can be addressed by reframing existing experience). For each soft gap it generates a specific reframe suggestion tied to the candidate's actual bullets. This output is what Phase 3 resume tailoring will consume directly.

#### Task 2.5 — Job Lifecycle & Search UX ✅ COMPLETE
- [x] `--recent` flag on `score` — sorts by most recently posted first (fewest applicants); combine with `--limit` to target freshest batch
- [x] `--search TEXT` flag on `jobs` — case-insensitive filter on title or company name (find a job you remember by company without needing its ID)
- [x] `--unscored` flag on `jobs` — lists jobs not yet scored, sorted by newest posted; shows IDs for use with `score --job-id`
- [x] `--applied` flag on `jobs` — shows only applied jobs (your application pipeline)
- [x] `--all` flag on `jobs` — shows every job in the DB regardless of status
- [x] Applied jobs hidden from default `jobs` view — list stays clean as you apply
- [x] `python main.py mark-applied --job-id <id>` — sets `Job.status = "applied"`, hides from default list
- [x] `show` command now displays fit reasoning stored from scoring run
- [x] Fit reasoning persisted to `gap_analysis` JSON field as `fit_reasoning` key so it survives DB across sessions
- [x] Status column added to all `jobs` table views

**What was built:**
The daily workflow is now: `search` → `score --recent --limit 10` → `jobs` → `jobs --search "company"` → `show --job-id X` → `mark-applied --job-id X`. Applied jobs are hidden automatically so the list stays focused. `--search` solves "I remember the company but can't find the ID" without needing a database UI.

---

### PHASE 3 — Application Prep
**Goal:** Generate tailored application materials per job.
**Depends on:** Phase 2 complete

#### Task 3.1 — Resume Tailor
- [ ] In `agents/resume_tailor.py`, build `tailor_resume(job, resume_data, gap_analysis)`
- [ ] Claude rewrites bullet points to match JD keywords using `reframe_suggestions` from gap analyzer
- [ ] Save output as new `.docx` in `data/resume_versions/resume_{job_id}.docx`
- [ ] Create `ResumeVersion` DB record linked to job
- [ ] Never modify `data/base_resume.docx` — always work from a copy

#### Task 3.2 — Cover Letter Generator
- [ ] In `agents/cover_letter.py`, build `generate_cover_letter(job, resume_data, company_research=None)`
- [ ] Claude prompt includes: JD, user's background summary, company name, and optionally company research (Phase 4.1)
- [ ] Save as `data/cover_letters/cover_letter_{job_id}.docx`
- [ ] Note: cover letter gets richer once Phase 4.1 (company research) is built — design with that in mind

---

### PHASE 3.5 — Interview Prep Agent (Expanded)
**Goal:** Full interview preparation suite triggered once a job is worth pursuing.
**Depends on:** Phase 2 (gap analyzer), Phase 3 (application prep)

#### Task 3.5.1 — Glassdoor Interview Review Scraper
- [ ] Use Playwright in `tools/browser.py` to scrape Glassdoor interview reviews for a given company
- [ ] Extract: difficulty rating, interview format, common questions reported by candidates
- [ ] Store raw reviews on `InterviewPrep` model

#### Task 3.5.2 — Tech Stack Question Generator
- [ ] Claude reads JD and extracts all mentioned technologies (languages, frameworks, tools, cloud platforms)
- [ ] For each technology, generate 3–5 targeted technical interview questions at the appropriate level
- [ ] Store as structured JSON: `{ "Python": [...], "Kubernetes": [...] }`

#### Task 3.5.3 — Behavioral Question Generator
- [ ] Claude reads JD soft skill language ("collaborative", "takes ownership", "moves fast")
- [ ] Maps each trait to STAR-format behavioral questions
- [ ] Generate 8–10 behavioral questions with suggested answer frameworks

#### Task 3.5.4 — Company-Specific Prep
- [ ] Generate "why do you want to work here" talking points
- [ ] Pull recent eng blog posts or company news (SerpAPI) for informed questions to ask the interviewer
- [ ] Note: this step gets significantly richer once Phase 4.1 (company research agent) is complete

#### Task 3.5.5 — Mock Interview CLI Mode
- [ ] `python main.py prep mock --job-id <id>` launches an interactive CLI loop
- [ ] Claude asks a question (rotates between technical, behavioral, company-specific)
- [ ] User types their answer
- [ ] Claude scores the answer (1–10) with specific critique and a suggested better answer
- [ ] Session is saved to `InterviewPrep.mock_sessions` as JSON for later review

#### Task 3.5.6 — Study Plan Generator
- [ ] Reads `hard_gaps` from gap analyzer (Phase 2.4)
- [ ] Claude generates a prioritized study plan: topic, resources (courses, docs, leetcode tags), estimated hours
- [ ] Outputs as a readable CLI table and saves to `InterviewPrep` model
- [ ] Ties into Phase 7.2 (interview outcome tracker) — if you fail on a topic, study plan updates

---

### PHASE 4 — Intelligence & Research
**Goal:** Know the company deeply before applying or reaching out.
**Depends on:** Phase 1 (DB, scraper). Enriches Phase 3.2 and 3.5.4 retroactively.

#### Task 4.1 — Company Research Agent
- [ ] In `agents/company_research.py`, build `research_company(company_name)`
- [ ] Sources to pull: Glassdoor rating (Playwright), recent news (SerpAPI), funding/stage (Crunchbase scrape or SerpAPI), tech stack (StackShare or Builtwith), layoff history (layoffs.fyi scrape)
- [ ] Claude synthesizes into a structured `CompanyResearch` record
- [ ] CLI: `python main.py research --company "Stripe"`

#### Task 4.2 — Salary Intelligence Agent
- [ ] In `agents/salary_intel.py`, scrape Levels.fyi and Glassdoor for comp data
- [ ] Inputs: company name + role level (junior/mid/senior)
- [ ] Output: salary range, equity range, bonus, total comp — stored in `SalaryData`
- [ ] CLI: `python main.py salary --company "Stripe" --level senior`

#### Task 4.3 — Hiring Signal Detector
- [ ] Monitor job posting velocity: if a company posts 3+ eng roles in 7 days, flag as "hiring surge"
- [ ] Also use SerpAPI to find LinkedIn posts where employees say "we're hiring"
- [ ] Boost `fit_score` priority for companies with active hiring signals

---

### PHASE 5 — Outreach
**Goal:** Get a human to see your application.
**Depends on:** Phase 4 complete (need company research before reaching out)

#### Task 5.1 — Referral Detector
- [ ] User exports LinkedIn connections as CSV (Settings → Data Export)
- [ ] `python main.py referrals --job-id <id>` cross-references CSV against job's company
- [ ] Outputs matching connections with their title and LinkedIn URL

#### Task 5.2 — Contact Finder
- [ ] In `agents/contact_finder.py`, use SerpAPI to search `site:linkedin.com [company] recruiter software engineer`
- [ ] Playwright to visit and parse LinkedIn profiles
- [ ] Store found contacts in `Contact` model linked to job

#### Task 5.3 — Outreach Message Generator
- [ ] Claude writes personalized LinkedIn DM or email using: contact name/title, company research, your background, the specific role
- [ ] Two variants per contact: short LinkedIn DM (300 chars) and longer email version

#### Task 5.4 — Outreach Sequence Manager
- [ ] In `agents/outreach.py`, manage full send → follow-up → ghost lifecycle
- [ ] Day 0: send initial message via Gmail API
- [ ] Day 5: if no response, send follow-up
- [ ] Day 10: mark as ghosted
- [ ] All state tracked in `OutreachSequence` table

---

### PHASE 6 — Auto-Application
**Goal:** Submit applications automatically via Playwright.
**Depends on:** Phase 3 complete (need tailored resume + cover letter before applying)
**Note:** Most brittle phase — ATS sites update their DOM frequently. Build with resilience in mind.

#### Task 6.1 — Greenhouse Autofill
- [ ] Playwright selectors for standard Greenhouse application form
- [ ] Claude answers custom questions using JD + resume context
- [ ] Log application to `Application` table on success

#### Task 6.2 — Lever Autofill
- [ ] Same approach as Greenhouse for Lever ATS

#### Task 6.3 — Workday Autofill
- [ ] Multi-step forms, dynamic fields, login-wall behavior
- [ ] Build with extra error handling and screenshot-on-failure for debugging

#### Task 6.4 — LinkedIn Easy Apply
- [ ] Playwright automation for LinkedIn Easy Apply flow
- [ ] Requires LinkedIn session cookie management

---

### PHASE 7 — Analytics & Feedback Loop
**Goal:** Make the system smarter over time.
**Depends on:** All previous phases generating data

#### Task 7.1 — Response Rate Analyzer
- [ ] Query `OutreachSequence` and `Application` tables to compute response rates
- [ ] Claude summarizes patterns: "Your response rate is 3x higher for Series B startups vs FAANG"

#### Task 7.2 — Interview Outcome Tracker
- [ ] `python main.py outcome --job-id <id>` prompts user to log interview result
- [ ] Claude analyzes patterns across outcomes + mock interview sessions
- [ ] Feeds updated study plan back to Phase 3.5.6

#### Task 7.3 — Daily Digest Command
- [ ] `python main.py digest` — the daily driver command
- [ ] Sections: new jobs ranked by fit, follow-ups due today, hiring surges, pipeline summary, study plan items due

---

## CLI Command Reference (Final State)
```bash
python main.py db init              # Initialize database
python main.py search               # Scrape new job listings
python main.py score                # Score and rank all unscored jobs
python main.py research --company   # Run company research agent
python main.py salary --company --level  # Get salary intel
python main.py prep run --job-id    # Generate interview prep for a job
python main.py prep mock --job-id   # Start mock interview session
python main.py referrals --job-id   # Check LinkedIn connections at company
python main.py outreach --job-id    # Find contacts + generate messages
python main.py outreach --due       # Show follow-ups due today
python main.py apply --job-id       # Auto-fill and submit application
python main.py outcome --job-id     # Log interview outcome
python main.py digest               # Daily summary dashboard
```

## Key Connections Between Phases
- `gap_analyzer (2.4)` → feeds → `resume_tailor (3.1)` and `study_plan (3.5.6)`
- `company_research (4.1)` → enriches → `cover_letter (3.2)` and `company_prep (3.5.4)`
- `mock_interview sessions (3.5.5)` → feeds → `outcome_tracker (7.2)` → updates → `study_plan (3.5.6)`
- `hiring_signals (4.3)` → boosts priority in → `scorer (2.2)`
- `response_rate_analyzer (7.1)` → informs → `outreach_message_generator (5.3)`

## Environment Variables Required (.env)
```
ANTHROPIC_API_KEY=
SERPAPI_KEY=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
# token.json is written automatically by the Gmail OAuth flow at runtime
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
TARGET_ROLES=Software Engineer,Backend Engineer,Full Stack Engineer
TARGET_LOCATIONS=Remote,San Francisco,New York
MIN_FIT_SCORE=6
TARGET_COMP_MIN=150000
```

## Dependencies (requirements.txt)
```
anthropic
langgraph
langchain-core
typer[all]
sqlalchemy
alembic
jobspy
playwright
google-search-results        # ✅ corrected from 'serpapi'
python-docx
pypdf                        # ✅ corrected from 'pypdf2'
apscheduler
google-auth
google-auth-oauthlib
google-api-python-client
requests
python-dotenv
rich
pydantic
pydantic-settings            # ✅ added
pytest                       # ✅ added
pytest-asyncio               # ✅ added
# linkedin-api removed — violates ToS, use Playwright instead
```
