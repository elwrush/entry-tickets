# AGENTS.md — Entry Tickets

## Project structure

```
scripts/
  build_test_slides.py     # Main test builder: word selection, slides, TTS, answer keys
  build_entry_tickets.py   # Supabase → Typst → PDF per-class answer sheets
  test_entry_tickets.py    # Test harness / helper utilities
templates/
  entry-ticket-slides.html # Base reveal.js template (15-slide deck)
  ACT.png, cambridge.png   # Logo images for Typst PDF headers
config/
  words_b1.json            # Permanent B1 word bank (array, shrinks as words consumed)
  words_b2.json            # Permanent B2 word bank (array, shrinks as words consumed)
  phonemic.json            # Phonemic transcription lookup (word → IPA)
  definitions.json         # Definition lookup (word → {def, pos})
  grammar_bank.json        # Grammar question bank (T/F + short answer per topic)
  tts_vocab_voice.json     # Inworld TTS voice ID
ANSWER_KEYS/               # Generated answer key JSONs (iteratively labelled)
slides/                    # Generated reveal.js output
  index.html               # Root TOC — lists all available entry ticket versions
  entry-ticket-{N}/        # Per-test subfolder
    index.html             # Combined M2+M3 deck (15 slides: TOC + M2×7 + M3×7)
    assets/                # TTS dictation audio MP3s
output/                    # Per-class PDF answer sheets from Typst
.word_cache/               # Cached Oxford 3000 word lists (for resetting word banks)
.kilo/
  command/
    build-entry-ticket.md  # Command entry point for building entry tickets
    git-backup.md          # Command entry point for git backup
  skills/
    build-entry-ticket/    # Skill logic for building entry tickets
    git-backup/            # Skill logic for git backup
```

## Key commands

```powershell
# Build next test (auto-detects test number from ANSWER_KEYS/)
# --m2-grammar and --m3-grammar are REQUIRED — agent must ask user first
python scripts/build_test_slides.py --m2-grammar "Compound sentences" --m3-grammar "Sentence fragments and run-ons"

# Rebuild test 1 (delete ANSWER_KEYS first or they auto-increment)
Remove-Item ANSWER_KEYS -Recurse; python scripts/build_test_slides.py --m2-grammar "..." --m3-grammar "..."

# Build per-class PDF answer sheets (run after slides build)
python scripts/build_entry_tickets.py M3-4A
python scripts/build_entry_tickets.py M2-4A
python scripts/build_entry_tickets.py M3-3A
python scripts/build_entry_tickets.py M3-5A
python scripts/build_entry_tickets.py M2-5A

# Open slides in browser
start slides/index.html
```

## Test structure (per level, 15 slides total, combined M2+M3 deck)

| Slide | Items | Timing |
|---|---|---|
| 0: TOC (click M2 or M3) | — | Teacher click |
| 1: Title | — | Teacher click |
| 2: Phonemic | 1, 2 | 15s auto |
| 3: Dictation (TTS audio) | 3 | Auto after audio ends |
| 4: Multiple choice vocab | 4 | 10s auto |
| 5: True/False grammar | 5, 6 | 15s auto |
| 6: Short answer grammar | 7 | 15s auto |
| 7: End | — | Static |

M2 runs slides 0–7, then M3 runs slides 8–14 (same pattern repeated).

## Styling rules (hard)

- **Background:** `#000000` on all slides
- **Text:** White, Arial, no text-shadow, no decorations, unadorned
- **Yellow** (`#ffdd00 !important`): target sentences in T/F (5,6), target sentence in short answer (7), MC word (4), A/B/C labels on MC options
- All yellow inline styles need `!important` because template CSS uses `.reveal * { color: #fff !important; }`
- Phonemic script: bare IPA (no slashes), no syllable-separating periods, stress marks use `'` not `ˈ`
- Example: `'ɒbviəs` not `/ˈɒb.vi.əs/`

## Navigation

- TOC slide (index 0) links to `#/1` (M2) and `#/8` (M3)
- Title slides and end slides have `← Back to menu` → `#/0`
- Use reveal.js native hash links (`href="#/N"`) — `Reveal.slide(N)` in onclick does not work reliably

## Audio (dictation slide 3)

- Inworld TTS-2 via `INWORLD_API_KEY` env var
- Voice ID from `config/tts_vocab_voice.json` (copy from `C:\PROJECTS\LESSON-PLAN-WRITER-3\config\tts_vocab_voice.json` if missing)
- TTS text: `"Three. {word}."` + 5s silence + `"{word}."` (number must be spelled out, not digit)
- Audio stored in `slides/assets/{level}_dictation_{word}.mp3`
- Audio auto-advance uses `ended` event + 2s buffer (not `duration` calculation)

## Word lists

- Source: `Oxford 3000_by CEFR level.pdf` from `jnoodle/English-Vocabulary-Word-List`
- Extracted by level, stored permanently in `config/words_b1.json` and `config/words_b2.json`
- B1 → M2, B2 → M3
- Selection: seeded random (`{date}-{test_number}-m{level}`), picks 4 words per level from the permanent bank
- Consumption model: selected words are **removed from the bank files** after each build — they can never repeat

## Answer keys

- Written to `ANSWER_KEYS/{level}-entry-ticket-{N}.json`
- Test number auto-detected: scans existing keys, max N + 1 (or 1 if none)
- Never show answers on screen — speaker notes only

## Required env vars

- `SUPABASE_URL` + `SUPABASE_ESL_KEY` — for Supabase classlists queries (PDF answer sheets)
- `INWORLD_API_KEY` — for TTS dictation audio (skip if missing)

## Word and definition banks

- `config/definitions.json` — word → definition + part of speech (B1/B2-level, no dictionary API)
- `config/phonemic.json` — word → phonemic transcription (from agent knowledge, no `eng_to_ipa` or API)
- When a selected word lacks phonemic or definition, the build aborts and tells the agent exactly which entry to add to which JSON file
- The agent edits the JSON files directly (raw IPA characters, or `\uXXXX` escapes for non-console-safe characters)

## Dependencies

- Python: `fitz` (PyMuPDF), `requests`, `eng_to_ipa` (not actually used but installed)
- Typst CLI (for PDF answer sheets)
- FFmpeg (for TTS silence concat)
- reveal.js 5.1.0 loaded from CDN (no local install needed)
