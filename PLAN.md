# Job Application Agent Suite — Master Build Plan

## Project Overview
An AI agent suite that automates the entire software engineering job application process.
Built with Python, Claude API, Playwright, SQLite, and Streamlit.

Two interfaces — same underlying code:
- **CLI** (`main.py`) — terminal commands, best for batch operations and debugging
- **UI** (`streamlit run Home.py`) — browser dashboard, best for browsing, reviewing, and one-click actions

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
- **CLI:** Typer (`main.py`)
- **UI:** Streamlit (`Home.py` + `pages/`) ✅ added
- **Browser Automation:** Playwright + Chromium
- **Database:** SQLite + SQLAlchemy
- **Job Scraping:** JobSpy
- **Search:** SerpAPI (`google-search-results` package) ✅ corrected from original
- **Email:** Gmail API
- **Resume/Doc editing:** python-docx + pypdf ✅ corrected from pypdf2
- **Scheduling:** APScheduler

---

## Folder Structure
```
JobX/
├── main.py                        # Typer CLI entry point
├── Home.py                        # Streamlit UI — Daily Digest (home page)
├── config.py                      # API keys, user prefs, .env loader
├── requirements.txt
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml                # Streamlit theme (dark mode, accent color)
├── pages/                         # Streamlit pages (auto-discovered)
│   ├── 1_Jobs.py                  # Job browser with filters + gap analysis
│   ├── 2_Pipeline.py              # Orchestrator UI — run all steps for a job
│   ├── 3_Research.py              # Company research + salary lookup
│   ├── 4_Prep.py                  # Interview prep viewer + mock interview
│   ├── 5_Outreach.py              # Outreach messages + follow-up tracker
│   ├── 6_Analytics.py            # Pipeline stats + outcome logging
│   └── 7_Settings.py              # Resume upload, search/score controls, DB stats
├── alembic.ini                    # Alembic migration config
├── alembic/                       # Migration scripts (auto-generated)
├── db/
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy ORM models
│   └── session.py                 # DB session factory + init_db()
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py            # Chains research → tailor → cover letter → prep → salary
│   ├── scorer.py                  # Fit score + ATS check + gap analysis
│   ├── resume_tailor.py           # Resume rewriting per JD
│   ├── cover_letter.py            # Cover letter generator
│   ├── interview_prep.py          # Full interview prep agent
│   ├── company_research.py        # Company intel agent
│   ├── salary_intel.py            # Salary data agent
│   ├── hiring_signals.py          # Hiring velocity detector
│   ├── contact_finder.py          # Find hiring managers via SerpAPI
│   ├── outreach.py                # Message gen + sequence manager + Gmail send
│   ├── autofill.py                # ATS autofill (Greenhouse + Lever)
│   ├── analytics.py               # Response rates + outcome tracker + Claude analysis
│   ├── digest.py                  # Daily digest data (also used by Home.py)
│   └── referral_detector.py       # LinkedIn CSV cross-reference
├── tools/
│   ├── __init__.py
│   ├── llm.py                     # Claude API wrapper + prompt templates
│   ├── scraper.py                 # JobSpy wrapper + LinkedIn description fetcher
│   ├── glassdoor.py               # Playwright Glassdoor scraper
│   ├── levelsfyi.py               # levels.fyi comp + company meta fetcher
│   ├── leetcode.py                # LeetCode company problem fetcher
│   ├── stackshare.py              # StackShare tech stack scraper
│   ├── search.py                  # SerpAPI wrapper
│   ├── gmail_auth.py              # One-time Gmail OAuth flow
│   └── ats/
│       ├── greenhouse.py          # Greenhouse form autofill
│       └── lever.py               # Lever form autofill
├── tools/prompts/                 # Prompt templates as .txt files
├── tests/                         # pytest test files (205 tests)
└── data/
    ├── base_resume.docx           # User's master resume (user provides)
    ├── resume_parsed.json         # Cached parsed resume (auto-generated)
    ├── scraper_state.json         # Last scrape timestamp (auto-generated)
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
- [x] **Bug fix:** `load_prompt()` switched from `str.format(**kwargs)` to manual `str.replace()` — `str.format` treated every `{...}` in prompt files as a variable, breaking any prompt that included JSON examples. Now only named variables passed as kwargs are substituted.
- [x] 10 pytest tests in `tests/test_llm.py` — all passing, no real API calls (mocked)

**What was built:**
`tools/llm.py` is the single entry point for all Claude API calls in the project. `ClaudeClient.chat()` returns a plain string. `chat_json()` appends a JSON instruction to the system prompt, strips any markdown fences from the response, and parses the result into a Python dict — if parsing fails it retries once with a clearer prompt. `load_prompt()` reads `.txt` template files from `tools/prompts/` and fills in `{variables}` using targeted string replacement — safe to include JSON examples directly in prompt files without escaping.

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

**Bug fix — NaN descriptions stored as "nan":** JobSpy uses pandas internally. Missing description fields came back as `float('nan')`, which is truthy in Python, so `str(nan or "")` produced the literal string `"nan"` instead of empty string. Fixed with `_clean_str()` helper that explicitly checks `math.isnan()` before converting. Jobs without descriptions now store `""` and are excluded from scoring automatically.

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
- [x] `JD` column added to `jobs` table — green ✓ if job has a description, red ✗ if missing; makes it immediately clear which jobs can be scored/tailored
- [x] `show` command detects missing ATS/reasoning data and tells you whether to re-score or explains the job has no description
- [x] `jobs --recent` flag added — sorts by most recently posted instead of fit score, works across all modes (scored, applied, all)
- [x] `jobs --all` bypasses the 25-item default limit — shows every job in the DB
- [x] `python main.py parse-resume` command — exposes `force=True` via CLI so users can bust the resume cache after updating `data/base_resume.docx`
- [x] `python main.py fetch-descriptions` command — backfills missing descriptions for LinkedIn jobs scraped before `linkedin_fetch_description=True` was added; hits LinkedIn's public jobs-guest API with 1–3s random delays
- [x] `linkedin_fetch_description=True` added to `_scrape_one()` — all future LinkedIn scrapes include full descriptions

**What was built:**
The daily workflow is now: `search` → `score --recent --limit 10` → `jobs` → `jobs --search "company"` → `show --job-id X` → `mark-applied --job-id X`. Applied jobs are hidden automatically so the list stays focused. `--search` solves "I remember the company but can't find the ID" without needing a database UI. `parse-resume --force` is the correct way to refresh the resume cache after updating your base resume — all downstream agents (scorer, tailor, cover letter, prep) read from this cache.

---

### PHASE 3 — Application Prep ✅ COMPLETE — 16 tests passing
**Goal:** Generate tailored application materials per job.
**Depends on:** Phase 2 complete

#### Task 3.1 — Resume Tailor ✅ COMPLETE
- [x] `agents/resume_tailor.py` — `tailor_resume(job, resume_data, gap_analysis)` rewrites bullets using reframe_suggestions from gap analysis
- [x] `_extract_bullets()` reads all bullet paragraphs from docx (skips short lines, all-caps headers)
- [x] Claude returns exact original → rewritten mappings; replaced in a fresh copy via string matching on paragraph text
- [x] Saved to `data/resume_versions/resume_{job_id}.docx` — base resume never modified
- [x] `ResumeVersion` DB record created with file path and changes summary
- [x] `python main.py tailor --job-id <id>` wired up, prints bullet count and changes summary
- [x] 8 pytest tests — all passing

**What was built:**
`tailor_resume()` reads `data/base_resume.docx`, extracts all body paragraphs > 30 chars, and sends them to Claude along with the JD and reframe suggestions from the gap analyzer. Claude returns a list of `{original, rewritten}` pairs. These are matched back to the docx paragraphs by exact string and replaced in a copy — run formatting (bold, italic) is preserved. The result is saved as `data/resume_versions/resume_{job_id}.docx`. The base resume is never touched.

#### Task 3.2 — Cover Letter Generator ✅ COMPLETE
- [x] `agents/cover_letter.py` — `generate_cover_letter(job, resume_data, company_research=None)` generates a tailored cover letter
- [x] Prompt includes: JD, skills, experience summary, hard gaps, soft gaps, and reframe suggestions
- [x] `company_research` param reserved for Phase 4.1 — already in the signature so Phase 4 can enrich it without changing the interface
- [x] `_write_docx()` builds formatted `.docx` with subject line header + paragraph body split on `\n\n`
- [x] Saved to `data/cover_letters/cover_letter_{job_id}.docx`
- [x] `python main.py cover-letter --job-id <id>` wired up, prints path, subject line, and word count
- [x] 8 pytest tests — all passing (54/54 total)

**What was built:**
`generate_cover_letter()` builds a prompt with the full JD, candidate skills and experience summary, and the gap analysis output (hard gaps, soft gaps, reframe suggestions). Claude is instructed to write a direct 3–4 paragraph cover letter under 350 words — no generic openers, no filler phrases. The result is saved as a formatted `.docx` with proper margins and font sizing. Phase 4 company research will plug in via the `company_research` param to add company-specific talking points.

---

### PHASE 3.5 — Interview Prep Agent ✅ COMPLETE — 41 tests passing
**Goal:** Full interview preparation suite triggered once a job is worth pursuing.
**Depends on:** Phase 2 (gap analyzer), Phase 3 (application prep)

#### Task 3.5.1 — Real Interview Data (LeetCode + Glassdoor + levels.fyi) ✅ COMPLETE
**Goal:** Ground technical questions in real reported data instead of Claude inference. Three sources, each adds a different layer.

**Why each source:**
- **LeetCode** — company-tagged problems with difficulty and frequency data. Tells you *exactly* which coding problems a company has asked historically. Sourced from public GitHub dataset (663 companies, no auth).
- **Glassdoor** — past candidates write out the actual questions they were asked in interviews. Covers system design, behavioral, and technical. Playwright scrapes what's visible before the login wall (typically 5–15 questions).
- **levels.fyi** — originally planned for interview round data, but levels.fyi removed their interview section. Pivoted to comp data (salary, equity, total comp by role) which is useful for offer evaluation and comp discussion rounds.
- **Blind** — skipped. Mobile-first app, requires hard auth, no public web endpoint worth scraping.

##### Task 3.5.1a — LeetCode Company Problem Fetcher ✅ COMPLETE
- [x] `tools/leetcode.py` — fetches from `snehasishroy/leetcode-companywise-interview-questions` GitHub dataset (663 companies, no auth required)
- [x] `_company_slug()` normalizes company name to dataset slug (e.g. "Goldman Sachs" → "goldman-sachs", "J.P. Morgan" → "jp-morgan")
- [x] Tries time windows in order: `three-months` → `six-months` → `all` (most recent data first)
- [x] Returns top 20 problems sorted by frequency with title, difficulty, URL, frequency%, acceptance%
- [x] Stored in `InterviewPrep.technical_questions["LeetCode"]` as formatted strings
- [x] Passed to Claude as context so technical questions are grounded in real company-specific data
- [x] Fallback: if company not found, logs a dim message and Claude generates questions from JD only
- [x] 12 pytest tests in `tests/test_leetcode.py` — all passing

**What was built:**
`tools/leetcode.py` hits the GitHub raw content API to pull a company's CSV of LeetCode problems. The data is real — sourced from LeetCode Premium company tags and maintained publicly. Problems come with frequency scores (how often that company asks them), so the top-20 list is signal-ranked. Claude receives this as context when generating technical questions, so instead of guessing, it knows "Stripe most commonly asks Invalid Transactions, Two Sum, and Merge Intervals" and can reference them directly. Raw problems are also stored in the DB under the `LeetCode` key for use in mock interviews.

##### Task 3.5.1b — Glassdoor Interview Review Scraper ✅ COMPLETE
- [x] `tools/glassdoor.py` — Playwright scraper for Glassdoor interview questions
- [x] `_find_employer_id()` resolves company name → Glassdoor employer ID via typeahead API
- [x] `_scrape_page()` renders the page headlessly, dismisses cookie/login modals, extracts question cards
- [x] Multiple CSS selector fallbacks — Glassdoor renames classes often, data-test attrs are more stable
- [x] Extracts per question: question text, difficulty rating, interview outcome
- [x] Stored in `InterviewPrep.technical_questions["Glassdoor"]`
- [x] Passed to Claude as `{glassdoor_context}` in technical questions prompt
- [x] Graceful fallback: returns `found: False` if blocked or company not found
- [x] 15 pytest tests in `tests/test_glassdoor.py` — all passing

**What was built:**
`tools/glassdoor.py` first resolves the company's Glassdoor employer ID via the typeahead API (so the URL includes the numeric ID for reliability), then uses Playwright to render the JS-heavy interview page. Login/cookie popups are dismissed automatically. The scraper tries multiple selector patterns to handle Glassdoor's frequently changing class names. Typically extracts 5–15 questions visible before the login wall.

##### Task 3.5.1c — levels.fyi Compensation Fetcher ✅ COMPLETE
- [x] `tools/levelsfyi.py` — fetches salary/comp data from levels.fyi's public LLM-readable markdown endpoint
- [x] `_company_slug()` normalizes company name to levels.fyi URL slug
- [x] Fetches `https://www.levels.fyi/companies/{slug}/salaries.md` — no auth, no scraping
- [x] Parses: median total comp, Software Engineer median, top 10 role medians
- [x] Stored in `InterviewPrep.company_questions["compensation"]`
- [x] `_format_compensation_context()` formats data for prompts
- [x] 14 pytest tests in `tests/test_levelsfyi.py` — all passing
- [x] **Pivot note:** levels.fyi removed their interview section. Comp data is what's available — useful for offer evaluation and discussing expectations during interviews.

