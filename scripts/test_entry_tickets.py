"""Post-build validation tests for entry tickets.
Run after each build: python scripts/test_entry_tickets.py
Exit code 0 = all pass, non-zero = one or more failures.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ANSWER_KEYS_DIR = PROJECT_ROOT / "ANSWER_KEYS"
SLIDES_DIR = PROJECT_ROOT / "slides"

errors = []


def fail(msg: str):
    errors.append(msg)
    print(f"  FAIL: {msg}")


def check(condition: bool, msg: str):
    if not condition:
        fail(msg)


def slugify(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


# ---------------------------------------------------------------------------
# 1. Collect all answer keys and their word lists
# ---------------------------------------------------------------------------
def collect_keys() -> list:
    keys = sorted(ANSWER_KEYS_DIR.glob("*.json"))
    if not keys:
        fail("No answer keys found")
        return []
    data = []
    for p in keys:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            data.append(d)
        except Exception as e:
            fail(f"Cannot read {p.name}: {e}")
    return data


def get_words(d: dict) -> set:
    words = set()
    for sec_key, sec_val in d.get("sections", {}).items():
        items = sec_val.get("items", [])
        if isinstance(items, dict):
            items = [items]
        for item in items:
            w = item.get("word", "")
            if w:
                words.add(w.lower())
    return words


# ---------------------------------------------------------------------------
# 2. No word overlap between tickets
# ---------------------------------------------------------------------------
def test_no_word_overlap(keys: list):
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            overlap = get_words(keys[i]) & get_words(keys[j])
            if overlap:
                fail(
                    f"Word overlap between {keys[i]['test']} and {keys[j]['test']}: {', '.join(sorted(overlap))}"
                )


# ---------------------------------------------------------------------------
# 3. T/F items: distinct numbers 5 and 6, short answer number 7
# ---------------------------------------------------------------------------
def test_item_numbering(keys: list):
    for d in keys:
        test_name = d["test"]
        tf = d["sections"].get("true_false", {}).get("items", [])
        nums = [item["number"] for item in tf]
        check(
            sorted(nums) == [5, 6],
            f"{test_name} T/F numbers are {nums}, expected [5, 6]",
        )

        sa = d["sections"].get("short_answer", {})
        check(
            sa.get("number") == 7,
            f"{test_name} short answer number is {sa.get('number')}, expected 7",
        )


# ---------------------------------------------------------------------------
# 4. Slide content mirrors answer keys
# ---------------------------------------------------------------------------
def test_slides_match_keys(keys: list):
    for d in keys:
        test_name = d["test"]
        m = re.search(r"(M[23]).*?(\d+)", test_name)
        if not m:
            fail(f"Cannot parse level/ticket from '{test_name}'")
            continue
        level, ticket = m.group(1), m.group(2)
        slide_path = SLIDES_DIR / f"entry-ticket-{ticket}" / "index.html"
        if not slide_path.exists():
            fail(f"Slide not found: {slide_path}")
            continue

        html = slide_path.read_text(encoding="utf-8")

        # All words present in HTML
        for word in get_words(d):
            check(word in html, f"{test_name}: word '{word}' missing from slide")

        # T/F answers and short answer in speaker notes only
        tf = d["sections"].get("true_false", {}).get("items", [])
        for item in tf:
            check(
                str(item["answer"]) in html,
                f"{test_name}: T/F answer '{item['answer']}' missing from HTML",
            )

        sa = d["sections"].get("short_answer", {})
        check(
            sa.get("answer", "") in html,
            f"{test_name}: short answer '{sa.get('answer')}' missing from HTML",
        )

        # MC correct letter in speaker notes
        mc = d["sections"].get("multiple_choice", {}).get("items", [])
        if mc:
            check(
                mc[0]["correct"] in html,
                f"{test_name}: MC correct letter '{mc[0]['correct']}' missing",
            )


# ---------------------------------------------------------------------------
# 5. No answers visible on screen (only in <aside class="notes">)
# ---------------------------------------------------------------------------
def test_answers_hidden(keys: list):
    for d in keys:
        test_name = d["test"]
        m = re.search(r"(M[23]).*?(\d+)", test_name)
        if not m:
            continue
        _, ticket = m.group(1), m.group(2)
        slide_path = SLIDES_DIR / f"entry-ticket-{ticket}" / "index.html"
        if not slide_path.exists():
            continue
        html = slide_path.read_text(encoding="utf-8")

        # Strip <aside class="notes">...</aside> and check no answer markers remain
        visible = re.sub(r"<aside class=\"notes\">.*?</aside>", "", html, flags=re.DOTALL)

        tf = d["sections"].get("true_false", {}).get("items", [])
        for item in tf:
            # Check the speaker-note answer marker (e.g. "5=F") is not visible
            check(
                f"{item['number']}={item['answer']}" not in visible,
                f"{test_name}: T/F '{item['number']}={item['answer']}' visible on screen",
            )

        sa = d["sections"].get("short_answer", {})
        check(
            f"Answer: {sa.get('answer')}" not in visible,
            f"{test_name}: 'Answer: {sa.get('answer')}' visible on screen",
        )

        mc = d["sections"].get("multiple_choice", {}).get("items", [])
        if mc:
            check(
                f"Answer: {mc[0]['correct']}" not in visible,
                f"{test_name}: 'Answer: {mc[0]['correct']}' visible on screen",
            )


# ---------------------------------------------------------------------------
# 6. Phonemic transcriptions exist for all phonemic words
# ---------------------------------------------------------------------------
def test_phonemic_present(keys: list):
    for d in keys:
        test_name = d["test"]
        for item in d["sections"].get("phonemic", {}).get("items", []):
            ph = item.get("phonemic", "")
            check(
                len(ph) > 2,
                f"{test_name}: missing phonemic for '{item['word']}'",
            )


# ---------------------------------------------------------------------------
# 7. Sections present in slide HTML (all 14 sections)
# ---------------------------------------------------------------------------
def test_slide_structure(keys: list):
    ticket_nums = set()
    for d in keys:
        m = re.search(r"(\d+)$", d["test"])
        if m:
            ticket_nums.add(m.group(1))
    for t in sorted(ticket_nums):
        slide_path = SLIDES_DIR / f"entry-ticket-{t}" / "index.html"
        if not slide_path.exists():
            continue
        html = slide_path.read_text(encoding="utf-8")

        expected_ids = [
            "slide-toc",
            "slide-m2-title",
            "slide-m2-phonemic",
            "slide-m2-dictation",
            "slide-m2-mc",
            "slide-m2-tf",
            "slide-m2-short",
            "slide-m2-end",
            "slide-m3-title",
            "slide-m3-phonemic",
            "slide-m3-dictation",
            "slide-m3-mc",
            "slide-m3-tf",
            "slide-m3-short",
            "slide-m3-end",
        ]
        for sid in expected_ids:
            check(
                f'id="{sid}"' in html,
                f"Ticket {t}: missing section '{sid}'",
            )

        # TOC links
        check('href="#/1"' in html, f"Ticket {t}: missing M2 TOC link")
        check('href="#/8"' in html, f"Ticket {t}: missing M3 TOC link")


# ---------------------------------------------------------------------------
# 8. Timers set on timed sections
# ---------------------------------------------------------------------------
def test_timers(keys: list):
    ticket_nums = set()
    for d in keys:
        m = re.search(r"(\d+)$", d["test"])
        if m:
            ticket_nums.add(m.group(1))
    timer_specs = {
        "phonemic": "15",
        "mc": "10",
        "tf": "15",
        "short": "15",
    }
    for t in sorted(ticket_nums):
        slide_path = SLIDES_DIR / f"entry-ticket-{t}" / "index.html"
        if not slide_path.exists():
            continue
        html = slide_path.read_text(encoding="utf-8")
        for level in ("m2", "m3"):
            for section, expected_sec in timer_specs.items():
                check(
                    f'data-timer="{expected_sec}"' in html,
                    f"Ticket {t} {level}-{section}: expected data-timer={expected_sec}",
                )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    keys = collect_keys()
    if not keys:
        sys.exit(1)

    print("Testing No word overlap...")
    test_no_word_overlap(keys)

    print("Testing Item numbering...")
    test_item_numbering(keys)

    print("Testing Slides match answer keys...")
    test_slides_match_keys(keys)

    print("Testing Answers hidden from screen...")
    test_answers_hidden(keys)

    print("Testing Phonemic transcriptions present...")
    test_phonemic_present(keys)

    print("Testing Slide structure...")
    test_slide_structure(keys)

    print("Testing Timers...")
    test_timers(keys)

    if errors:
        print(f"\n{'=' * 50}")
        print(f"FAILURES: {len(errors)}")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"\nAll tests passed ({len(keys)} answer keys, {len(set(re.search(r'(\d+)$', d['test']).group(1) for d in keys))} tickets).")


if __name__ == "__main__":
    main()
