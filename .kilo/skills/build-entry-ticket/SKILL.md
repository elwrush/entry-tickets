---
name: build-entry-ticket
description: Builds entry ticket test slideshows (reveal.js + TTS audio + answer keys) for M2 and M3 levels. Fetches Oxford word lists from jnoodle GitHub, generates IPA transcriptions, produces TTS dictation audio, and writes per-class answer sheets as Typst PDFs.
---

# Skill: Build Entry Ticket

## Purpose

Generate a complete entry ticket test for M2 (B1) and M3 (B2) levels, delivered as a single reveal.js slideshow with TTS audio for dictation, timed auto-advancing sections, and answer keys. Each level has 7 questions. M2 runs first, then M3, in one deck.

The test structure per level:

| Slide | Content | Items | Timing | Audio |
|---|---|---|---|---|
| 1 | Title — "M2 Entry Ticket Number X" | — | Teacher click | — |
| 2 | Phonemic transcription — 2 words from Oxford B1/B2 list | 1, 2 | 15s auto-advance | — |
| 3 | Dictation — 1 word spoken by TTS | 3 | Auto-advance after audio | Inworld TTS |
| 4 | Multiple choice vocabulary — 1 word + 3 definitions | 4 | 10s auto-advance | — |
| 5 | True/False — 2 grammar questions | 5, 6 | 15s auto-advance | — |
| 6 | Short answer — 1 grammar question | 7 | 15s auto-advance | — |
| 7 | STOP / DON'T TALK / RETURN YOUR PAPERS | — | Static | — |

**Total slides:** 14 (M2 × 7 + M3 × 7)

## When to Use

Use this skill when you need to build entry ticket tests for M2 (B1) and/or M3 (B2) classes. The skill handles the complete pipeline: word extraction from Oxford PDFs, IPA generation, TTS audio, slide assembly, and answer keys.

**Trigger:** `/build-entry-ticket` command or direct request.

**Non-verbose:** The command fires silently — no confirmation message is printed before the first question.

## Design Rules (Hard)

- **Background:** `#000000` (black) on all test slides
- **Text:** White (`#fff`), Arial font (`font-family: Arial, sans-serif`), no text-shadow, no decorations
- **Unadorned:** No logos, no badges, no borders, no icons — pure text on black
- **Answers never shown on screen** — speaker notes only
- **Slide numbering:** Questions numbered 1–7 per level (resets for M3)

## Workflow (7 Steps)

---

### Step 1 — Grammar Focus

Ask the user for the grammar focus for each level (used for true/false items 5–6 and short-answer item 7):

> **M2 (B1):** *"What is the grammar focus for this M2 entry ticket?"*

> **M3 (B2):** *"What is the grammar focus for this M3 entry ticket?"*

Collect enough detail to write unambiguous questions:
- Target structure
- Example of correct vs incorrect usage
- Any specific terminology the students have been taught

---

### Step 2 — Determine Test Number

Scan `ANSWER_KEYS/` directory for existing answer key JSON files. Find the highest existing `{level}-entry-ticket-{N}.json` number across both levels, then set `test_number = N + 1`. If `ANSWER_KEYS/` does not exist or contains no files, test_number = 1.

---

### Step 3 — Fetch Oxford Word Lists

Download the Oxford 3000 by CEFR level PDF from the jnoodle GitHub repo and extract B1 and B2 word lists.

**Source:** `https://github.com/jnoodle/English-Vocabulary-Word-List`
**PDF:** `Oxford 3000_by CEFR level.pdf` (12 pages: A1 pages 1–3, A2 pages 4–6, B1 pages 7–9, B2 pages 10–12)

**Extract words with Python:**

```python
import urllib.request, fitz

def extract_words_by_level(pdf_url: str, level_header: str) -> list[str]:
    """Extract words for a given CEFR level from the Oxford 3000 PDF."""
    resp = urllib.request.urlopen(pdf_url)
    doc = fitz.open(stream=resp.read(), filetype="pdf")

    # Find start and end pages for the level
    pages = []
    in_level = False
    for i in range(doc.page_count):
        text = doc[i].get_text()
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line == level_header:
                in_level = True
                continue  # skip the header itself
            # Next level header ends the current level
            if in_level and line in ("A1", "A2", "B1", "B2", "C1", "C2") and line != level_header:
                in_level = False
                break
        if in_level:
            pages.append(i)

    doc.close()
    return words
```