**What was built:**
`tools/levelsfyi.py` uses levels.fyi's documented `.md` endpoint (they explicitly support LLM access via this format). No Playwright needed — plain `requests`. Parses markdown into structured comp data: median total comp, SWE median, and a breakdown by job family. Stored under `company_questions["compensation"]` so it's available during offer/negotiation discussions in mock interviews.

**How it integrates into `prep run`:**
```
python main.py prep run --job-id 12
  → [1/7] Fetch LeetCode company problems     (real data — GitHub dataset)
  → [2/7] Scrape Glassdoor interview reviews  (real data — Playwright)
  → [3/7] Fetch levels.fyi compensation data  (real data — markdown API)
  → [4/7] Generate technical questions        (Claude + LeetCode + Glassdoor context)
  → [5/7] Generate behavioral questions       (Claude)
  → [6/7] Generate company-specific prep      (Claude + comp data)
  → [7/7] Generate study plan                 (Claude + gap analysis)
```
Claude still runs but now has real data as context — so instead of guessing, it synthesizes and fills gaps around what was actually reported.

#### Task 3.5.2 — Tech Stack Question Generator ✅ COMPLETE
- [x] `generate_technical_questions(job, resume_data)` in `agents/interview_prep.py`
- [x] Claude extracts every technology from the JD and generates 3–5 questions per technology
- [x] Questions vary in difficulty — one foundational, at least one challenging
- [x] Stored as `{technology: [q1, q2, ...]}` in `InterviewPrep.technical_questions`
- [x] 2 pytest tests — passing

