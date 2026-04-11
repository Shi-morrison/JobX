"""Greenhouse ATS autofill (Phase 6.1).

Greenhouse application URLs look like:
  https://boards.greenhouse.io/{company}/jobs/{job_id}
  https://job-boards.greenhouse.io/{company}/jobs/{job_id}

Standard form fields:
  - First name, last name, email, phone
  - Resume upload (PDF)
  - Cover letter upload or textarea
  - LinkedIn URL, website
  - Custom questions (text, textarea, select, checkbox)

Resilience strategy:
  - Screenshot on any failure → data/screenshots/
  - All selectors have fallbacks
  - Skips optional fields that aren't found
  - Returns structured result with success flag + what was filled
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

SCREENSHOT_DIR = Path("data/screenshots")

# Standard field selectors — Greenhouse uses consistent IDs/names
_FIELD_SELECTORS = {
    "first_name": ["#first_name", "input[name='first_name']", "input[placeholder*='First']"],
    "last_name":  ["#last_name",  "input[name='last_name']",  "input[placeholder*='Last']"],
    "email":      ["#email",      "input[name='email']",      "input[type='email']"],
    "phone":      ["#phone",      "input[name='phone']",      "input[placeholder*='Phone']"],
    "resume":     ["input[name='resume']", "input[id*='resume'][type='file']"],
    "cover_letter_file": ["input[name='cover_letter']", "input[id*='cover_letter'][type='file']"],
    "cover_letter_text": ["textarea[name='cover_letter']", "textarea[id*='cover_letter']"],
    "linkedin":   ["input[name='linkedin_profile']", "input[id*='linkedin']", "input[placeholder*='LinkedIn']"],
    "website":    ["input[name='website']", "input[id*='website']", "input[placeholder*='website']"],
}


async def _find_and_fill(page: Page, selectors: list[str], value: str) -> bool:
    """Try each selector in order; fill the first found. Returns True on success."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.fill(value)
                return True
        except Exception:
            continue
    return False


async def _upload_file(page: Page, selectors: list[str], file_path: str) -> bool:
    """Try to upload a file to the first matching file input."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.set_input_files(file_path)
                return True
        except Exception:
            continue
    return False


async def _get_custom_questions(page: Page) -> list[dict]:
    """Extract custom questions from the Greenhouse form.

    Returns list of {label, field_id, field_type, options}
    """
    questions = []
    try:
        # Greenhouse wraps custom questions in li.field with a label
        question_blocks = page.locator("li.field")
        count = await question_blocks.count()
        for i in range(count):
            block = question_blocks.nth(i)
            label_el = block.locator("label").first
            label_text = (await label_el.inner_text()).strip() if await label_el.count() > 0 else ""
            if not label_text:
                continue

            # Determine field type
            textarea = block.locator("textarea").first
            select = block.locator("select").first
            checkbox = block.locator("input[type='checkbox']").first
            text_input = block.locator("input[type='text']").first

            field_id = ""
            field_type = "text"
            options = []

            if await textarea.count() > 0:
                field_type = "textarea"
                field_id = await textarea.get_attribute("id") or await textarea.get_attribute("name") or ""
            elif await select.count() > 0:
                field_type = "select"
                field_id = await select.get_attribute("id") or await select.get_attribute("name") or ""
                option_els = block.locator("select option")
                for j in range(await option_els.count()):
                    val = await option_els.nth(j).get_attribute("value") or ""
                    text = (await option_els.nth(j).inner_text()).strip()
                    if val and val != "":
                        options.append({"value": val, "text": text})
            elif await checkbox.count() > 0:
                field_type = "checkbox"
                field_id = await checkbox.get_attribute("id") or ""
            elif await text_input.count() > 0:
                field_id = await text_input.get_attribute("id") or await text_input.get_attribute("name") or ""

            questions.append({
                "label": label_text,
                "field_id": field_id,
                "field_type": field_type,
                "options": options,
            })
    except Exception:
        pass
    return questions


async def _answer_custom_questions(
    page: Page,
    questions: list[dict],
    job_title: str,
    company: str,
    experience_summary: str,
    skills: str,
) -> int:
    """Use Claude to answer custom questions and fill them in. Returns count filled."""
    if not questions:
        return 0

    from tools.llm import ClaudeClient, load_prompt
    client = ClaudeClient()
    filled = 0

    for q in questions:
        # Skip demographic / EEO fields — these are select menus with race/gender options
        label_lower = q["label"].lower()
        if any(kw in label_lower for kw in ["race", "ethnicity", "gender", "veteran", "disability", "pronouns"]):
            continue

        try:
            prompt = load_prompt(
                "custom_question",
                job_title=job_title,
                company=company,
                question=q["label"],
                experience_summary=experience_summary,
                skills=skills,
            )
            result = client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            answer = result.get("answer", "")
            if not answer:
                continue

            if q["field_type"] in ("text", "textarea") and q["field_id"]:
                el = page.locator(f"#{q['field_id']}").first
                if await el.count() > 0:
                    await el.fill(answer)
                    filled += 1
            elif q["field_type"] == "select" and q["options"]:
                # Pick the option whose text best matches the answer
                answer_lower = answer.lower()
                best = q["options"][0]["value"]
                for opt in q["options"]:
                    if opt["text"].lower() in answer_lower or answer_lower in opt["text"].lower():
                        best = opt["value"]
                        break
                el = page.locator(f"#{q['field_id']}").first
                if await el.count() > 0:
                    await el.select_option(value=best)
                    filled += 1

        except Exception:
            continue

    return filled


async def _screenshot(page: Page, name: str) -> str:
    """Take a screenshot and save to data/screenshots/. Returns path."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return str(path)


