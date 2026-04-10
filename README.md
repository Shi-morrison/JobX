# JobX

An AI-powered CLI suite that automates the software engineering job application process — from scraping listings to scoring fit, tailoring resumes, generating cover letters, prepping for interviews, and tracking outreach.

Built with Python, Claude AI, SQLite, and Playwright.

---

## What It Does

| Phase | Feature | Status |
|---|---|---|
| 1 | Job scraping (LinkedIn + Indeed) | ✅ Live |
| 2 | Resume parsing + fit scoring + ATS check + gap analysis | ✅ Live |
| 2.5 | Job lifecycle: search, filter, mark-applied, applied pipeline | ✅ Live |
| 3 | Resume tailoring + cover letter generation | ✅ Live |
| 3.5 | Interview prep (questions, mock sessions, study plan) | ✅ Live |
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

**1. Clone the repo and create a virtual environment:**
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
- `TARGET_ROLES` — comma-separated job titles to search for
- `TARGET_LOCATIONS` — comma-separated locations (use `Remote` for remote)
- `MIN_FIT_SCORE` — minimum score (1–10) to generate materials for a job
- `TARGET_COMP_MIN` — minimum salary to flag underpaying roles

**4. Add your resume:**

Place your resume at `data/base_resume.docx`. This is the master file — JobX will never modify it, only read from it.

**5. Initialize the database:**
```bash
python main.py db init
```

---

## Usage

> Every command supports `--help` to see all available options:
> ```bash
> python main.py --help                  # list all commands
> python main.py search --help           # flags for the search command
> python main.py prep --help             # flags for prep subcommands
> ```

### Scrape jobs
```bash
python main.py search
```
Pulls new listings from LinkedIn and Indeed based on your configured roles and locations. Results are stored in `data/jobs.db` and printed as a table.

**Options:**
```
--hours-back INTEGER   How many hours back to search (default: auto since last run)
--location TEXT        Location to search — use "remote" for remote jobs, or a city
                       like "New York". Case-insensitive. Overrides TARGET_LOCATIONS in .env.
--level TEXT           Seniority filter: intern, junior, mid, senior, staff
--results INTEGER      Max listings per role/location combo (default: 15)
--help                 Show all flags and examples
```

**Examples:**
```bash
python main.py search
python main.py search --location remote --level senior
python main.py search --location "New York" --hours-back 48 --results 20
python main.py search --help
```

---

### List jobs
```bash
python main.py jobs
```
Lists scored jobs ranked by fit score. Applied jobs are hidden by default so the list stays clean. Use `--search` to find a specific job by company or title without needing to remember its ID.

