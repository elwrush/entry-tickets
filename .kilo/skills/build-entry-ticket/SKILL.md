---
name: build-entry-ticket
description: Builds entry ticket test slideshows (reveal.js + TTS audio + answer keys) for M2 and M3 levels. Selects words from permanent Oxford B1/B2 word banks, consumes them on use, uses IPA from agent-written phonemic bank, produces TTS dictation audio, and writes per-class answer sheets as Typst PDFs.
---

# Skill: Build Entry Ticket

## Purpose

Generate a complete entry ticket test for M2 (B1) and M3 (B2) levels, delivered as a single reveal.js slideshow with TTS audio for dictation, timed auto-advancing sections, and answer keys. Each level has 7 questions. M2 runs first, then M3, in one deck.

The test structure per level:

| Slide | Content | Items | Timing | Audio |
|---|---|---|---|---|
| 0 | TOC — click M2 or M3 to start | — | Teacher click | — |
| 1 | Title — "M2 Entry Ticket Number X" | — | Teacher click | — |
| 2 | Phonemic transcription — 2 words from Oxford B1/B2 list | 1, 2 | 15s auto-advance | — |
| 3 | Dictation — 1 word spoken by TTS | 3 | Auto-advance after audio | Inworld TTS |
| 4 | Multiple choice vocabulary — 1 word + 3 definitions | 4 | 10s auto-advance | — |
| 5 | True/False — 2 grammar questions | 5, 6 | 15s auto-advance | — |
| 6 | Short answer — 1 grammar question | 7 | 15s auto-advance | — |
| 7 | STOP / DON'T TALK / RETURN YOUR PAPERS | — | Static | — |

**Total slides:** 15 (1 TOC + M2 × 7 + M3 × 7)

M2 runs slides 0–7, then M3 runs slides 8–14 (same pattern repeated).

## When to Use

Use this skill when you need to build entry ticket tests for M2 (B1) and/or M3 (B2) classes. The skill handles the complete pipeline: word selection from permanent Oxford B1/B2 banks, IPA lookup from agent-provided phonemic bank, TTS audio, slide assembly, and answer keys. Selected words are consumed from the banks and never repeat.

**Trigger:** `/build-entry-ticket` command or direct request.

**Non-verbose:** The command fires silently — no confirmation message is printed before the first question.

## Design Rules (Hard)

- **Background:** `#000000` (black) on all test slides
- **Text:** White (`#fff`), Arial font (`font-family: Arial, sans-serif`), no text-shadow, no decorations
- **Unadorned:** No logos, no badges, no borders, no icons — pure text on black
- **Answers never shown on screen** — speaker notes only
- **Slide numbering:** Questions numbered 1–7 per level (resets for M3)
- **Academic English conventions:** All question text, example sentences, and wording must observe the conventions of formal academic English — appropriate punctuation, standard grammar, and register-consistent phrasing. This is a governing principle, not an exhaustive rulebook; the agent and authorial voice are expected to exercise judgement to produce naturally correct academic prose without needing every rule enumerated.

## Workflow (7 Steps)

---

### Step 1 — Grammar Focus

**The agent MUST ask the user for the grammar focus before running any build command.** Do not skip this step. Do not use defaults without asking.

Ask the user:

> **M2 (B1):** *"What is the grammar focus for this M2 entry ticket?"*

> **M3 (B2):** *"What is the grammar focus for this M3 entry ticket?"*

Collect enough detail to write unambiguous questions:
- Target structure
- Example of correct vs incorrect usage
- Any specific terminology the students have been taught

**Then pass both answers as CLI flags to the build script:**

```powershell
python scripts/build_test_slides.py --m2-grammar "Compound sentences" --m3-grammar "Sentence fragments and run-ons"
```

The script requires both flags. It will error if either is missing.

---

### Step 2 — Determine Test Number

Scan `ANSWER_KEYS/` directory for existing answer key JSON files. Find the highest existing `{level}-entry-ticket-{N}.json` number across both levels, then set `test_number = N + 1`. If `ANSWER_KEYS/` does not exist or contains no files, test_number = 1.

---

### Step 3 — Word Selection from Permanent Banks

The build script loads B1 and B2 words from permanent config files, not from the Oxford PDF. These files were populated once from the Oxford 3000 CEFR list and **shrink over time** as words are consumed by builds.

**Word banks:**
- B1 → `config/words_b1.json` (array of word strings, from Oxford B1 list)
- B2 → `config/words_b2.json` (array of word strings, from Oxford B2 list)
- Source: `https://github.com/jnoodle/English-Vocabulary-Word-List`

**Selection:**
- Seeded random: `seed = f"{date}{test_number}-m{level}"` for reproducibility
- 4 words per level: index 0-1 for phonemic slides, index 2 for dictation, index 3 for MC

**Consumption:**
- After the build, the 4 selected words are **removed from the bank file**
- They can never be selected again — the bank permanently shrinks

**What the agent must provide:**
Before the build succeeds, every selected word needs:
1. A phonemic transcription in `config/phonemic.json`
2. A simple B1/B2-level definition in `config/definitions.json`

