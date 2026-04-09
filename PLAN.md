# Job Application Agent Suite — Master Build Plan

## Project Overview
A CLI-based AI agent suite that automates the entire software engineering job application process.
Built with Python, Claude API, LangGraph, Playwright, and SQLite.

## Tech Stack
- **Language:** Python 3.11+
- **AI:** Anthropic Claude API (`claude-sonnet-4-20250514`)
- **Agent Orchestration:** LangGraph
- **CLI:** Typer
- **Browser Automation:** Playwright + Chromium
- **Database:** SQLite + SQLAlchemy
- **Job Scraping:** JobSpy
- **Search:** SerpAPI or Brave Search API
- **Email:** Gmail API + smtplib
- **Resume/Doc editing:** python-docx
- **Scheduling:** APScheduler

## Folder Structure
```
job-agent/
├── main.py                        # Typer CLI entry point
├── config.py                      # API keys, user prefs, .env loader
├── requirements.txt
├── .env.example
├── db/
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy ORM models
│   └── session.py                 # DB session factory
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py            # LangGraph master agent
│   ├── searcher.py                # Job scraping + dedup
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
└── data/
    ├── base_resume.docx           # User's master resume (user provides)
    ├── resume_versions/           # Tailored resumes per job (auto-generated)
    ├── cover_letters/             # Cover letters per job (auto-generated)
    └── jobs.db                    # SQLite database (auto-generated)
```

## Database Models (db/models.py)
Define these SQLAlchemy models:
- `Job` — id, title, company, url, description, source, posted_date, fit_score, ats_score, status, created_at
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

### PHASE 1 — Foundation
**Goal:** Scaffolding, DB, Claude wrapper, job scraper. Everything else depends on this.
**Estimated Time:** 4–5 days

