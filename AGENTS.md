# AGENTS.md — Entry Tickets

## Project structure

```
scripts/
  build_test_slides.py     # Main test builder: word selection, slides, TTS, answer keys
  build_entry_tickets.py   # Supabase → Typst → PDF per-class answer sheets
templates/
  entry-ticket-slides.html # Base reveal.js template (15-slide deck)
  ACT.png, cambridge.png   # Logo images for Typst PDF headers
ANSWER_KEYS/               # Generated answer key JSONs (iteratively labelled)
slides/                    # Generated reveal.js output
  index.html               # Combined M2+M3 deck (15 slides)
  assets/                  # TTS dictation audio MP3s
output/                    # Per-class PDF answer sheets from Typst
.word_cache/               # Cached Oxford 3000 word lists (avoid re-download)
config/tts_vocab_voice.json  # Inworld TTS voice ID
```

## Key commands

```powershell
# Build next test (auto-detects test number from ANSWER_KEYS/)
python scripts/build_test_slides.py

# Rebuild test 1 (delete ANSWER_KEYS first or they auto-increment)
Remove-Item ANSWER_KEYS -Recurse; python scripts/build_test_slides.py

# Build per-class PDF answer sheets (run after slides build)
python scripts/build_entry_tickets.py M3-4A
python scripts/build_entry_tickets.py M2-4A
python scripts/build_entry_tickets.py M3-3A
python scripts/build_entry_tickets.py M3-5A
python scripts/build_entry_tickets.py M2-5A

# Open slides in browser
start slides/index.html
```

## Test structure (per level, 15 slides total)

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

## Styling rules (hard)

- **Background:** `#000000` on all slides
- **Text:** White, Arial, no text-shadow, no decorations, unadorned
- **Yellow** (`#ffdd00 !important`): target sentences in T/F (5,6), target sentence in short answer (7), MC word (4), A/B/C labels on MC options
- All yellow inline styles need `!important` because template CSS uses `.reveal * { color: #fff !important; }`
- Phonemic script: wrap in `/.../`, no syllable-separating periods, stress marks use `'` not `ˈ`
- Example: `/'ɒbviəs/` not `/ˈɒb.vi.əs/`

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
- Extracted by level, cached to `.word_cache/oxford_3000_{level}.json` after first download
- B1 → M2, B2 → M3
- Selection: seeded random (`{date}-{test_number}-m{level}`), filtered to words in `WORD_MEANINGS` + `PHONEMIC` dictionaries

## Answer keys

- Written to `ANSWER_KEYS/{level}-entry-ticket-{N}.json`
- Test number auto-detected: scans existing keys, max N + 1 (or 1 if none)
- Never show answers on screen — speaker notes only

## Required env vars

- `SUPABASE_URL` + `SUPABASE_ESL_KEY` — for Supabase classlists queries (PDF answer sheets)
- `INWORLD_API_KEY` — for TTS dictation audio (skip if missing)

## Word and definition banks

- `WORD_MEANINGS` dict in `build_test_slides.py` — simple B1/B2-level definitions, no dictionary API
- `PHONEMIC` dict — phonemic transcriptions from agent knowledge, no `eng_to_ipa` or API
- Both must be extended when new words are wanted — the word pool is filtered to only words present in both banks

## Dependencies

- Python: `fitz` (PyMuPDF), `requests`, `eng_to_ipa` (not actually used but installed)
- Typst CLI (for PDF answer sheets)
- FFmpeg (for TTS silence concat)
- reveal.js 5.1.0 loaded from CDN (no local install needed)