If either is missing, the build prints the exact word and aborts. The agent adds the missing entry directly to the JSON file using raw IPA characters (or JSON `\uXXXX` escapes if the console can't display them), then re-runs.

**Selection criteria (for the initial Oxford extraction):**
- Minimum 5 characters
- Must be real English words
- Prefer words with non-trivial pronunciation

---

### Step 4 — Ensure Phonemic Transcriptions

Phonemic transcriptions are stored in `config/phonemic.json` (a separate lookup file from the word banks). If a selected word lacks a phonemic entry, the build aborts and tells the agent exactly which word to add.

The agent adds the missing entry directly to `config/phonemic.json`:
- Using the `edit` tool with raw IPA characters (works correctly — the edit tool handles UTF-8)
- Or using JSON `\uXXXX` escapes if console encoding prevents direct character input

**Conventions:** Raw IPA string without surrounding slashes, no syllable-separating periods (`.`), primary stress marked with ASCII apostrophe (`'`) not IPA `ˈ`. Displayed on the slide as bare IPA symbols.

**No phonetic libraries or APIs:** `eng_to_ipa` is installed but never used. The Free Dictionary API is never called for phonemic data. All transcriptions come from agent knowledge.

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

#### Slide 0: TOC (table of contents)
```html
<section id="slide-toc" data-background-color="#000000" style="display: flex; justify-content: center; align-items: center;">
  <h2 style="font-family: Arial, sans-serif; font-size: 2.0em; color: #fff; margin-bottom: 0.8em;">Entry Ticket Number 1</h2>
  <p style="font-family: Arial, sans-serif; font-size: 1.3em; margin: 0.4em 0;">
    <a href="#/1" style="color: #ffdd00; text-decoration: none;">M2 Entry Ticket &rarr;</a>
  </p>
  <p style="font-family: Arial, sans-serif; font-size: 1.3em; margin: 0.4em 0;">
    <a href="#/8" style="color: #ffdd00; text-decoration: none;">M3 Entry Ticket &rarr;</a>
  </p>
</section>
```

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

#### Complete deck order (15 slides):
0. `slide-toc`
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

1. Build all 15 `<section>` elements in a string (TOC + M2×7 + M3×7)
2. Load `templates/entry-ticket-slides.html` template
3. Replace `<!-- TEST_TITLE -->` with `"Entry Ticket Number {test_number}"`
4. Replace `<!-- SLIDES WILL BE SPLICED HERE -->` with the sections HTML
5. Write to `slides/entry-ticket-{N}/index.html`
6. Rebuild root TOC at `slides/index.html` via `build_root_toc()`

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
│   ├── index.html                     # Root TOC — lists all available entry ticket versions
│   └── entry-ticket-{N}\
│       ├── index.html                 # Combined M2+M3 deck (15 slides: TOC + M2×7 + M3×7)
│       └── assets\                    # TTS dictation audio MP3s
├── ANSWER_KEYS\
│   ├── M2-entry-ticket-{N}.json
│   └── M3-entry-ticket-{N}.json
├── output\                            # Per-class PDF answer sheets from Typst
│   ├── M2-4A-entry-tickets.pdf
│   ├── M2-5A-entry-tickets.pdf
│   ├── M3-3A-entry-tickets.pdf
│   ├── M3-4A-entry-tickets.pdf
│   └── M3-5A-entry-tickets.pdf
├── scripts\
│   ├── build_test_slides.py          # Main test builder: word selection, slides, TTS, answer keys
│   ├── build_entry_tickets.py        # Supabase → Typst → PDF per-class answer sheets
│   └── test_entry_tickets.py         # Test harness / helpers
├── templates\
│   ├── entry-ticket-slides.html      # Base reveal.js template (15-slide deck)
│   ├── ACT.png                       # Logo for Typst PDF headers
│   └── cambridge.png                 # Logo for Typst PDF headers
├── config\
│   ├── words_b1.json                 # Permanent B1 word bank (array, shrinks as consumed)
│   ├── words_b2.json                 # Permanent B2 word bank (array, shrinks as consumed)
│   ├── phonemic.json                 # Phonemic lookup (word → IPA)
│   ├── definitions.json              # Definition lookup (word → {def, pos})
│   ├── grammar_bank.json             # Grammar questions (T/F + short answer per topic)
│   └── tts_vocab_voice.json          # Inworld TTS voice ID
├── .word_cache\                      # Cached Oxford 3000 word lists (for resetting banks)
└── .kilo\
    ├── command\
    │   ├── build-entry-ticket.md
    │   └── git-backup.md
    └── skills\
        ├── build-entry-ticket\
        │   └── SKILL.md
        └── git-backup\
            └── SKILL.md
```

---

## Edge Cases

| Scenario | Handling |
|---|---|---|
| Word lacks phonemic transcription | Build aborts with the word name; agent adds it to `config/phonemic.json` via `edit` tool |
| Word lacks definition | Build aborts with the word name; agent adds it to `config/definitions.json` via `edit` tool |
| Inworld API key not set | Skip audio generation, show dictation without audio, warn user |
| Test number folder conflict | Overwrite existing files (each build is deterministic for the same test number) |
| Word bank runs dry | Re-populate from `.word_cache/` cache or re-download Oxford PDF; then add phonemic/definitions for needed words |

---

## Verification

After building, verify:
1. Open `slides/index.html` in a browser — confirm all 14 slides render on black backgrounds
2. Check auto-advance timers: phonemic (15s), MC (10s), TF (15s), short answer (15s)
3. Confirm dictation audio plays and slide advances after audio finishes
4. Confirm answer keys match every question on screen
5. Confirm no answers are visible on any slide (check speaker notes only)
6. Confirm all text is Arial, white on black, no shadows or decorations