#### Task 3.5.3 — Behavioral Question Generator ✅ COMPLETE
- [x] `generate_behavioral_questions(job, resume_data)` in `agents/interview_prep.py`
- [x] Claude reads JD soft skill language and maps traits to STAR-format questions
- [x] Each question includes trait label and suggested answer framework tied to candidate's real experience
- [x] 8–10 questions stored in `InterviewPrep.behavioral_questions`
- [x] 2 pytest tests — passing

#### Task 3.5.4 — Company-Specific Prep ✅ COMPLETE
- [x] `generate_company_questions(job, resume_data)` in `agents/interview_prep.py`
- [x] Generates "why do you want to work here" talking points specific to this company and role
- [x] Generates 5–7 smart questions to ask the interviewer with a talking point for each
- [x] Stored in `InterviewPrep.company_questions` as `{questions: [...], why_us: [...]}`
- [x] Phase 4 company research will enrich this automatically once built
- [x] 2 pytest tests — passing

#### Task 3.5.5 — Mock Interview CLI Mode ✅ COMPLETE
- [x] `python main.py prep mock --job-id <id>` launches interactive CLI loop
- [x] Questions interleave: 2 technical → 1 behavioral → 1 company, repeat
- [x] User types answer; Claude scores 1–10 with specific critique and stronger answer example
- [x] `skip` skips a question, `quit` ends the session
- [x] Session saved to `InterviewPrep.mock_sessions` as `{timestamp, avg_score, qa_pairs}`
- [x] 2 pytest tests — passing

