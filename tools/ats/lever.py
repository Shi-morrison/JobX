"""Lever ATS autofill (Phase 6.2).

Lever application URLs look like:
  https://jobs.lever.co/{company}/{job_id}
  https://jobs.lever.co/{company}/{job_id}/apply

Lever's form is simpler than Greenhouse — mostly a single page with:
  - Name, email, phone, current company, LinkedIn, Twitter, GitHub, website
  - Resume upload
  - Cover letter textarea
  - Custom questions (text inputs, textareas, dropdowns)
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

SCREENSHOT_DIR = Path("data/screenshots")

_FIELD_SELECTORS = {
    "name":     ["input[name='name']",     "input[placeholder*='Full name']", "input[placeholder*='Name']"],
    "email":    ["input[name='email']",    "input[type='email']"],
    "phone":    ["input[name='phone']",    "input[placeholder*='Phone']"],
    "org":      ["input[name='org']",      "input[placeholder*='Company']", "input[placeholder*='Current company']"],
    "linkedin": ["input[name='urls[LinkedIn]']", "input[placeholder*='LinkedIn']"],
    "github":   ["input[name='urls[GitHub]']",   "input[placeholder*='GitHub']"],
    "website":  ["input[name='urls[Portfolio]']", "input[name='urls[Other]']", "input[placeholder*='website']"],
    "resume":   ["input[type='file'][name='resume']", "input[type='file'][class*='resume']", "input[type='file']"],
    "cover_letter": ["textarea[name='comments']", "textarea[placeholder*='cover letter']", "textarea[placeholder*='Add a cover letter']"],
}


async def _find_and_fill(page: Page, selectors: list[str], value: str) -> bool:
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
    """Extract Lever custom questions (application-specific fields)."""
    questions = []
    try:
        # Lever wraps custom fields in div.application-question
        blocks = page.locator(".application-question")
        count = await blocks.count()
        for i in range(count):
            block = blocks.nth(i)
            label_el = block.locator("label").first
            label_text = (await label_el.inner_text()).strip() if await label_el.count() > 0 else ""
            if not label_text:
                continue

            textarea = block.locator("textarea").first
            select = block.locator("select").first
            text_input = block.locator("input[type='text']").first

            field_type = "text"
            field_id = ""
            options = []

            if await textarea.count() > 0:
                field_type = "textarea"
                field_id = await textarea.get_attribute("name") or await textarea.get_attribute("id") or ""
            elif await select.count() > 0:
                field_type = "select"
                field_id = await select.get_attribute("name") or await select.get_attribute("id") or ""
                option_els = block.locator("select option")
                for j in range(await option_els.count()):
                    val = await option_els.nth(j).get_attribute("value") or ""
                    text = (await option_els.nth(j).inner_text()).strip()
                    if val:
                        options.append({"value": val, "text": text})
            elif await text_input.count() > 0:
                field_id = await text_input.get_attribute("name") or await text_input.get_attribute("id") or ""

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
    if not questions:
        return 0

    from tools.llm import ClaudeClient, load_prompt
    client = ClaudeClient()
    filled = 0

    for q in questions:
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
            result = ClaudeClient().chat_json(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            answer = result.get("answer", "")
            if not answer:
                continue

            if q["field_type"] in ("text", "textarea") and q["field_id"]:
                sel = f"[name='{q['field_id']}']" if "/" not in q["field_id"] else f"[name=\"{q['field_id']}\"]"
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(answer)
                    filled += 1
            elif q["field_type"] == "select" and q["options"] and q["field_id"]:
                answer_lower = answer.lower()
                best = q["options"][0]["value"]
                for opt in q["options"]:
                    if opt["text"].lower() in answer_lower or answer_lower in opt["text"].lower():
                        best = opt["value"]
                        break
                sel = f"select[name='{q['field_id']}']"
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.select_option(value=best)
                    filled += 1
        except Exception:
            continue

    return filled


async def _screenshot(page: Page, name: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return str(path)


async def fill_lever(
    url: str,
    applicant: dict,
    resume_path: str,
    cover_letter_text: str = "",
    dry_run: bool = True,
) -> dict:
    """Fill a Lever application form.

    Args:
        url: Lever job URL (will auto-append /apply if needed).
        applicant: Dict with name (full), email, phone, org, linkedin, github, website,
                   job_title, company, experience_summary, skills.
        resume_path: Absolute path to resume PDF.
        cover_letter_text: Cover letter body text for the textarea.
        dry_run: If True, fill but do not submit.

    Returns:
        {"success": bool, "filled_fields": [...], "custom_answered": int,
         "screenshot": str, "error": str}
    """
    # Lever apply pages end in /apply
    apply_url = url if url.endswith("/apply") else url.rstrip("/") + "/apply"

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
            await page.goto(apply_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            fields_to_fill = [
                ("name",     applicant.get("name", f"{applicant.get('first_name','')} {applicant.get('last_name','')}".strip())),
                ("email",    applicant.get("email", "")),
                ("phone",    applicant.get("phone", "")),
                ("org",      applicant.get("org", applicant.get("current_company", ""))),
                ("linkedin", applicant.get("linkedin", "")),
                ("github",   applicant.get("github", "")),
                ("website",  applicant.get("website", "")),
            ]
            for field_key, value in fields_to_fill:
                if value and await _find_and_fill(page, _FIELD_SELECTORS[field_key], value):
                    result["filled_fields"].append(field_key)

            # Resume upload
            if resume_path and Path(resume_path).exists():
                if await _upload_file(page, _FIELD_SELECTORS["resume"], resume_path):
                    result["filled_fields"].append("resume")

            # Cover letter textarea
            if cover_letter_text:
                if await _find_and_fill(page, _FIELD_SELECTORS["cover_letter"], cover_letter_text):
                    result["filled_fields"].append("cover_letter")

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

            result["screenshot"] = await _screenshot(page, f"lever_{applicant.get('company', 'company')}_prefill")

            if not dry_run:
                submit = page.locator("button[type='submit'], input[type='submit']").first
                if await submit.count() > 0:
                    await submit.click()
                    await page.wait_for_timeout(3000)
                    result["screenshot"] = await _screenshot(page, f"lever_{applicant.get('company', 'company')}_submitted")
                    result["success"] = True
                else:
                    result["error"] = "Submit button not found"
            else:
                result["success"] = True

        except PWTimeout as e:
            result["error"] = f"Timeout: {e}"
            result["screenshot"] = await _screenshot(page, "lever_timeout")
        except Exception as e:
            result["error"] = str(e)
            try:
                result["screenshot"] = await _screenshot(page, "lever_error")
            except Exception:
                pass
        finally:
            await browser.close()

    return result


def fill_lever_sync(
    url: str,
    applicant: dict,
    resume_path: str,
    cover_letter_text: str = "",
    dry_run: bool = True,
) -> dict:
    """Synchronous wrapper for fill_lever."""
    return asyncio.run(fill_lever(url, applicant, resume_path, cover_letter_text, dry_run))