Actually extract by collecting all lines between level headers across the relevant pages.

**Word pools needed:**
- M2 (B1): 4 words from B1 list (2 phonemic + 1 dictation + 1 MC)
- M3 (B2): 4 words from B2 list (2 phonemic + 1 dictation + 1 MC)

**Selection criteria:**
- Minimum 5 characters (exclude words like "a", "an", "and", "but", "the")
- Must be real English words (no abbreviations)
- Prefer words with non-trivial pronunciation (avoid "cat", "dog")
- For MC: must have a clear definition that can be contrasted with plausible distractors

**Random selection:**
Use `random.Random(seed)` where `seed = f"{date}{test_number}-m{level}"` for reproducible selection.
Pick 2 phonemic words, 1 dictation word, 1 MC word (all different, 4 total per level).

---

### Step 4 — Generate Phonemic Transcriptions

For each phonemic word, get its IPA transcription.

**Primary:** Install `eng_to_ipa` (`pip install eng_to_ipa`), use `ipa.convert(word, keep_punctuation=False)`.

**Fallback:** Free Dictionary API `https://api.dictionaryapi.dev/api/v2/entries/en/{word}` — extract `phonetics[0].text`.

**Format:** Raw IPA string without surrounding slashes. Displayed on slide as the IPA symbols only.

---

### Step 5 — Generate TTS Dictation Audio

Generate a single dictation audio clip per level for item 3.

**Audio script:** `"Three. {word}. [5 second silence] {word}."`

Use Inworld TTS-2 (same voice as LPW3 project) for the speech segments. Insert 5 seconds of silence between readings using FFmpeg concat.

**Voice config path:** `C:\PROJECTS\ENTRY TICKETS\config\tts_vocab_voice.json`

If the config file does not exist, copy from `C:\PROJECTS\LESSON-PLAN-WRITER-3\config\tts_vocab_voice.json`.

**Inworld API key:** `INWORLD_API_KEY` env var.

**Audio file naming:** `assets/m2_dictation_{level}_{word}.mp3` (e.g., `assets/m2_dictation_possess.mp3`)

---

### Step 6 — Build reveal.js Slideshow

Build a single `index.html` file. Start from `templates/entry-ticket-slides.html`. Splice the 14 `<section>` elements into the `<div class="slides">` container.

**Slide patterns (per level):**

All sections use `data-background-color="#000000"`.

#### Slide 1: Title
```html
<section id="slide-m2-title" data-background-color="#000000" style="display: flex; justify-content: center; align-items: center;">
  <h2 style="font-family: Arial, sans-serif; font-size: 2.4em; color: #fff;">M2 Entry Ticket Number 1</h2>
  <aside class="notes">Teacher: click to proceed when all students are ready.</aside>
</section>
```

#### Slide 2: Phonemic (items 1, 2 — 15s auto-advance)
```html
<section id="slide-m2-phonemic" data-background-color="#000000" data-timer="15">
  <p style="font-family: Arial, sans-serif; font-size: 1.1em; font-style: italic; color: #ccc;">Write the English words</p>
  <ol style="font-family: Arial, sans-serif; color: #fff; font-size: 1.6em;">
    <li>ˈprɒsəpæɡˈnəʊziə</li>
    <li>ɪkˈstrɔːrdɪneri</li>
  </ol>
  <aside class="notes">15 seconds. Answers: 1=prosopagnosia, 2=extraordinary</aside>
</section>
```

#### Slide 3: Dictation (item 3 — auto-advance after audio)
```html
<section id="slide-m2-dictation" data-background-color="#000000">
  <p style="font-family: Arial, sans-serif; font-size: 1.1em; font-style: italic; color: #ccc;">Write what you hear</p>
  <ol start="3" style="font-family: Arial, sans-serif; color: #fff; font-size: 1.4em;">
    <li>
      <audio data-autoplay preload="auto" style="position: absolute; width: 0; height: 0; overflow: hidden;" src="assets/m2_dictation_possess.mp3"></audio>
      <span style="color: #888; font-style: italic;">_____</span>
    </li>
  </ol>
  <aside class="notes">Audio plays: "Three. possess. [5s] possess." Answer: possess</aside>
</section>
```