#### Task 3.5.6 — Study Plan Generator ✅ COMPLETE
- [x] `generate_study_plan(job, resume_data, gap_analysis)` in `agents/interview_prep.py`
- [x] Reads hard_gaps and soft_gaps from Phase 2.4 gap analysis
- [x] Claude generates prioritized study plan: topic, specific resources, estimated hours, why it matters
- [x] Skips Claude entirely if no gaps — saves API cost
- [x] Displayed as a Rich table with priority color-coding (red=high, yellow=medium)
- [x] Stored in `InterviewPrep.study_plan`
- [x] 3 pytest tests — passing

**What was built:**
`agents/interview_prep.py` orchestrates the full prep pipeline. `python main.py prep run --job-id <id>` runs all 7 steps (LeetCode → Glassdoor → levels.fyi → technical → behavioral → company → study plan) in sequence, prints a summary, and saves everything to the `InterviewPrep` table. Real data from all three sources is passed as context to Claude so questions are grounded in what this company actually asks. `python main.py prep mock --job-id <id>` launches an interactive CLI loop where Claude acts as the interviewer — each answer is scored and critiqued in real time. Sessions are saved for later review. Use `--force` to regenerate prep for a job you've updated.

---

### PHASE 4 — Intelligence & Research ✅ COMPLETE
**Goal:** Know the company deeply before applying or reaching out.
**Depends on:** Phase 1 (DB, scraper). Enriches Phase 3.2 and 3.5.4 retroactively.