#### Task 1.1 — Project Scaffolding & Config
- [ ] Initialize project folder structure as shown above
- [ ] Create `requirements.txt` with all dependencies
- [ ] Create `.env.example` with required keys: `ANTHROPIC_API_KEY`, `SERPAPI_KEY`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`
- [ ] Create `config.py` that loads `.env` and exposes typed config values
- [ ] Create `main.py` Typer CLI skeleton with placeholder commands: `search`, `score`, `apply`, `outreach`, `prep`, `digest`

#### Task 1.2 — Database Schema
- [ ] Create all SQLAlchemy models listed above in `db/models.py`
- [ ] Create `db/session.py` with session factory and `init_db()` function
- [ ] Add `alembic` for migrations
- [ ] Write a `python main.py db init` CLI command that initializes the database

#### Task 1.3 — Claude Wrapper / LLM Core
- [ ] Create `tools/llm.py` with a reusable `ClaudeClient` class
- [ ] Support `chat()`, `chat_json()` (forces JSON response), and `chat_with_system()` methods
- [ ] Add prompt template loader — store prompts as `.txt` files in `tools/prompts/`
- [ ] Add retry logic and error handling
- [ ] Model to use: `claude-sonnet-4-20250514`

#### Task 1.4 — Job Scraper
- [ ] Create `tools/scraper.py` wrapping JobSpy for LinkedIn, Indeed, Glassdoor
- [ ] Filter to software engineer roles only (configurable keywords in config)
- [ ] Implement deduplication by URL before inserting to DB
- [ ] Track `last_scraped_at` so subsequent runs only fetch new listings
- [ ] Implement `python main.py search` CLI command that triggers scraper and reports new jobs found

---

### PHASE 2 — Scoring & Prioritization
**Goal:** Rank jobs before spending time on any of them.
**Estimated Time:** 3–4 days
**Depends on:** Phase 1 complete

#### Task 2.1 — Resume Parser
- [ ] Create a function in `tools/llm.py` that reads `data/base_resume.docx` using `python-docx`
- [ ] Extract structured data: skills, experience entries (company/title/bullets), education
- [ ] Store as a Python dict that gets passed into all scoring/tailoring prompts

#### Task 2.2 — Fit Scorer
- [ ] In `agents/scorer.py`, build a `score_fit(job, resume_data)` function
- [ ] Claude prompt: given JD + resume, return JSON with `fit_score` (1–10), `matching_skills`, `missing_skills`, `reasoning`
- [ ] Update `Job.fit_score` in DB after scoring
- [ ] CLI: `python main.py score` — scores all unscored jobs, prints ranked list

#### Task 2.3 — ATS Keyword Checker
- [ ] Extract keywords from JD using Claude (role-specific terms, technologies, certifications)
- [ ] Cross-reference against resume text
- [ ] Return `ats_score` (% of key terms present) and `missing_keywords` list
- [ ] Store on `Job` model

#### Task 2.4 — Gap Analyzer
- [ ] Claude prompt: given missing skills from 2.2 and missing keywords from 2.3, generate a `gap_analysis` JSON
- [ ] Fields: `hard_gaps` (can't frame around), `soft_gaps` (can reframe), `reframe_suggestions` (how to cover soft gaps with existing experience)
- [ ] Store on `Job` model as JSON field
- [ ] This output feeds directly into Phase 3.1 (resume tailor) and Phase 3.5.6 (study plan)

---

### PHASE 3 — Application Prep
**Goal:** Generate tailored application materials per job.
**Estimated Time:** 2–3 days
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
**Estimated Time:** 6–7 days
**Depends on:** Phase 2 (gap analyzer), Phase 3 (application prep). Phase 4.1 (company research) will enrich 3.5.4 retroactively.

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
- [ ] Note: this step gets significantly richer once Phase 4.1 (company research agent) is complete — add a hook to re-run this step with company research data when available

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
**Estimated Time:** 5 days
**Depends on:** Phase 1 (DB, scraper). Enriches Phase 3.2 and 3.5.4 retroactively.

#### Task 4.1 — Company Research Agent
- [ ] In `agents/company_research.py`, build `research_company(company_name)`
- [ ] Sources to pull: Glassdoor rating (Playwright), recent news (SerpAPI), funding/stage (Crunchbase scrape or SerpAPI), tech stack (StackShare or Builtwith), layoff history (layoffs.fyi scrape)
- [ ] Claude synthesizes into a structured `CompanyResearch` record
- [ ] CLI: `python main.py research --company "Stripe"`
- [ ] After building this, re-run cover letter and company-specific prep for any jobs already in DB

#### Task 4.2 — Salary Intelligence Agent
- [ ] In `agents/salary_intel.py`, scrape Levels.fyi and Glassdoor for comp data
- [ ] Inputs: company name + role level (junior/mid/senior)
- [ ] Output: salary range, equity range, bonus, total comp — stored in `SalaryData`
- [ ] CLI: `python main.py salary --company "Stripe" --level senior`
- [ ] Use this to auto-flag jobs that are likely underpaying based on your target comp

#### Task 4.3 — Hiring Signal Detector
- [ ] Monitor job posting velocity: if a company posts 3+ eng roles in 7 days, flag as "hiring surge"
- [ ] This runs automatically during `python main.py search` — check posting counts per company in DB
- [ ] Also use SerpAPI to find LinkedIn posts where employees say "we're hiring"
- [ ] Boost `fit_score` priority for companies with active hiring signals

---

### PHASE 5 — Outreach
**Goal:** Get a human to see your application.
**Estimated Time:** 6 days
**Depends on:** Phase 4 complete (need company research before reaching out)

#### Task 5.1 — Referral Detector
- [ ] User exports LinkedIn connections as CSV (Settings → Data Export)
- [ ] `python main.py referrals --job-id <id>` cross-references CSV against job's company
- [ ] Outputs matching connections with their title and LinkedIn URL
- [ ] Highest ROI feature in the entire suite — always check before cold outreach

#### Task 5.2 — Contact Finder
- [ ] In `agents/contact_finder.py`, use SerpAPI to search `site:linkedin.com [company] recruiter software engineer`
- [ ] Also search for engineering managers at the target team if inferable from JD
- [ ] Playwright to visit and parse LinkedIn profiles
- [ ] Store found contacts in `Contact` model linked to job

#### Task 5.3 — Outreach Message Generator
- [ ] Claude writes personalized LinkedIn DM or email using: contact name/title, company research, your background, the specific role
- [ ] Two variants per contact: short LinkedIn DM (300 chars) and longer email version
- [ ] Never generic — every message references something specific about the company or role

#### Task 5.4 — Outreach Sequence Manager
- [ ] In `agents/outreach.py`, manage full send → follow-up → ghost lifecycle
- [ ] Day 0: send initial message via Gmail API
- [ ] Day 5: if no response, send follow-up
- [ ] Day 10: mark as ghosted
- [ ] `python main.py outreach --due` shows all follow-ups due today
- [ ] All state tracked in `OutreachSequence` table

---

### PHASE 6 — Auto-Application
**Goal:** Submit applications automatically via Playwright.
**Estimated Time:** 8–12 days
**Depends on:** Phase 3 complete (need tailored resume + cover letter before applying)
**Note:** Most brittle phase — ATS sites update their DOM frequently. Build with resilience in mind.

#### Task 6.1 — Greenhouse Autofill
- [ ] Playwright selectors for standard Greenhouse application form
- [ ] Fill: name, email, phone, LinkedIn, resume upload, cover letter upload, custom questions
- [ ] Claude answers custom questions using JD + resume context
- [ ] Log application to `Application` table on success

#### Task 6.2 — Lever Autofill
- [ ] Same approach as Greenhouse for Lever ATS
- [ ] Lever forms are simpler — should be faster to build

#### Task 6.3 — Workday Autofill
- [ ] Workday is the most complex — expect significant Playwright work
- [ ] Multi-step forms, dynamic fields, login-wall behavior
- [ ] Build with extra error handling and screenshot-on-failure for debugging

#### Task 6.4 — LinkedIn Easy Apply
- [ ] Playwright automation for LinkedIn Easy Apply flow
- [ ] Handle multi-step and single-step variants
- [ ] Requires LinkedIn session cookie management

---

### PHASE 7 — Analytics & Feedback Loop
**Goal:** Make the system smarter over time.
**Estimated Time:** 3–5 days
**Depends on:** All previous phases generating data

#### Task 7.1 — Response Rate Analyzer
- [ ] Query `OutreachSequence` and `Application` tables to compute response rates
- [ ] Break down by: resume version, outreach message type, job source, company size, role type
- [ ] Claude summarizes patterns: "Your response rate is 3x higher for Series B startups vs FAANG"

#### Task 7.2 — Interview Outcome Tracker
- [ ] `python main.py outcome --job-id <id>` prompts user to log interview result
- [ ] Fields: stage reached, rejection reason, feedback received
- [ ] Claude analyzes patterns across outcomes + mock interview sessions from 3.5.5
- [ ] Generates actionable insight: "You're consistently reaching final rounds but losing on system design"
- [ ] Feeds updated study plan back to Phase 3.5.6

#### Task 7.3 — Daily Digest Command
- [ ] `python main.py digest` — the daily driver command
- [ ] Output sections:
  - New jobs found since last run, ranked by fit score
  - Follow-ups due today (from outreach sequences)
  - Companies with hiring surges detected
  - Your current pipeline: X applied / Y responded / Z interviewing
  - Any study plan items due today
- [ ] Keep output clean and scannable — this is what you run every morning

---

## CLI Command Reference (Final State)
```bash
python main.py db init              # Initialize database
python main.py search               # Scrape new job listings
python main.py score                # Score and rank all unscored jobs
python main.py research --company   # Run company research agent
python main.py salary --company --level  # Get salary intel
python main.py prep --job-id        # Generate interview prep for a job
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
GMAIL_REFRESH_TOKEN=
LINKEDIN_EMAIL=           # for linkedin-api / Playwright sessions
LINKEDIN_PASSWORD=
TARGET_ROLES=Software Engineer,Backend Engineer,Full Stack Engineer
TARGET_LOCATIONS=Remote,San Francisco,New York
MIN_FIT_SCORE=6           # only prep materials for jobs above this threshold
TARGET_COMP_MIN=150000    # flag jobs likely below this
```

## Dependencies (requirements.txt)
```
anthropic
langgraph
langchain-core
typer
sqlalchemy
alembic
jobspy
playwright
serpapi
python-docx
pypdf2
apscheduler
google-auth
google-auth-oauthlib
google-api-python-client
linkedin-api
requests
python-dotenv
rich                      # for pretty CLI output
```