#### Slide 4: Multiple Choice (item 4 — 10s auto-advance)
```html
<section id="slide-m2-mc" data-background-color="#000000" data-timer="10">
  <p style="font-family: Arial, sans-serif; font-size: 1.1em; font-style: italic; color: #ccc;">Write the letter of the correct definition</p>
  <p style="font-family: Arial, sans-serif; font-size: 1.4em; font-weight: bold; color: #fff;">possess</p>
  <ol style="font-family: Arial, sans-serif; color: #fff; font-size: 1.0em; list-style-type: none; padding-left: 0;">
    <li style="margin-bottom: 0.4em;">A. to have or own something</li>
    <li style="margin-bottom: 0.4em;">B. to ask for something</li>
    <li style="margin-bottom: 0em;">C. to look at something</li>
  </ol>
  <aside class="notes">10 seconds. Answer: A</aside>
</section>
```

**Deterministic randomisation of correct answer position:**
```python
import random
seed = f"{test_number}-m{level}-mc-4"
options = [correct_def, distractor1, distractor2]
random.Random(seed).shuffle(options)
correct_letter = chr(65 + options.index(correct_def))  # A, B, or C
```

#### Slide 5: True/False (items 5, 6 — 15s auto-advance)
```html
<section id="slide-m2-tf" data-background-color="#000000" data-timer="15">
  <p style="font-family: Arial, sans-serif; font-size: 1.1em; font-style: italic; color: #ccc;">True or False? Write T or F.</p>
  <ol start="5" style="font-family: Arial, sans-serif; color: #fff; font-size: 1.1em;">
    <li style="margin-bottom: 0.8em;">The following sentence is compound: "My friend and I went to Paris last year."</li>
    <li style="margin-bottom: 0em;">This sentence is punctuated correctly: "My sister likes chocolate but I prefer icecream."</li>
  </ol>
  <aside class="notes">15 seconds. 5=False (simple sentence), 6=False (needs comma before 'but')</aside>
</section>
```

#### Slide 6: Short Answer (item 7 — 15s auto-advance)
```html
<section id="slide-m2-short" data-background-color="#000000" data-timer="15">
  <p style="font-family: Arial, sans-serif; font-size: 1.1em; font-style: italic; color: #ccc;">Read the question. Write your answer (max 3 words or a number).</p>
  <p style="font-family: Arial, sans-serif; color: #fff; font-size: 1.2em;">7. How many clauses does this sentence have? "My friend is a wise and courageous person."</p>
  <aside class="notes">15 seconds. Answer: 1 (simple sentence with compound subject complement)</aside>
</section>
```

#### Slide 7: End
```html
<section id="slide-m2-end" data-background-color="#000000" style="display: flex; justify-content: center; align-items: center;">
  <h2 style="font-family: Arial, sans-serif; font-size: 2.8em; color: #fff; margin-bottom: 0.3em;">STOP</h2>
  <p style="font-family: Arial, sans-serif; font-size: 1.4em; color: #fff; margin: 0.2em 0;">DON'T TALK</p>
  <p style="font-family: Arial, sans-serif; font-size: 1.4em; color: #fff; margin: 0.2em 0;">RETURN YOUR PAPERS</p>
</section>
```

#### Complete deck order (14 slides):
1. `slide-m2-title`
2. `slide-m2-phonemic`
3. `slide-m2-dictation`
4. `slide-m2-mc`
5. `slide-m2-tf`
6. `slide-m2-short`
7. `slide-m2-end`
8. `slide-m3-title`
9. `slide-m3-phonemic`
10. `slide-m3-dictation`
11. `slide-m3-mc`
12. `slide-m3-tf`
13. `slide-m3-short`
14. `slide-m3-end`

#### Splice approach

