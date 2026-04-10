# JobX

An AI-powered CLI suite that automates the software engineering job application process — from scraping listings to scoring fit, tailoring resumes, generating cover letters, prepping for interviews, and tracking outreach.

Built with Python, Claude AI, SQLite, and Playwright.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Requirements](#requirements)
- [Setup](#setup)
- [Commands](#commands)
  - [parse-resume](#parse-resume)
  - [search](#search)
  - [fetch-descriptions](#fetch-descriptions)
  - [score](#score)
  - [jobs](#jobs)
  - [show](#show)
  - [mark-applied](#mark-applied)
  - [tailor](#tailor)
  - [cover-letter](#cover-letter)
  - [prep run](#prep-run)
  - [prep mock](#prep-mock)
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
| 4 | Company research + salary intelligence + hiring signals | Planned |
| 5 | Contact finding + outreach sequences | Planned |
| 6 | Auto-application (Greenhouse, Lever, Workday, LinkedIn) | Planned |
| 7 | Analytics + feedback loop + daily digest | Planned |

---

## Requirements

- Python 3.11+
- A `.env` file (copy from `.env.example`)
- Your resume at `data/base_resume.docx`
- An [Anthropic API key](https://console.anthropic.com/) (for AI features — Phase 2+)

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
Open `.env` and fill in:
- `ANTHROPIC_API_KEY` — required for Phase 2+ (scoring, writing, prep)
- `TARGET_ROLES` — JSON array of job titles, e.g. `["Backend Engineer", "Software Engineer"]`
- `TARGET_LOCATIONS` — JSON array of locations, e.g. `["Remote", "New York"]`
- `MIN_FIT_SCORE` — minimum score (1–10) to generate materials for a job
- `TARGET_COMP_MIN` — minimum salary to flag underpaying roles

**4. Add your resume:**

Place your resume at `data/base_resume.docx`. JobX never modifies this file — it only reads from it.

**5. Initialize the database:**
```bash
python main.py db init
```

**6. Parse your resume:**
```bash
python main.py parse-resume
```
This sends your resume to Claude once and caches the result. All scoring, tailoring, and prep reads from this cache. Re-run with `--force` any time you update your resume.

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

Parses `data/base_resume.docx` with Claude and caches the result to `data/resume_parsed.json`. All agents (scorer, tailor, cover letter, prep) read from this cache — Claude is only called once.

**Run `--force` after updating your resume.** Followed by `python main.py score --force` to re-score jobs with the new resume.

| Flag | Description |
|---|---|
| `--force` | Re-parse even if cache exists |

---

### search

```bash
python main.py search
```

Scrapes new job listings from LinkedIn and Indeed based on your configured roles and locations. Results are stored in `data/jobs.db` and printed as a table. Tracks the last run time — subsequent runs only pull listings newer than the last scrape.

| Flag | Description |
|---|---|
| `--hours-back INTEGER` | How far back to search (default: auto since last run) |
| `--location TEXT` | Override TARGET_LOCATIONS — use `"remote"` or a city like `"New York"` |
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

Backfills missing descriptions for LinkedIn jobs that were scraped without one. Hits LinkedIn's public job API for each job with 1–3s delays between requests. Run `score` afterwards to score the newly described jobs.

> New scrapes automatically include descriptions — this is only needed for jobs already in your DB.

| Flag | Description |
|---|---|
| `--limit INTEGER` | Max jobs to backfill (default: all) |

```bash
python main.py fetch-descriptions
python main.py fetch-descriptions --limit 10
```

---

### score

```bash
python main.py score
```

Scores unscored jobs with Claude — returns fit score (1–10), matching skills, missing skills, ATS keyword coverage, gap analysis, and reasoning. Results are saved to the DB and printed as a color-coded table (green ≥7, yellow ≥5, red <5).

Skips jobs without a description. If all your unscored jobs lack descriptions, run `fetch-descriptions` first.

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Score one specific job |
| `--limit INTEGER` | Max jobs to score in this run |
| `--recent` | Score most recently posted jobs first (fewest applicants) |
| `--min-score INTEGER` | Only display results at or above this score |
| `--show-reasoning` | Print Claude's reasoning under each score |
| `--force` | Re-score already-scored jobs |

```bash
python main.py score                               # score all unscored jobs
python main.py score --limit 5                    # score next 5 unscored jobs
python main.py score --recent --limit 10          # score 10 most recently posted
python main.py score --recent --force --limit 10  # re-score 10 most recent
python main.py score --job-id 12                  # score one specific job
python main.py score --force --job-id 12          # re-score an already-scored job
```

---

### jobs

```bash
python main.py jobs
```

Lists scored jobs ranked by fit score. Applied jobs are hidden by default. The `JD` column shows `✓` if the job has a description (can be scored/tailored) or `✗` if missing.

| Flag | Description |
|---|---|
| `--search TEXT` | Filter by keyword in title or company. Case-insensitive. |
| `--min-score INTEGER` | Only show jobs at or above this fit score |
| `--limit INTEGER` | Max jobs to show (default: 25) |
| `--recent` | Sort by most recently posted instead of fit score |
| `--unscored` | Show only unscored jobs sorted by newest posted |
| `--applied` | Show your applied job pipeline |
| `--all` | Every job in the database — scored, unscored, and applied |

```bash
python main.py jobs                        # scored jobs ranked by fit score
python main.py jobs --recent               # scored jobs sorted by newest posted
python main.py jobs --search "stripe"      # find jobs at Stripe
python main.py jobs --min-score 7          # only high-fit jobs
python main.py jobs --unscored             # unscored jobs (find IDs to score)
python main.py jobs --applied              # your applied pipeline
python main.py jobs --all                  # everything in the DB
```

---

### show

```bash
python main.py show --job-id <id>
```

Full details for a single job: fit score, ATS coverage, fit reasoning, hard gaps, soft gaps, and reframe suggestions. Find IDs with `python main.py jobs` or `python main.py jobs --search "company"`.

```bash
python main.py show --job-id 12
```

---

### mark-applied

```bash
python main.py mark-applied --job-id <id>
```

Marks a job as applied and hides it from the default `jobs` list. Still accessible with `python main.py jobs --applied`.

```bash
python main.py mark-applied --job-id 12
```

---

### tailor

```bash
python main.py tailor --job-id <id>
```

Rewrites your resume bullets to match a specific job using the gap analysis reframe suggestions from scoring. Saves to `data/resume_versions/resume_<id>.docx`. Your base resume is never modified.

Requires the job to be scored first.

```bash
python main.py tailor --job-id 12
```

---

### cover-letter

```bash
python main.py cover-letter --job-id <id>
```

Generates a tailored cover letter using your experience, the job description, and gap analysis. Direct and concise — no generic openers. Saves to `data/cover_letters/cover_letter_<id>.docx`. Outputs the subject line and word count.

Requires the job to be scored first.

```bash
python main.py cover-letter --job-id 12
```

---

### prep run

```bash
python main.py prep run --job-id <id>
```

Generates full interview prep in 7 steps:

1. **LeetCode problems** — fetches real company-tagged problems sorted by frequency from a public GitHub dataset (663 companies). Falls back to Claude if company not in dataset.
2. **Glassdoor reviews** — Playwright scrapes reported interview questions from Glassdoor (5–15 questions typically visible before login wall).
3. **levels.fyi comp data** — fetches salary benchmarks (median total comp, SWE median, role breakdowns) for offer evaluation context.
4. **Technical questions** — Claude generates questions per JD technology, grounded in real LeetCode + Glassdoor data.
5. **Behavioral questions** — STAR-format questions mapped to the JD's soft skill signals.
6. **Company prep** — "why us" talking points and smart questions to ask the interviewer.
7. **Study plan** — prioritized topics from gap analysis with specific resources and estimated hours.

Requires the job to be scored first.

| Flag | Description |
|---|---|
| `--job-id INTEGER` | Job ID to prepare for (required) |
| `--force` | Regenerate even if prep already exists |

```bash
python main.py prep run --job-id 12
python main.py prep run --job-id 12 --force
```

---

### prep mock

```bash
python main.py prep mock --job-id <id>
```

Interactive mock interview session. Claude acts as the interviewer — questions rotate through technical, behavioral, and company-specific. Type your answer, get scored 1–10 with specific critique and a stronger example answer. Type `skip` to skip, `quit` to end. Sessions are saved to the DB for later review.

Requires prep to be generated first: `python main.py prep run --job-id <id>`

```bash
python main.py prep mock --job-id 12
```

---

## Daily Workflow

```bash
# Morning: pull fresh listings
python main.py search

# Score the newest jobs first (fewest applicants)
python main.py score --recent --limit 10

# Review results
python main.py jobs
python main.py jobs --search "stripe"
python main.py show --job-id 12

# Generate application materials for a job you want
python main.py tailor --job-id 12
python main.py cover-letter --job-id 12

# Prep for the interview
python main.py prep run --job-id 12
python main.py prep mock --job-id 12

# Track applications
python main.py mark-applied --job-id 12
python main.py jobs --applied

# After updating your resume
python main.py parse-resume --force
python main.py score --force
```

---

## Database

All data is stored locally in `data/jobs.db` — a single SQLite file. No cloud, no account, no cost.

To browse visually, install the **SQLite Viewer** extension in VS Code (`qwtel.sqlite-viewer`) and click the file in the explorer.

| Table | What it stores |
|---|---|
| `jobs` | Scraped listings with fit scores, ATS scores, gap analysis, and status |
| `resume_versions` | Tailored resumes per job with change summaries |
| `interview_prep` | Technical questions (+ LeetCode/Glassdoor data), behavioral, company prep, study plan, mock sessions |
| `applications` | Submitted applications (Phase 6) |
| `contacts` | Hiring managers and recruiters (Phase 5) |
| `outreach_sequences` | Message send/follow-up tracking (Phase 5) |
| `company_research` | Company intel: funding, news, tech stack (Phase 4) |
| `salary_data` | Comp benchmarks (Phase 4) |
| `interview_outcomes` | Interview results and feedback (Phase 7) |

---

## Running Tests

```bash
pytest tests/ -v
```

108 tests — all mocked. No API calls, no network requests, no cost.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Phase 2+ | Claude API key |
| `SERPAPI_KEY` | Phase 4+ | Web search API key |
| `GMAIL_CLIENT_ID` | Phase 5+ | Gmail OAuth client ID |
| `GMAIL_CLIENT_SECRET` | Phase 5+ | Gmail OAuth client secret |
| `LINKEDIN_EMAIL` | Phase 5+ | LinkedIn account email |
| `LINKEDIN_PASSWORD` | Phase 5+ | LinkedIn account password |
| `TARGET_ROLES` | Optional | JSON array of job titles to search for |
| `TARGET_LOCATIONS` | Optional | JSON array of locations (`"Remote"` for remote) |
| `MIN_FIT_SCORE` | Optional | Minimum fit score to generate materials for (default: 6) |
| `TARGET_COMP_MIN` | Optional | Minimum salary to flag underpaying roles (default: 150000) |