#### Task 4.1 — Company Research Agent ✅ COMPLETE
- [x] `agents/company_research.py` — `research_company(company_name)` orchestrates all sources
- [x] Sources: Glassdoor rating (Playwright), recent news (SerpAPI), funding/stage (SerpAPI), tech stack (StackShare), layoff history (layoffs.fyi)
- [x] Claude synthesizes into a structured `CompanyResearch` record saved to DB
- [x] `get_cached_research(company)` — returns cached record to avoid redundant API calls
- [x] CLI: `python main.py research --company "Stripe"` + Research page in UI

#### Task 4.2 — Salary Intelligence Agent ✅ COMPLETE
- [x] `agents/salary_intel.py` — fetches levels.fyi `.md` endpoint (no auth, LLM-readable)
- [x] Claude extracts role-level range (±20% around median), stores in `SalaryData` table
- [x] Inputs: company name + role level (junior/mid/senior/staff/principal)
- [x] Output: salary_min, salary_max, equity_range, matched_role — cached per company+level
- [x] CLI: `python main.py salary --company "Stripe" --level senior` + salary section in Research page

#### Task 4.3 — Hiring Signal Detector ✅ COMPLETE
- [x] `agents/hiring_signals.py` — `get_surge_companies(days=7, min_jobs=3)` queries jobs table
- [x] Groups by company, returns sorted list of companies posting 3+ jobs in last 7 days
- [x] `get_surge_companies_set()` for O(1) lookup — used by `jobs` command to show ⚡ surge flag
- [x] Optional SerpAPI enrichment via `check_hiring_posts(company)` (skips gracefully if no key)
- [x] CLI: `python main.py signals` + surge section on Home page in UI

---

### PHASE 5 — Outreach ✅ COMPLETE
**Goal:** Get a human to see your application.
**Depends on:** Phase 4 complete (need company research before reaching out)