async def fill_greenhouse(
    url: str,
    applicant: dict,
    resume_path: str,
    cover_letter_path: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Fill a Greenhouse application form.

    Args:
        url: Greenhouse job URL.
        applicant: Dict with first_name, last_name, email, phone, linkedin, website,
                   job_title, company, experience_summary, skills.
        resume_path: Absolute path to resume PDF.
        cover_letter_path: Absolute path to cover letter file (optional).
        dry_run: If True, fill the form but do not click Submit.

    Returns:
        {"success": bool, "filled_fields": [...], "custom_answered": int,
         "screenshot": str, "error": str}
    """
    result = {
        "success": False,
        "filled_fields": [],
        "custom_answered": 0,
        "screenshot": "",
        "error": "",
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            # Standard fields
            fields_to_fill = [
                ("first_name", applicant.get("first_name", "")),
                ("last_name",  applicant.get("last_name", "")),
                ("email",      applicant.get("email", "")),
                ("phone",      applicant.get("phone", "")),
                ("linkedin",   applicant.get("linkedin", "")),
                ("website",    applicant.get("website", "")),
            ]
            for field_key, value in fields_to_fill:
                if value and await _find_and_fill(page, _FIELD_SELECTORS[field_key], value):
                    result["filled_fields"].append(field_key)

            # Resume upload
            if resume_path and Path(resume_path).exists():
                if await _upload_file(page, _FIELD_SELECTORS["resume"], resume_path):
                    result["filled_fields"].append("resume")

            # Cover letter — try file upload first, then textarea
            if cover_letter_path and Path(cover_letter_path).exists():
                if await _upload_file(page, _FIELD_SELECTORS["cover_letter_file"], cover_letter_path):
                    result["filled_fields"].append("cover_letter_file")
            # Also check for text cover letter textarea
            elif applicant.get("cover_letter_text"):
                if await _find_and_fill(page, _FIELD_SELECTORS["cover_letter_text"], applicant["cover_letter_text"]):
                    result["filled_fields"].append("cover_letter_text")

            # Custom questions
            custom_qs = await _get_custom_questions(page)
            if custom_qs:
                result["custom_answered"] = await _answer_custom_questions(
                    page,
                    custom_qs,
                    job_title=applicant.get("job_title", "Software Engineer"),
                    company=applicant.get("company", ""),
                    experience_summary=applicant.get("experience_summary", ""),
                    skills=applicant.get("skills", ""),
                )

            # Screenshot before submit (always, for review)
            result["screenshot"] = await _screenshot(page, f"greenhouse_{applicant.get('company', 'company')}_prefill")

            if not dry_run:
                # Click submit — Greenhouse uses input[type='submit'] or button[type='submit']
                submit = page.locator("input[type='submit'], button[type='submit']").first
                if await submit.count() > 0:
                    await submit.click()
                    await page.wait_for_timeout(3000)
                    result["screenshot"] = await _screenshot(page, f"greenhouse_{applicant.get('company', 'company')}_submitted")
                    result["success"] = True
                else:
                    result["error"] = "Submit button not found"
            else:
                result["success"] = True  # dry_run counts as success if we got this far

        except PWTimeout as e:
            result["error"] = f"Timeout: {e}"
            result["screenshot"] = await _screenshot(page, "greenhouse_timeout")
        except Exception as e:
            result["error"] = str(e)
            try:
                result["screenshot"] = await _screenshot(page, "greenhouse_error")
            except Exception:
                pass
        finally:
            await browser.close()

    return result


def fill_greenhouse_sync(
    url: str,
    applicant: dict,
    resume_path: str,
    cover_letter_path: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Synchronous wrapper for fill_greenhouse."""
    return asyncio.run(fill_greenhouse(url, applicant, resume_path, cover_letter_path, dry_run))