The table includes a `JD` column: `✓` means the job has a description (can be scored and tailored), `✗` means no description was scraped (scoring won't work for that listing).

**Options:**
```
--min-score INTEGER   Only show jobs at or above this fit score
--limit INTEGER       Max jobs to show (default: 25)
--search TEXT         Filter by keyword in job title or company. Case-insensitive.
--recent              Sort by most recently posted first instead of fit score
--unscored            Show only unscored jobs sorted by newest posted (find IDs for score --job-id)
--applied             Show only jobs you have marked as applied (your application pipeline)
--all                 Show every job in the database — scored, unscored, and applied
```

**Examples:**
```bash
python main.py jobs                        # scored jobs ranked by fit score
python main.py jobs --recent               # scored jobs sorted by newest posted
python main.py jobs --search "stripe"      # find jobs at Stripe
python main.py jobs --search "ML"          # find ML-related jobs
python main.py jobs --min-score 7          # only high-fit jobs
python main.py jobs --unscored             # unscored jobs sorted by newest posted
python main.py jobs --applied              # your applied job pipeline
python main.py jobs --all                  # every job in the database
```

---

### Show full job details
```bash
python main.py show --job-id <id>
```
Shows complete details for a single job: fit score, ATS coverage, fit reasoning, hard gaps, soft gaps, and reframe suggestions. Find job IDs with `python main.py jobs` or `python main.py jobs --search "company"`.

---

### Mark a job as applied
```bash
python main.py mark-applied --job-id <id>
```
Marks a job as applied and hides it from the default `jobs` list. Applied jobs are still accessible with `python main.py jobs --applied`.

**Example:**
```bash
python main.py mark-applied --job-id 12
```

---

### Score jobs
```bash
python main.py score
```
Scores all unscored jobs using Claude — returns fit score (1–10), matching skills, missing skills, and reasoning. Results are saved to the DB and printed as a color-coded ranked table (green ≥7, yellow ≥5, red <5).

By default scores all **unscored** jobs only. Already-scored jobs are skipped unless you use `--force`.

**Options:**
```
--job-id INTEGER       Score one specific job by ID (find IDs with: python main.py jobs --unscored)
--limit INTEGER        Max jobs to score in this run (good for testing a small batch first)
--recent               Score most recently posted jobs first — fewest applicants, highest response rate
--min-score INTEGER    Only display jobs at or above this score (all jobs still scored and saved)
--show-reasoning       Print Claude's reasoning under each score
--force                Re-score jobs that have already been scored
--help                 Show all flags
```

**Examples:**
```bash
python main.py score                              # score all unscored jobs
python main.py score --limit 5                   # score next 5 unscored jobs
python main.py score --recent --limit 10         # score 10 most recently posted jobs
python main.py score --recent --force --limit 10 # re-score 10 most recent jobs
python main.py score --job-id 12                 # score one specific job
python main.py score --force --job-id 12         # re-score an already-scored job
python main.py score --min-score 7 --show-reasoning
```

---

### Research a company *(Phase 4 — planned)*
```bash
python main.py research --company "Stripe"
```

---

### Get salary intelligence *(Phase 4 — planned)*
```bash
python main.py salary --company "Stripe" --level senior
```

---

### Tailor your resume
```bash
python main.py tailor --job-id <id>
```
Rewrites your resume bullets to match a specific job's requirements using the gap analysis reframe suggestions from scoring. Saves to `data/resume_versions/resume_<id>.docx`. Your base resume at `data/base_resume.docx` is never modified.

Requires the job to be scored first: `python main.py score --job-id <id>`

**Example:**
```bash
python main.py tailor --job-id 12
```

---

### Generate a cover letter
```bash
python main.py cover-letter --job-id <id>
```
Generates a tailored cover letter using your experience, the job description, and gap analysis. Saves to `data/cover_letters/cover_letter_<id>.docx`. Outputs a subject line and word count.

Requires the job to be scored first: `python main.py score --job-id <id>`

**Example:**
```bash
python main.py cover-letter --job-id 12
```

---

### Interview prep
```bash
python main.py prep run --job-id <id>
```
Generates full interview prep for a job in 5 steps:
1. **LeetCode problems** — fetches real company-tagged problems sorted by frequency (663 companies supported). Falls back to Claude if company not in dataset.
2. **Technical questions** — Claude generates questions per JD technology, grounded in real LeetCode data
3. **Behavioral questions** — STAR-format questions mapped to JD soft skill signals
4. **Company prep** — "why us" talking points and smart questions to ask the interviewer
5. **Study plan** — prioritized topics from gap analysis with specific resources and estimated hours

Requires the job to be scored first: `python main.py score --job-id <id>`

**Options:**
```
--job-id INTEGER   Job ID to prepare for (required)
--force            Regenerate even if prep already exists
```

**Examples:**
```bash
python main.py prep run --job-id 12
python main.py prep run --job-id 12 --force
```

---

### Mock interview
```bash
python main.py prep mock --job-id <id>
```
Runs an interactive mock interview session. Claude acts as the interviewer — questions rotate through technical, behavioral, and company-specific. Type your answer, get scored 1–10 with specific critique and a stronger example answer. Type `skip` to skip a question, `quit` to end the session. Sessions are saved for later review.

Requires prep to be generated first: `python main.py prep run --job-id <id>`

**Example:**
```bash
python main.py prep mock --job-id 12
```

---

### Outreach *(Phase 5 — planned)*
```bash
python main.py outreach --job-id 5
python main.py outreach --due
```

---

### Apply to a job *(Phase 6 — planned)*
```bash
python main.py apply --job-id 5
```

---

### Log an interview outcome *(Phase 7 — planned)*
```bash
python main.py outcome --job-id 5
```

---

### Daily digest *(Phase 7 — planned)*
```bash
python main.py digest
```

---

## Database

All data is stored locally in `data/jobs.db` — a single SQLite file. No cloud, no account, no cost.

To browse the database visually, install the **SQLite Viewer** extension in VS Code (`qwtel.sqlite-viewer`) and click the file in the explorer.

**Tables:**

| Table | What it stores |
|---|---|
| `jobs` | Scraped listings with fit scores and status |
| `applications` | Submitted applications |
| `contacts` | Hiring managers and recruiters |
| `outreach_sequences` | Message send/follow-up/ghost tracking |
| `resume_versions` | Tailored resumes per job |
| `company_research` | Company intel (funding, news, tech stack) |
| `salary_data` | Comp data from Levels.fyi and Glassdoor |
| `interview_prep` | Questions, study plans, mock session logs |
| `interview_outcomes` | Interview results and feedback |

---

## Running Tests

```bash
pytest tests/ -v
```

All tests are mocked — no API calls, no network requests, no cost.

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
| `TARGET_ROLES` | Optional | Comma-separated job titles (default: Software Engineer, Backend Engineer, Full Stack Engineer) |
| `TARGET_LOCATIONS` | Optional | Comma-separated locations (default: Remote, San Francisco, New York) |
| `MIN_FIT_SCORE` | Optional | Minimum fit score to generate materials for (default: 6) |
| `TARGET_COMP_MIN` | Optional | Minimum salary to flag underpaying roles (default: 150000) |