#### Task 5.1 — Referral Detector ✅ COMPLETE
- [x] `agents/referral_detector.py` — `load_connections(csv_path)` parses LinkedIn CSV export
- [x] Handles 3-line header format LinkedIn uses (notes line, blank line, real headers)
- [x] `find_referrals(job_company, connections)` — fuzzy match handles "Stripe" vs "Stripe, Inc."
- [x] `save_referrals_to_db(job_id, matches)` — upserts by linkedin_url
- [x] CLI: `python main.py referrals --job-id <id>` (requires `data/linkedin_connections.csv`)

#### Task 5.2 — Contact Finder ✅ COMPLETE
- [x] `agents/contact_finder.py` — SerpAPI `site:linkedin.com/in` queries for recruiters/EMs
- [x] `_parse_name_title(search_title, company)` parses "Jane Doe - Recruiter at Stripe | LinkedIn"
- [x] Stores found contacts in `Contact` table linked to job, upserts by linkedin_url
- [x] CLI: `python main.py find-contacts --job-id <id>` (requires SERPAPI_KEY)

#### Task 5.3 — Outreach Message Generator ✅ COMPLETE
- [x] `agents/outreach.py` — `generate_messages(contact, job, resume_data, company_intel)`
- [x] Claude writes LinkedIn DM (≤300 chars) and cold email (150–200 words) per contact
- [x] Both variants saved to `OutreachSequence` table per contact

#### Task 5.4 — Outreach Sequence Manager ✅ COMPLETE
- [x] `mark_sent(sequence_id)` — sets sent_at, schedules follow_up_due (+5 days), status="sent"
- [x] `mark_responded(sequence_id)` — sets response_received=True, status="responded"
- [x] `get_due_followups()` — returns sequences where follow_up_due ≤ now and not responded
- [x] `auto_ghost_stale()` — marks 10+ day old unresponded sequences as ghosted
- [x] `_send_gmail(to_email, subject, body)` — Gmail API send (requires token.json from OAuth)
- [x] CLI: `python main.py outreach --job-id <id>` / `--due` flag for follow-ups
- [x] `tools/gmail_auth.py` — one-time OAuth flow to generate token.json

---

### PHASE 6 — Auto-Application ✅ COMPLETE
**Goal:** Submit applications automatically via Playwright.
**Depends on:** Phase 3 complete (need tailored resume + cover letter before applying)
**Note:** Most brittle phase — ATS sites update their DOM frequently. Built with resilience in mind.

#### Task 6.1 — Greenhouse Autofill ✅ COMPLETE
- [x] Playwright selectors for standard Greenhouse application form
- [x] Claude answers custom questions using JD + resume context
- [x] Screenshot before/after for review
- [x] Log application to `Application` table on success

#### Task 6.2 — Lever Autofill ✅ COMPLETE
- [x] Same approach as Greenhouse for Lever ATS
- [x] Auto-appends `/apply` to Lever job URLs

#### Task 6.3 — Workday Autofill
- [ ] Not implemented — too brittle, custom per-company DOM. Apply manually.

#### Task 6.4 — LinkedIn Easy Apply
- [ ] Not implemented — requires LinkedIn session cookie management, high ban risk. Apply manually.

---

### PHASE 7 — Analytics & Feedback Loop ✅ COMPLETE
**Goal:** Make the system smarter over time.
**Depends on:** All previous phases generating data

#### Task 7.1 — Response Rate Analyzer ✅ COMPLETE
- [x] `agents/analytics.py` — queries `OutreachSequence` and `Application` tables
- [x] Computes: total sent, responded, ghosted, response rate %
- [x] Claude summarizes patterns and gives recommendations (needs 3+ applications)
- [x] `python main.py analytics` + Analytics page in UI

#### Task 7.2 — Interview Outcome Tracker ✅ COMPLETE
- [x] `python main.py outcome --job-id <id>` — interactive prompt to log stage + feedback
- [x] Claude analyzes feedback and suggests specific study topics to close the gap
- [x] Outcome logging also available in Analytics page in UI

#### Task 7.3 — Daily Digest ✅ COMPLETE
- [x] `python main.py digest` — terminal daily driver command
- [x] `Home.py` (Streamlit) — visual daily digest dashboard (home page of UI)
- [x] Sections: pipeline summary, new scored jobs (24h), follow-ups due, hiring surges, study plan