1. Build all 14 `<section>` elements in a string
2. Copy `templates/entry-ticket-slides.html` to `slides/index.html`
3. Replace `<!-- TEST_TITLE -->` with `"Entry Ticket Number {test_number}"`
4. Find the `<!-- SLIDES WILL BE SPLICED HERE -->` comment and insert the sections
5. Update any necessary paths

---

### Step 7 — Generate Answer Keys

Write answer keys as JSON files in `ANSWER_KEYS/`.

**File naming:** `ANSWER_KEYS/{level}-entry-ticket-{N}.json`

**Structure:**
```json
{
  "test": "M2 Entry Ticket Number 1",
  "date": "070626",
  "grammar_focus": "Compound sentences",
  "sections": {
    "phonemic": {
      "instruction": "Write the English words",
      "items": [
        {"number": 1, "word": "prosopagnosia", "phonemic": "ˈprɒsəpæɡˈnəʊziə"},
        {"number": 2, "word": "extraordinary", "phonemic": "ɪkˈstrɔːrdɪneri"}
      ]
    },
    "dictation": {
      "instruction": "Write what you hear",
      "items": [
        {"number": 3, "word": "possess"}
      ]
    },
    "multiple_choice": {
      "instruction": "Write the letter of the correct definition",
      "items": [
        {
          "number": 4,
          "word": "possess",
          "options": {"A": "to have or own something", "B": "to ask for something", "C": "to look at something"},
          "correct": "A",
          "definition": "to have or own something"
        }
      ]
    },
    "true_false": {
      "instruction": "True or False? Write T or F.",
      "items": [
        {"number": 5, "statement": "...", "answer": "F", "explanation": "..."},
        {"number": 6, "statement": "...", "answer": "F", "explanation": "..."}
      ]
    },
    "short_answer": {
      "instruction": "Read the question. Write your answer (max 3 words or a number).",
      "number": 7,
      "question": "...",
      "answer": "1",
      "acceptable_answers": ["1", "one", "1 clause"]
    }
  }
}
```

---

## Files and Directory Structure

Final project tree after build:

```
C:\PROJECTS\ENTRY TICKETS\
├── slides\
│   ├── index.html                     # Combined M2 + M3 reveal.js deck (14 slides)
│   └── assets\
│       ├── m2_dictation_{word}.mp3
│       └── m3_dictation_{word}.mp3
├── ANSWER_KEYS\
│   ├── M2-entry-ticket-{N}.json
│   └── M3-entry-ticket-{N}.json
├── output\                            # Per-class PDF answer sheets
│   ├── M2-4A-entry-tickets.pdf
│   ├── M2-5A-entry-tickets.pdf
│   ├── M3-3A-entry-tickets.pdf
│   ├── M3-4A-entry-tickets.pdf
│   └── M3-5A-entry-tickets.pdf
├── scripts\
│   └── build_entry_tickets.py        # Supabase → Typst → PDF pipeline
├── templates\
│   ├── ACT.png
│   ├── cambridge.png
│   └── entry-ticket-slides.html      # Base reveal.js template
└── .kilo\
    ├── command\
    │   └── build-entry-ticket.md
    └── skills\
        └── build-entry-ticket\
            └── SKILL.md
```

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Oxford PDF download fails | Use local cached copy; if none, warn user and use hardcoded fallback list |
| IPA generation fails for a word | Try dictionary API; if that also fails, replace the word and retry |
| Inworld API key not set | Skip audio generation, show dictation without audio, warn user |
| Test number folder conflict | Warn user; overwrite with confirmation |
| Word list runs out of eligible words | Relax selection criteria (allow 4+ chars, simpler words) |
| No B1/B2 words available | Fall back to Oxford 3000 flat list; warn user about level mismatch |

---

## Verification

After building, verify:
1. Open `slides/index.html` in a browser — confirm all 14 slides render on black backgrounds
2. Check auto-advance timers: phonemic (15s), MC (10s), TF (15s), short answer (15s)
3. Confirm dictation audio plays and slide advances after audio finishes
4. Confirm answer keys match every question on screen
5. Confirm no answers are visible on any slide (check speaker notes only)
6. Confirm all text is Arial, white on black, no shadows or decorations
