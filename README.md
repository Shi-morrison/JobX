# JobX

An AI-powered job application suite that automates the entire software engineering job search — from scraping listings to scoring fit, tailoring resumes, generating cover letters, prepping for interviews, outreach, and auto-applying.

Two interfaces, same underlying code:
- **CLI** (`python main.py <command>`) — terminal commands, best for batch operations and debugging
- **UI** (`streamlit run Home.py`) — browser dashboard, best for browsing, reviewing, and one-click actions

Built with Python, Claude AI, SQLite, Playwright, and Streamlit.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Requirements](#requirements)
- [Setup](#setup)
- [The Fast Path](#the-fast-path)
- [Streamlit UI](#streamlit-ui)
- [Commands](#commands)
  - [parse-resume](#parse-resume)
  - [search](#search)
  - [fetch-descriptions](#fetch-descriptions)
  - [score](#score)
  - [jobs](#jobs)
  - [show](#show)
  - [mark-applied](#mark-applied)
  - [research](#research)
  - [salary](#salary)
  - [signals](#signals)
  - [tailor](#tailor)
  - [cover-letter](#cover-letter)
  - [run](#run)
  - [apply](#apply)
  - [prep run](#prep-run)
  - [prep mock](#prep-mock)
  - [referrals](#referrals)
  - [find-contacts](#find-contacts)
  - [outreach](#outreach)
  - [outcome](#outcome)
  - [analytics](#analytics)
  - [digest](#digest)
- [Daily Workflow](#daily-workflow)
- [Database](#database)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)

---

## What It Does

| Phase | Feature | Status |
|---|---|---|
| 1 | Job scraping (LinkedIn + Indeed) with full descriptions | ✅ Live |
| 2 | Resume parsing + fit scoring + ATS check + gap analysis | ✅ Live |
| 2.5 | Job lifecycle: search, filter, mark-applied, applied pipeline | ✅ Live |
| 3 | Resume tailoring + cover letter generation | ✅ Live |
| 3.5 | Interview prep: LeetCode + Glassdoor data, questions, mock sessions, study plan | ✅ Live |
| 4 | Company research + salary intelligence + hiring signals | ✅ Live |
| 5 | Contact finding + outreach sequences + Gmail send | ✅ Live |
| 6 | Auto-application (Greenhouse + Lever autofill) | ✅ Live |
| 7 | Analytics + interview outcome tracking + daily digest | ✅ Live |
| 8 | Streamlit browser UI — all features accessible without CLI | ✅ Live |

---

## Requirements

- Python 3.11+
- A `.env` file (copy from `.env.example`)
- Your resume at `data/base_resume.docx`
- An [Anthropic API key](https://console.anthropic.com/) (required for Phase 2+)

---

## Setup

**1. Clone and create a virtual environment:**
```bash
git clone <repo-url>
cd JobX
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
playwright install chromium
```

**3. Configure your environment:**
```bash
cp .env.example .env
```
Open `.env` and fill in at minimum:
- `ANTHROPIC_API_KEY` — required for all AI features
- `TARGET_ROLES` — JSON array, e.g. `["Backend Engineer", "Software Engineer"]`
- `TARGET_LOCATIONS` — JSON array, e.g. `["Remote", "New York"]`

Optional keys unlock more features (see [Environment Variables](#environment-variables)).

**4. Add your resume:**

Place your resume at `data/base_resume.docx`. JobX never modifies this file.

**5. Initialize the database:**
```bash
python main.py db init
```

**6. Parse your resume:**
```bash
python main.py parse-resume
```
Sends your resume to Claude once and caches the result. All scoring, tailoring, and prep reads from this cache. Re-run with `--force` after updating your resume.

---

## The Fast Path

Three commands to find a good job and generate everything for it:

```bash
# 1. Find and score jobs
python main.py search --location remote --level senior
python main.py score --recent --limit 10
python main.py jobs                          # pick a job ID

# 2. Run the full pipeline in one shot
python main.py run --job-id 42

# 3. Review outputs, then apply
python main.py apply --job-id 42 --submit
python main.py mark-applied --job-id 42
```

`run` chains: company research → resume tailor → cover letter → interview prep → salary intel.

---

## Streamlit UI

A browser dashboard that calls the same agent functions as the CLI — no API layer, no separate backend.

```bash
streamlit run Home.py
# Opens at http://localhost:8501
```

| Page | What you do there |
|---|---|
| 🏠 Home | Daily digest — pipeline metrics, new jobs, follow-ups due, hiring surges, study plan |
| 📋 Jobs | Browse and filter jobs, read gap analysis, one-click navigate to Pipeline/Prep/Research |
| 🚀 Pipeline | Select a job and run all 5 steps (research → tailor → cover letter → prep → salary) with progress bar. Downloads and apply buttons at the end. |
| 🏢 Research | Research a company, browse cached results, look up salary intel |
| 📚 Prep | Read technical/behavioral/company questions, study plan, and run a mock interview with Claude scoring |
| 📨 Outreach | Generate messages for contacts, view message content, manage follow-ups, see all contacts |
| 📊 Analytics | Pipeline stats, charts, Claude pattern analysis, log interview outcomes |
| ⚙️ Settings | Upload/re-parse resume, run search/score, check API key status, download DB |

**Note:** Long-running operations (scoring, prep, pipeline) block the browser tab while running — progress is shown in the terminal. For personal use this is acceptable.

---

## Commands

> Every command supports `--help`:
> ```bash
> python main.py --help
> python main.py score --help
> python main.py prep --help
> ```

---

### parse-resume

```bash
python main.py parse-resume
python main.py parse-resume --force
```

Parses `data/base_resume.docx` with Claude and caches the result to `data/resume_parsed.json`. All agents (scorer, tailor, cover letter, prep) read from this cache.

**Run `--force` after updating your resume**, then re-score with `python main.py score --force`.

| Flag | Description |
|---|---|
| `--force` | Re-parse even if cache exists |

---

### search

```bash
python main.py search
```

Scrapes new job listings from LinkedIn and Indeed. Tracks last run time — subsequent runs only pull listings newer than the last scrape. Descriptions are fetched automatically.

| Flag | Description |
|---|---|
| `--hours-back INTEGER` | How far back to search (default: auto since last run) |
| `--location TEXT` | Override TARGET_LOCATIONS — `"remote"` or a city like `"New York"` |
| `--level TEXT` | Seniority filter: `intern`, `junior`, `mid`, `senior`, `staff` |
| `--results INTEGER` | Max listings per role/location combo (default: 15) |

```bash
python main.py search
python main.py search --location remote --level senior
python main.py search --location "New York" --hours-back 48 --results 20
```

---

### fetch-descriptions

```bash
python main.py fetch-descriptions
```

Backfills missing descriptions for LinkedIn jobs scraped without one. Needed only for jobs already in your DB — new scrapes include descriptions automatically.

| Flag | Description |
|---|---|
| `--limit INTEGER` | Max jobs to backfill (default: all) |

---

### score

```bash
python main.py score
```

Scores unscored jobs with Claude — returns fit score (1–10), ATS keyword coverage, gap analysis with hard gaps, soft gaps, and reframe suggestions. Results are color-coded (green ≥7, yellow ≥5, red <5).

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Score one specific job |
| `--limit INTEGER` | Max jobs to score in this run |
| `--recent` | Score most recently posted first (fewest applicants) |
| `--min-score INTEGER` | Only display results at or above this score |
| `--show-reasoning` | Print Claude's reasoning under each score |
| `--force` | Re-score already-scored jobs |

```bash
python main.py score                               # score all unscored jobs
python main.py score --recent --limit 10          # score 10 most recently posted
python main.py score --job-id 42                  # score one specific job
python main.py score --force --job-id 42          # re-score an already-scored job
```

---

### jobs

```bash
python main.py jobs
```

Lists scored jobs ranked by fit score. Applied jobs are hidden by default. The `⚡` column flags companies with a hiring surge (3+ postings in the last 7 days). The `JD` column shows `✓` if a description is available.

| Flag | Description |
|---|---|
| `--search TEXT` | Filter by keyword in title or company |
| `--min-score INTEGER` | Only show jobs at or above this fit score |
| `--limit INTEGER` | Max jobs to show (default: 25) |
| `--recent` | Sort by most recently posted instead of fit score |
| `--unscored` | Show only unscored jobs |
| `--applied` | Show your applied job pipeline |
| `--all` | Every job in the database |

```bash
python main.py jobs                        # scored jobs ranked by fit score
python main.py jobs --recent --limit 50    # 50 most recently posted
python main.py jobs --search "stripe"      # find jobs at Stripe
python main.py jobs --min-score 7          # only high-fit jobs
python main.py jobs --unscored             # find IDs to score
python main.py jobs --applied              # your applied pipeline
python main.py jobs --all                  # everything in the DB
```

---

### show

```bash
python main.py show --job-id <id>
```

Full details for a single job: fit score, ATS coverage, fit reasoning, hard gaps, soft gaps, and reframe suggestions. Find IDs with `python main.py jobs`.

---

### mark-applied

```bash
python main.py mark-applied --job-id <id>
```

Marks a job as applied. Applied jobs are hidden from the default `jobs` list and tracked under `--applied`.

---

### research

```bash
python main.py research --company "Stripe"
```

Researches a company from multiple sources: levels.fyi (funding stage, valuation, employee count, industry), Glassdoor (overall rating), StackShare (tech stack), and SerpAPI (recent news + layoff history, requires `SERPAPI_KEY`). Claude synthesizes a 2–3 sentence summary and flags stability signals.

Results are cached and automatically used by `cover-letter`, `prep run`, and `outreach`.

| Flag | Description |
|---|---|
| `--company TEXT` | Company name to research (required) |
| `--force` | Re-research even if cached |

```bash
python main.py research --company "Stripe"
python main.py research --company "Robinhood" --force
```

---

### salary

```bash
python main.py salary --company "Stripe" --level senior
```

Fetches compensation data from levels.fyi, uses Claude to extract a role-level-specific range (±20% around median), and caches the result.

| Flag | Description |
|---|---|
| `--company TEXT` | Company name (required) |
| `--level TEXT` | `junior`, `mid`, `senior`, `staff`, `principal` (required) |
| `--force` | Re-fetch even if cached |

```bash
python main.py salary --company "Stripe" --level senior
python main.py salary --company "Google" --level staff
```

---

### signals

```bash
python main.py signals
```

Detects companies with a hiring surge — 3+ engineering roles posted in the last N days. High-signal targets: more open roles = more chances. Surge companies are also flagged with `⚡` in the `jobs` list.

| Flag | Description |
|---|---|
| `--days INTEGER` | Look-back window (default: 7) |
| `--min-jobs INTEGER` | Minimum postings to count as a surge (default: 3) |
| `--serpapi` | Also search for "we're hiring" posts on LinkedIn (requires `SERPAPI_KEY`) |

```bash
python main.py signals
python main.py signals --days 14 --min-jobs 2
```

---

### tailor

```bash
python main.py tailor --job-id <id>
```

Rewrites resume bullets to match a specific job using gap analysis reframe suggestions. Saves to `data/resume_versions/resume_<id>.docx`. Base resume is never modified.

Requires the job to be scored first.

---

### cover-letter

```bash
python main.py cover-letter --job-id <id>
```

Generates a tailored cover letter using your experience, the job description, gap analysis, and cached company research. Saves to `data/cover_letters/cover_letter_<id>.docx`.

Requires the job to be scored first.

---

### run

```bash
python main.py run --job-id <id>
```

**The orchestrator.** Runs the full pipeline for a job in one command: company research → resume tailor → cover letter → interview prep → salary intel. All steps skip gracefully if outputs already exist.

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Job to process (required) |
| `--apply` | Also run autofill dry-run at the end |
| `--level TEXT` | Role level for salary lookup (default: `senior`) |
| `--force` | Re-run all steps even if outputs exist |

```bash
python main.py run --job-id 42                  # full pipeline
python main.py run --job-id 42 --apply          # also fill the application form
python main.py run --job-id 42 --force          # re-run everything
python main.py run --job-id 42 --level staff    # use staff level for salary
```

---

### apply

```bash
python main.py apply --job-id <id>
```

Fills an application form via Playwright. Detects the ATS from the job URL, fills standard fields (name, email, phone, resume, cover letter) and answers custom questions with Claude. Takes a screenshot before submitting — always review it first.

**Supported:** Greenhouse (`greenhouse.io`), Lever (`lever.co`)  
**Not supported:** Workday, LinkedIn Easy Apply (apply manually for these)

Default is a dry run — fills but does NOT submit. Add `--submit` when ready.

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Job to apply for (required) |
| `--submit` | Actually submit the form (default: dry run only) |

```bash
python main.py apply --job-id 42            # dry run — fill + screenshot
python main.py apply --job-id 42 --submit   # actually submit
```

---

### prep run

```bash
python main.py prep run --job-id <id>
```

Generates full interview prep in 7 steps:

1. **LeetCode problems** — real company-tagged problems from a public dataset (663 companies), sorted by frequency
2. **Glassdoor reviews** — Playwright-scraped interview questions reported by candidates
3. **levels.fyi comp data** — salary benchmarks for offer context
4. **Technical questions** — Claude generates questions per JD technology, grounded in LeetCode + Glassdoor data
5. **Behavioral questions** — STAR-format questions mapped to the JD's soft skill signals
6. **Company prep** — "why us" talking points and smart questions to ask the interviewer
7. **Study plan** — prioritized topics from gap analysis with resources and estimated hours

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Job to prepare for (required) |
| `--force` | Regenerate even if prep already exists |

---

### prep mock

```bash
python main.py prep mock --job-id <id>
```

Interactive mock interview. Claude acts as the interviewer — questions rotate through technical, behavioral, and company-specific. Each answer is scored 1–10 with critique and a stronger example. Type `skip` to skip a question, `quit` to end. Sessions are saved for later review.

Requires prep to be generated first: `python main.py prep run --job-id <id>`

---

### referrals

```bash
python main.py referrals --job-id <id>
```

Cross-references your LinkedIn connections CSV against the job's company to find warm contacts.

**Export your connections first:**  
LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections  
Save the downloaded CSV to `data/linkedin_connections.csv`

Found contacts are saved to the DB and used by `outreach`.

---

### find-contacts

```bash
python main.py find-contacts --job-id <id>
```

Searches for recruiters and engineering managers at the job's company via SerpAPI (`site:linkedin.com/in` search). Requires `SERPAPI_KEY`. Found contacts are saved for use by `outreach`.

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Job to find contacts for (required) |
| `--results INTEGER` | Max contacts to find (default: 5) |

---

### outreach

```bash
python main.py outreach --job-id <id>
python main.py outreach --due
```

Generates personalized LinkedIn DMs (≤300 chars) and emails for each saved contact using Claude, enriched with company research. Messages are stored in the DB. Optionally sends via Gmail (`--send`).

Run `referrals` or `find-contacts` first to populate contacts.

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Job to generate outreach for |
| `--messages` | Print the generated message text |
| `--send` | Send via Gmail (requires `token.json` OAuth setup — run `python tools/gmail_auth.py`) |
| `--due` | Show all follow-ups due today across all jobs |

```bash
python main.py outreach --job-id 42 --messages  # generate and display
python main.py outreach --job-id 42 --send      # generate and send via Gmail
python main.py outreach --due                   # follow-ups due today
```

**Gmail setup** (one-time):
```bash
# Fill GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env first
python tools/gmail_auth.py
```

---

### outcome

```bash
python main.py outcome --job-id <id>
```

Interactive prompt to log an interview outcome (stage reached, rejection reason, feedback). Claude analyzes the feedback and suggests specific study topics to close the gap. Outcomes feed into `analytics`.

---

### analytics

```bash
python main.py analytics
```

Shows application pipeline stats, outreach response rates, and outcome breakdown by fit score range. With 3+ applications, Claude identifies patterns and gives actionable recommendations (e.g. "response rate is higher for Series B startups").

---

### digest

```bash
python main.py digest
```

**The daily driver.** Shows everything you need to act on today:

1. Pipeline summary (scored / applied / interviewing / offers)
2. New scored jobs from the last 24 hours
3. Follow-ups due today
4. Active hiring surges
5. Study plan items from your latest prep session

---

## Daily Workflow

You can use the CLI, UI, or mix both — they share the same database.

```bash
# Morning: check what needs attention
python main.py digest
# or: open http://localhost:8501 (Home page)

# Pull fresh listings and score them
python main.py search
python main.py score --recent --limit 20

# Find a good job and run the full pipeline
python main.py jobs
python main.py run --job-id 42

# Apply
python main.py apply --job-id 42          # dry run, review screenshot
python main.py apply --job-id 42 --submit # submit
python main.py mark-applied --job-id 42

# Find contacts and send outreach
python main.py referrals --job-id 42
python main.py find-contacts --job-id 42  # requires SERPAPI_KEY
python main.py outreach --job-id 42 --messages

# Check hiring surges
python main.py signals

# Practice for an interview
python main.py prep mock --job-id 42

# Follow-ups
python main.py outreach --due

# After an interview
python main.py outcome --job-id 42
python main.py analytics
```

---

## Database

All data is stored locally in `data/jobs.db` — a single SQLite file. No cloud, no account, no cost.

Browse visually with the **SQLite Viewer** VS Code extension (`qwtel.sqlite-viewer`).

| Table | What it stores |
|---|---|
| `jobs` | Scraped listings with fit scores, ATS scores, gap analysis, and status |
| `resume_versions` | Tailored resumes per job with change summaries |
| `interview_prep` | Technical questions, behavioral, company prep, study plan, mock sessions |
| `applications` | Submitted applications with resume + cover letter paths |
| `contacts` | Recruiters and hiring managers found via referrals or SerpAPI |
| `outreach_sequences` | Message text, send status, follow-up dates |
| `company_research` | Company intel: funding, Glassdoor rating, tech stack, news |
| `salary_data` | Comp benchmarks from levels.fyi by role level |
| `interview_outcomes` | Interview results and feedback for analytics |

---

## Running Tests

```bash
pytest tests/ -v
```

205 tests — all mocked. No API calls, no network requests, no cost.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key — required for all AI features |
| `SERPAPI_KEY` | Optional | Enables news, layoffs, contact finder, hiring posts |
| `GMAIL_CLIENT_ID` | Optional | Gmail OAuth client ID — for `outreach --send` |
| `GMAIL_CLIENT_SECRET` | Optional | Gmail OAuth client secret |
| `LINKEDIN_EMAIL` | Optional | LinkedIn login — for future phases |
| `LINKEDIN_PASSWORD` | Optional | LinkedIn login — for future phases |
| `TARGET_ROLES` | Optional | JSON array of job titles to search for |
| `TARGET_LOCATIONS` | Optional | JSON array of locations (`"Remote"` for remote) |
| `MIN_FIT_SCORE` | Optional | Minimum fit score to generate materials for (default: 6) |
| `TARGET_COMP_MIN` | Optional | Minimum salary to flag underpaying roles (default: 150000) |