---

### PHASE 8 — Streamlit UI ✅ COMPLETE
**Goal:** Browser-based dashboard so everything is accessible without memorizing CLI commands.
**Depends on:** All previous phases
**Architecture:** Streamlit pages call agent functions directly — same code as CLI, no API layer.

#### Task 8.1 — Home / Daily Digest ✅ COMPLETE
- [x] `Home.py` — pipeline metrics, new jobs, follow-ups, surges, study plan in one view

#### Task 8.2 — Job Browser ✅ COMPLETE
- [x] `pages/1_Jobs.py` — filter by score/status/keyword, expand for full gap analysis
- [x] One-click navigate to Pipeline, Research, Prep for any job
- [x] Mark applied directly from job card

#### Task 8.3 — Pipeline Orchestrator ✅ COMPLETE
- [x] `pages/2_Pipeline.py` — select job, run all 5 steps with progress, download outputs
- [x] In-page display of salary intel and company summary after run
- [x] Dry-run and submit autofill buttons

#### Task 8.4 — Company Research ✅ COMPLETE
- [x] `pages/3_Research.py` — research form, cached results browser, salary lookup

#### Task 8.5 — Interview Prep ✅ COMPLETE
- [x] `pages/4_Prep.py` — tabbed view of technical/behavioral/company questions/study plan
- [x] In-browser mock interview with Claude scoring

#### Task 8.6 — Outreach ✅ COMPLETE
- [x] `pages/5_Outreach.py` — generate messages, view content, manage follow-ups, all contacts

#### Task 8.7 — Analytics ✅ COMPLETE
- [x] `pages/6_Analytics.py` — charts, Claude pattern analysis, outcome logging

#### Task 8.8 — Settings ✅ COMPLETE
- [x] `pages/7_Settings.py` — resume upload/parse, search/score controls, API key status, DB download

**How to run:**
```bash
streamlit run Home.py
# Opens at http://localhost:8501
```

---

## Command Reference

### CLI
```bash
python main.py db init                        # Initialize database
python main.py parse-resume                   # Parse resume (--force to re-parse)
python main.py search                         # Scrape new job listings
python main.py fetch-descriptions             # Backfill missing descriptions
python main.py score                          # Score and rank all unscored jobs
python main.py jobs                           # List scored jobs
python main.py show --job-id <id>             # Full details for one job
python main.py mark-applied --job-id <id>     # Mark job as applied
python main.py run --job-id <id>              # Full pipeline (orchestrator)
python main.py research --company <name>      # Run company research agent
python main.py salary --company <n> --level   # Get salary intel
python main.py signals                        # Detect hiring surges
python main.py tailor --job-id <id>           # Tailor resume for a job
python main.py cover-letter --job-id <id>     # Generate cover letter
python main.py apply --job-id <id>            # Autofill application (--submit to send)
python main.py prep run --job-id <id>         # Generate interview prep
python main.py prep mock --job-id <id>        # Start mock interview session
python main.py referrals --job-id <id>        # Check LinkedIn connections at company
python main.py find-contacts --job-id <id>    # Find recruiters via SerpAPI
python main.py outreach --job-id <id>         # Generate outreach messages
python main.py outreach --due                 # Show follow-ups due today
python main.py outcome --job-id <id>          # Log interview outcome
python main.py analytics                      # Analytics report
python main.py digest                         # Daily summary dashboard
```

### UI
```bash
streamlit run Home.py       # Start UI at http://localhost:8501
```

| Page | What you do there |
|---|---|
| 🏠 Home | Daily digest — see everything needing attention |
| 📋 Jobs | Browse, filter, read gap analysis |
| 🚀 Pipeline | Run research → tailor → cover letter → prep → salary in one click |
| 🏢 Research | Research a company, look up salary |
| 📚 Prep | Read prep questions, do mock interview |
| 📨 Outreach | Generate messages, manage follow-ups |
| 📊 Analytics | Stats, charts, log interview outcomes |
| ⚙️ Settings | Upload resume, run search/score, API key status |

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
