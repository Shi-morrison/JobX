# JobX

An AI-powered CLI suite that automates the software engineering job application process — from scraping listings to scoring fit, tailoring resumes, generating cover letters, prepping for interviews, and tracking outreach.

Built with Python, Claude AI, SQLite, and Playwright.

---

## What It Does

| Phase | Feature | Status |
|---|---|---|
| 1 | Job scraping (LinkedIn + Indeed) | ✅ Live |
| 2 | Resume parsing + fit scoring + ATS check + gap analysis | 🔨 In progress |
| 3 | Resume tailoring + cover letter generation | Planned |
| 3.5 | Interview prep (questions, mock sessions, study plan) | Planned |
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
--location TEXT        Override location for this run (e.g. "Remote", "New York")
--level TEXT           Seniority filter: intern, junior, mid, senior, staff
--job-type TEXT        Work arrangement: remote, hybrid, onsite
--results INTEGER      Max listings per role/location combo (default: 15)
```

**Examples:**
```bash
python main.py search
python main.py search --location Remote --level senior
python main.py search --hours-back 48 --job-type remote --results 20
python main.py search --help           # see all flags
```

---

### Score jobs *(Phase 2 — coming soon)*
```bash
python main.py score
```
Scores all unscored jobs using Claude — returns fit score (1–10), matching skills, missing skills, ATS keyword coverage, and gap analysis.

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

### Interview prep *(Phase 3.5 — planned)*
```bash
python main.py prep run --job-id 5
python main.py prep mock --job-id 5
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
