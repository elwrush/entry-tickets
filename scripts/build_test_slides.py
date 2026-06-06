"""build_test_slides.py — Build Entry Ticket Number 1 slideshow + answer keys.

Extracts B1/B2 words from the Oxford 3000 PDF, selects items, generates
IPA, TTS dictation audio, builds the reveal.js slideshow, and writes
answer keys.

Usage:
    python scripts/build_test_slides.py [--test-number N]

Requires env vars: SUPABASE_URL, SUPABASE_ESL_KEY (for PDF answer sheets)
Optional env var: INWORLD_API_KEY (for TTS audio)
"""

import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output"
SLIDES_DIR = PROJECT_ROOT / "slides"
ANSWER_KEYS_DIR = PROJECT_ROOT / "ANSWER_KEYS"
ASSETS_DIR = SLIDES_DIR / "assets"

OXFORD_3000_CEFR_URL = (
    "https://raw.githubusercontent.com/jnoodle/English-Vocabulary-Word-List/"
    "master/Oxford%203000_by%20CEFR%20level.pdf"
)

# Grammar focus from user input
GRAMMAR = {}  # Populated from CLI args


# ---------------------------------------------------------------------------
# Step 1: Extract words from Oxford 3000 CEFR PDF
# ---------------------------------------------------------------------------

WORD_CACHE_DIR = PROJECT_ROOT / ".word_cache"

def extract_words_by_level(pdf_url: str, target_level: str) -> list[str]:
    """Extract words for a given CEFR level, using a local cache if available."""
    cache_path = WORD_CACHE_DIR / f"oxford_3000_{target_level}.json"

    # Load from cache if available
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    # Download and extract
    print(f"  Downloading Oxford 3000 CEFR PDF...")
    WORD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    resp = urllib.request.urlopen(pdf_url)
    doc = fitz.open(stream=resp.read(), filetype="pdf")

    ALL_LEVELS = ["A1", "A2", "B1", "B2"]
    words = []
    current_level = None

    for i in range(doc.page_count):
        text = doc[i].get_text()
        lines = text.split("\n")

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line in ALL_LEVELS:
                current_level = line
                continue
            # Oxford header/footer lines
            if any(x in line for x in ("©", "Oxford University Press", "The Oxford", "Page")):
                continue
            if current_level == target_level:
                # Clean the word — remove POS tags like "v.", "n.", "adj.", etc.
                word = re.sub(r"\s+(v\.|n\.|adj\.|adv\.|prep\.|pron\.|conj\.|det\.|exclam\.|num\.)", "", line).strip()
                word = re.sub(r"/\s*adj\.?$", "", word).strip()
                # Skip empty, short (< 5 chars), or non-alpha words
                if len(word) >= 5 and word.isalpha() and word.islower():
                    words.append(word)

    doc.close()

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique.append(w)

    # Save to cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2)

    return unique


# ---------------------------------------------------------------------------
# Step 2: Select words with seeded random
# ---------------------------------------------------------------------------

def select_words(word_list: list[str], count: int, seed: str, min_len: int = 5) -> list[str]:
    """Select N random words from the list using a seeded RNG."""
    eligible = [w for w in word_list if len(w) >= min_len and w.isalpha()]
    rng = random.Random(seed)
    return rng.sample(eligible, min(count, len(eligible)))


# ---------------------------------------------------------------------------
# Step 3: Phonemic script generation
# Standard ESL phonemic transcriptions (learner-dictionary notation)
# ---------------------------------------------------------------------------

PHONEMIC = {
    # B1 words
    "obvious": "'ɒbviəs",
    "separate": "'sepərət",
    "punish": "'pʌnɪʃ",
    "specifically": "spə'sɪfɪkli",
    "battery": "'bætəri",
    "worst": "wɜːst",
    "admit": "əd'mɪt",
    "advise": "əd'vaɪz",
    "operation": "ˌɒpə'reɪʃən",
    "count": "kaʊnt",
    "respond": "rɪ'spɒnd",
    "positive": "'pɒzətɪv",
    "arrange": "ə'reɪndʒ",
    "connect": "kə'nekt",
    "discover": "dɪ'skʌvə",
    "encourage": "ɪn'kʌrɪdʒ",
    "establish": "ɪ'stæblɪʃ",
    "instruct": "ɪn'strʌkt",
    "measure": "'meʒə",
    "prepare": "prɪ'peə",
    "remind": "rɪ'maɪnd",
    "struggle": "'strʌɡəl",
    "suggest": "sə'dʒest",
    "support": "sə'pɔːt",
    # B2 words
    "rapidly": "'ræpɪdli",
    "ultimately": "'ʌltɪmətli",
    "interrupt": "ˌɪntə'rʌpt",
    "parliament": "'pɑːləmənt",
    "facility": "fə'sɪləti",
    "prospect": "'prɒspekt",
    "actual": "'æktʃuəl",
    "perspective": "pə'spektɪv",
    "controversy": "'kɒntrəvɜːsi",
    "consequence": "'kɒnsɪkwəns",
    "interpret": "ɪn'tɜːprɪt",
    "profound": "prə'faʊnd",
    "sophisticated": "sə'fɪstɪkeɪtɪd",
    "phenomenon": "fɪ'nɒmɪnən",
    "initiative": "ɪ'nɪʃətɪv",
    "inevitable": "ɪ'nevɪtəbəl",
    "explicit": "ɪk'splɪsɪt",
    "compromise": "'kɒmprəmaɪz",
    "ambiguous": "æm'bɪɡjuəs",
    "sufficient": "sə'fɪʃənt",
    "contemporary": "kən'tempərəri",
    "manipulate": "mə'nɪpjʊleɪt",
    "equivalent": "ɪ'kwɪvələnt",
    "implication": "ˌɪmplɪ'keɪʃən",
}


def get_phonemic(word: str) -> str | None:
    """Get standard ESL phonemic transcription from the built-in dictionary."""
    return PHONEMIC.get(word)


# ---------------------------------------------------------------------------
# Step 3b: MC item generation with level-appropriate definitions
# ---------------------------------------------------------------------------

# Word-to-meaning map: simple, level-appropriate definitions (B1/B2 accessible)
# Format: {word: { "def": "simple definition", "pos": "noun|verb|adj|adv" }}
WORD_MEANINGS = {
    # B1 level words
    "punish": {"def": "to make someone suffer because they did something wrong", "pos": "verb"},
    "specifically": {"def": "for one particular thing or purpose", "pos": "adv"},
    "battery": {"def": "a thing that gives power to phones, toys, and other devices", "pos": "noun"},
    "worst": {"def": "more bad than anything else; the opposite of best", "pos": "adj"},
    "admit": {"def": "to agree that something is true, especially when it is bad", "pos": "verb"},
    "advise": {"def": "to tell someone what you think they should do", "pos": "verb"},
    "operation": {"def": "a planned activity that has a particular purpose", "pos": "noun"},
    "count": {"def": "to say numbers in order", "pos": "verb"},
    "respond": {"def": "to answer someone or react to something", "pos": "verb"},
    "obvious": {"def": "easy to see or understand", "pos": "adj"},
    "positive": {"def": "feeling good and happy about something", "pos": "adj"},
    "arrange": {"def": "to put things in a particular order or position", "pos": "verb"},
    "connect": {"def": "to join two or more things together", "pos": "verb"},
    "discover": {"def": "to find something for the first time", "pos": "verb"},
    "encourage": {"def": "to give someone hope or confidence", "pos": "verb"},
    "establish": {"def": "to start or create something that will last", "pos": "verb"},
    "instruct": {"def": "to teach someone how to do something", "pos": "verb"},
    "measure": {"def": "to find the size, amount, or level of something", "pos": "verb"},
    "prepare": {"def": "to make something ready for use", "pos": "verb"},
    "remind": {"def": "to help someone remember something", "pos": "verb"},
    "separate": {"def": "to divide things into different parts or groups", "pos": "verb"},
    "struggle": {"def": "to try very hard to do something difficult", "pos": "verb"},
    "suggest": {"def": "to tell someone your idea about what they should do", "pos": "verb"},
    "support": {"def": "to help someone by agreeing with them or giving what they need", "pos": "verb"},
    # B2 level words
    "rapidly": {"def": "very quickly; at a fast speed", "pos": "adv"},
    "ultimately": {"def": "finally, after everything else has been considered", "pos": "adv"},
    "interrupt": {"def": "to stop someone while they are speaking or doing something", "pos": "verb"},
    "parliament": {"def": "a group of people who make the laws in some countries", "pos": "noun"},
    "facility": {"def": "a building or place that is used for a particular activity", "pos": "noun"},
    "prospect": {"def": "the possibility that something good might happen in the future", "pos": "noun"},
    "actual": {"def": "real and true, not imagined or guessed", "pos": "adj"},
    "perspective": {"def": "a particular way of thinking about or looking at something", "pos": "noun"},
    "controversy": {"def": "a strong disagreement about something that many people have different opinions about", "pos": "noun"},
    "consequence": {"def": "something that happens as a result of an action", "pos": "noun"},
    "interpret": {"def": "to explain the meaning of something", "pos": "verb"},
    "profound": {"def": "very great or strong; having a deep effect", "pos": "adj"},
    "sophisticated": {"def": "having a lot of experience and knowledge about the world", "pos": "adj"},
    "phenomenon": {"def": "something that happens or exists that is unusual or interesting", "pos": "noun"},
    "initiative": {"def": "a new plan or project to solve a problem", "pos": "noun"},
    "inevitable": {"def": "certain to happen; impossible to avoid", "pos": "adj"},
    "explicit": {"def": "said or written in a very clear and direct way", "pos": "adj"},
    "compromise": {"def": "an agreement where both sides give up something", "pos": "noun"},
    "ambiguous": {"def": "having more than one possible meaning; not clear", "pos": "adj"},
    "sufficient": {"def": "enough for a particular purpose", "pos": "adj"},
    "contemporary": {"def": "belonging to the present time; modern", "pos": "adj"},
    "manipulate": {"def": "to control someone or something in a clever or dishonest way", "pos": "verb"},
    "equivalent": {"def": "equal in value, amount, or meaning", "pos": "adj"},
    "implication": {"def": "a possible future effect or result of something", "pos": "noun"},
}


def get_definition(word: str) -> str | None:
    """Get a simple, level-appropriate definition from the word bank."""
    if word in WORD_MEANINGS:
        return WORD_MEANINGS[word]["def"]
    return None


def get_part_of_speech(word: str) -> str | None:
    """Get the part of speech for a word."""
    if word in WORD_MEANINGS:
        return WORD_MEANINGS[word]["pos"]
    return None


def generate_distractors(word: str, correct_def: str, pos: str, seed: str) -> list[str]:
    """Generate 2 level-appropriate distractors for an MC item.
    
    Distractors are taken from OTHER words of the SAME part of speech
    in the WORD_MEANINGS bank. Picks definitions with similar length
    to the correct definition so options appear balanced.
    """
    # Find other words with the same part of speech
    candidates = [
        (w, WORD_MEANINGS[w]["def"]) for w, info in WORD_MEANINGS.items()
        if w != word and info["pos"] == pos
    ]
    if len(candidates) < 2:
        return [d for _, d in candidates]

    # Sort by length proximity to the correct definition
    target_len = len(correct_def)
    candidates.sort(key=lambda x: abs(len(x[1]) - target_len))

    # Pick the 2 closest in length
    return [candidates[0][1], candidates[1][1]]


def build_mc_item(word: str, seed: str) -> dict:
    """Build MC item with level-appropriate definition + 2 distractors."""
    correct_def = get_definition(word)
    pos = get_part_of_speech(word)
    if not correct_def or not pos:
        return {"options": {"A": "definition not available", "B": "-", "C": "-"}, "correct": "?"}

    distractors = generate_distractors(word, correct_def, pos, seed)

    options = [correct_def] + distractors
    rng = random.Random(seed + "-shuffle")
    rng.shuffle(options)
    correct_letter = chr(65 + options.index(correct_def))

    return {
        "options": {"A": options[0], "B": options[1], "C": options[2]},
        "correct": correct_letter,
    }


# ---------------------------------------------------------------------------
# Step 4: TTS dictation audio
# ---------------------------------------------------------------------------

def generate_dictation_audio(word: str, number: int, level: str, output_path: Path) -> bool:
    """Generate TTS dictation audio clip using Inworld TTS-2 + FFmpeg silence."""
    api_key = os.environ.get("INWORLD_API_KEY")
    if not api_key:
        print("  WARNING: INWORLD_API_KEY not set. Skipping audio generation.")
        return False

    # Load voice ID
    voice_config = PROJECT_ROOT / "config" / "tts_vocab_voice.json"
    if not voice_config.exists():
        # Try to copy from LPW3
        lpw3_config = Path(r"C:\PROJECTS\LESSON-PLAN-WRITER-3\config\tts_vocab_voice.json")
        if lpw3_config.exists():
            (PROJECT_ROOT / "config").mkdir(exist_ok=True)
            shutil.copy2(lpw3_config, voice_config)
        else:
            print("  WARNING: No TTS voice config found. Skipping audio.")
            return False

    with open(voice_config) as f:
        voice_id = json.load(f)["voice_id"]

    auth_header = f"Basic {api_key}"
    TEMP_DIR = PROJECT_ROOT / "tmp"
    TEMP_DIR.mkdir(exist_ok=True)

    try:
        # Generate clip 1: "Three. word."
        number_word = ["One", "Two", "Three", "Four", "Five", "Six", "Seven"][number - 1] if 1 <= number <= 7 else str(number)
        clip1_text = f"{number_word}. {word}."
        r1 = requests.post(
            "https://api.inworld.ai/tts/v1/voice",
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json={
                "text": clip1_text,
                "voice_id": voice_id,
                "model_id": "inworld-tts-2",
                "audio_config": {"audio_encoding": "MP3", "sample_rate_hertz": 24000},
            },
        )
        r1.raise_for_status()
        clip1_bytes = base64_decode(r1.json()["audioContent"])

        # Generate clip 2: "word."
        r2 = requests.post(
            "https://api.inworld.ai/tts/v1/voice",
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json={
                "text": f"{word}.",
                "voice_id": voice_id,
                "model_id": "inworld-tts-2",
                "audio_config": {"audio_encoding": "MP3", "sample_rate_hertz": 24000},
            },
        )
        r2.raise_for_status()
        clip2_bytes = base64_decode(r2.json()["audioContent"])

        # Write temp files
        tmp1 = TEMP_DIR / f"dict_{level}_{word}_1.mp3"
        tmp2 = TEMP_DIR / f"dict_{level}_{word}_2.mp3"
        tmp1.write_bytes(clip1_bytes)
        tmp2.write_bytes(clip2_bytes)

        # Generate 5 seconds of silence
        silence = TEMP_DIR / f"dict_{level}_{word}_silence.mp3"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-t", "5",
            "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
            "-acodec", "libmp3lame", "-b:a", "32k",
            str(silence),
        ], capture_output=True, check=True)

        # Concatenate
        list_path = TEMP_DIR / f"dict_{level}_{word}_concat.txt"
        list_path.write_text(
            f"file '{tmp1}'\nfile '{silence}'\nfile '{tmp2}'\n", encoding="utf-8"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(output_path),
        ], capture_output=True, check=True)

        # Cleanup
        for f in [tmp1, tmp2, silence, list_path]:
            try: f.unlink()
            except: pass

        print(f"  Generated dictation audio: {output_path.name}")
        return True

    except Exception as e:
        print(f"  WARNING: TTS audio generation failed: {e}")
        return False


def base64_decode(content):
    import base64
    return base64.b64decode(content)


# ---------------------------------------------------------------------------
# Step 5: Build slides HTML
# ---------------------------------------------------------------------------

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_title_slide(level: str, test_number: int) -> str:
    return f"""<section id="slide-{level.lower()}-title" data-background-color="#000000" style="display: flex; justify-content: center; align-items: center;">
  <h2 style="font-family: Arial, sans-serif; font-size: 2.4em; color: #fff;">{level} Entry Ticket Number {test_number}</h2>
  <p style="font-family: Arial, sans-serif; font-size: 0.9em; margin-top: 2em;">
    <a href="#/0" style="color: #888; text-decoration: none;">&larr; Back to menu</a>
  </p>
  <aside class="notes">Teacher: click to proceed when all students are ready.</aside>
</section>"""


def build_phonemic_slide(level: str, items: list, test_number: int) -> str:
    rows = ""
    for item in items:
        ph = item["phonemic"]
        rows += f'    <li style="margin-bottom: 0.4em;">/{escape_html(ph)}/</li>\n'
    speaker_notes = "; ".join(f'{i["number"]}={i["word"]}' for i in items)
    return f"""<section id="slide-{level.lower()}-phonemic" data-background-color="#000000" data-timer="15">
  <p class="instruction">Write the English words</p>
  <ol style="font-family: Arial, sans-serif; color: #fff; font-size: 1.6em;">
{rows}  </ol>
  <aside class="notes">15 seconds. {speaker_notes}</aside>
</section>"""


def build_dictation_slide(level: str, item: dict, test_number: int) -> str:
    audio_src = f"assets/{level.lower()}_dictation_{item['word']}.mp3"
    return f"""<section id="slide-{level.lower()}-dictation" data-background-color="#000000">
  <p class="instruction">Write what you hear</p>
  <ol start="3" style="font-family: Arial, sans-serif; color: #fff; font-size: 1.4em;">
    <li>
      <audio data-autoplay preload="auto" style="position: absolute; width: 0; height: 0; overflow: hidden;" src="{audio_src}"></audio>
      <span style="color: #888; font-style: italic;">_____</span>
    </li>
  </ol>
  <aside class="notes">Audio plays: "Three. {item['word']}. [5s] {item['word']}." Answer: {item['word']}</aside>
</section>"""


def build_mc_slide(level: str, item: dict, test_number: int) -> str:
    word = item["word"]
    opts = item["mc"]["options"]
    notes = f"10 seconds. Answer: {item['mc']['correct']} ({opts[item['mc']['correct']]})"
    return f"""<section id="slide-{level.lower()}-mc" data-background-color="#000000" data-timer="10">
  <p class="instruction">Write the letter of the correct definition</p>
  <p style="font-family: Arial, sans-serif; font-size: 1.4em; font-weight: bold; color: #ffdd00 !important;">{escape_html(word)}</p>
  <ol style="font-family: Arial, sans-serif; color: #fff; font-size: 1.0em; list-style-type: none; padding-left: 0;">
    <li style="margin-bottom: 0.4em;"><span style="color: #ffdd00 !important;">A.</span> {escape_html(opts['A'])}</li>
    <li style="margin-bottom: 0.4em;"><span style="color: #ffdd00 !important;">B.</span> {escape_html(opts['B'])}</li>
    <li style="margin-bottom: 0em;"><span style="color: #ffdd00 !important;">C.</span> {escape_html(opts['C'])}</li>
  </ol>
  <aside class="notes">{notes}</aside>
</section>"""


def highlight_example(text: str) -> str:
    """Wrap quoted sentences in yellow spans and offset them on a new line.
    Uses !important to override the template's .reveal span { color: #fff !important }."""
    import re
    escaped = escape_html(text)
    # Replace quoted text with yellow span on a new line
    highlighted = re.sub(
        r'&quot;(.+?)&quot;',
        r'<br><span style="color: #ffdd00 !important; margin-left: 1.2em;">&quot;\1&quot;</span>',
        escaped,
    )
    return highlighted


def build_tf_slide(level: str, items: list, test_number: int) -> str:
    rows = ""
    for item in items:
        stmt = highlight_example(item["statement"])
        rows += f'    <li style="margin-bottom: 0.8em;">{item["number"]}. {stmt}</li>\n'
    speaker_notes = "; ".join(f'{i["number"]}={i["answer"]} ({i["explanation"]})' for i in items)
    return f"""<section id="slide-{level.lower()}-tf" data-background-color="#000000" data-timer="15">
  <p class="instruction">True or False? Write T or F.</p>
  <ol start="5" style="font-family: Arial, sans-serif; color: #fff; font-size: 1.1em; list-style-type: none; padding-left: 0;">
{rows}  </ol>
  <aside class="notes">15 seconds. {speaker_notes}</aside>
</section>"""


def build_short_slide(level: str, item: dict, test_number: int) -> str:
    notes = f"15 seconds. Answer: {item['answer']}"
    question_html = highlight_example(item["question"])
    return f"""<section id="slide-{level.lower()}-short" data-background-color="#000000" data-timer="15">
  <p class="instruction">Read the question. Write your answer (max 3 words or a number).</p>
  <p style="font-family: Arial, sans-serif; color: #fff; font-size: 1.2em;">{item["number"]}. {question_html}</p>
  <aside class="notes">{notes}</aside>
</section>"""


def build_end_slide(level: str) -> str:
    return f"""<section id="slide-{level.lower()}-end" data-background-color="#000000" style="display: flex; justify-content: center; align-items: center;">
  <h2 class="end-title">STOP</h2>
  <p class="end-line">DON'T TALK</p>
  <p class="end-line">RETURN YOUR PAPERS</p>
  <p style="font-family: Arial, sans-serif; font-size: 0.9em; margin-top: 2em;">
    <a href="#/0" style="color: #888; text-decoration: none;">&larr; Back to menu</a>
  </p>
</section>"""


def build_toc_slide(test_number: int) -> str:
    """Build a table-of-contents slide as the first slide (index 0).
    Uses reveal.js native hash navigation (#/N) for reliable slide jumps."""
    return f"""<section id="slide-toc" data-background-color="#000000" style="display: flex; justify-content: center; align-items: center;">
  <h2 style="font-family: Arial, sans-serif; font-size: 2.0em; color: #fff; margin-bottom: 0.8em;">Entry Ticket Number {test_number}</h2>
  <p style="font-family: Arial, sans-serif; font-size: 1.3em; margin: 0.4em 0;">
    <a href="#/1" style="color: #ffdd00; text-decoration: none;">M2 Entry Ticket &rarr;</a>
  </p>
  <p style="font-family: Arial, sans-serif; font-size: 1.3em; margin: 0.4em 0;">
    <a href="#/8" style="color: #ffdd00; text-decoration: none;">M3 Entry Ticket &rarr;</a>
  </p>
  <aside class="notes">Click M2 or M3 to jump to that test. M2 is B1 (Compound sentences), M3 is B2 (Sentence fragments and run-ons).</aside>
</section>"""


def build_all_slides(m2_data: dict, m3_data: dict, test_number: int) -> str:
    sections = [build_toc_slide(test_number)]
    for level, data in [("M2", m2_data), ("M3", m3_data)]:
        sections.append(build_title_slide(level, test_number))
        sections.append(build_phonemic_slide(level, data["phonemic"], test_number))
        sections.append(build_dictation_slide(level, data["dictation"], test_number))
        sections.append(build_mc_slide(level, data["mc"], test_number))
        sections.append(build_tf_slide(level, data["tf"], test_number))
        sections.append(build_short_slide(level, data["short"], test_number))
        sections.append(build_end_slide(level))
    return "\n\n".join(sections)


def splice_into_template(sections_html: str, test_number: int) -> str:
    template_path = TEMPLATES_DIR / "entry-ticket-slides.html"
    template = template_path.read_text(encoding="utf-8")

    # Replace title
    template = template.replace("<!-- TEST_TITLE -->", f"Entry Ticket Number {test_number}")

    # Splice sections
    marker = "<!-- SLIDES WILL BE SPLICED HERE -->"
    if marker in template:
        template = template.replace(marker, sections_html)

    return template


# ---------------------------------------------------------------------------
# Root TOC generation
# ---------------------------------------------------------------------------

def build_root_toc():
    """Generate slides/index.html listing all available entry ticket versions."""
    versions = sorted(
        d.name for d in SLIDES_DIR.iterdir()
        if d.is_dir() and d.name.startswith("entry-ticket-") and (d / "index.html").exists()
    )

    cards = ""
    for v in versions:
        num = v.replace("entry-ticket-", "")
        cards += f"""      <a href="{v}/" class="card">
        <div class="card-title">Entry Ticket {num}</div>
        <div class="card-dir">{v}</div>
      </a>
"""

    landing = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Entry Tickets</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: Arial, sans-serif;
      background: #000;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 60px 20px;
    }}
    h1 {{ font-size: 2.2em; color: #fff; margin-bottom: 40px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 20px;
      max-width: 640px;
      width: 100%;
    }}
    .card {{
      background: #111; border-radius: 8px; padding: 24px;
      text-decoration: none; color: #fff;
      transition: background 0.2s;
    }}
    .card:hover {{ background: #222; }}
    .card-title {{ font-size: 1.15em; font-weight: bold; color: #ffdd00; }}
    .card-dir {{ font-size: 0.85em; color: #888; margin-top: 4px; }}
  </style>
</head>
<body>
  <h1>Entry Tickets</h1>
  <div class="grid">
{cards}  </div>
</body>
</html>"""

    toc_path = SLIDES_DIR / "index.html"
    toc_path.write_text(landing, encoding="utf-8")
    print(f"  Root TOC: {toc_path}")


# ---------------------------------------------------------------------------
# Step 8: Write answer keys
# ---------------------------------------------------------------------------

def write_answer_key(level: str, data: dict, test_number: int):
    key = {
        "test": f"{level} Entry Ticket Number {test_number}",
        "date": __import__("datetime").datetime.now().strftime("%m%d%y"),
        "grammar_focus": GRAMMAR[level]["focus"],
        "sections": {
            "phonemic": {
                "instruction": "Write the English words",
                "items": [
                    {"number": i["number"], "word": i["word"], "phonemic": i["phonemic"]}
                    for i in data["phonemic"]
                ],
            },
            "dictation": {
                "instruction": "Write what you hear",
                "items": [
                    {"number": data["dictation"]["number"], "word": data["dictation"]["word"]}
                ],
            },
            "multiple_choice": {
                "instruction": "Write the letter of the correct definition",
                "items": [
                    {
                        "number": data["mc"]["number"],
                        "word": data["mc"]["word"],
                        "options": data["mc"]["mc"]["options"],
                        "correct": data["mc"]["mc"]["correct"],
                        "definition": data["mc"]["mc"]["options"][data["mc"]["mc"]["correct"]],
                    }
                ],
            },
            "true_false": {
                "instruction": "True or False? Write T or F.",
                "items": [
                    {"number": i["number"], "statement": i["statement"], "answer": i["answer"], "explanation": i["explanation"]}
                    for i in data["tf"]
                ],
            },
            "short_answer": {
                "instruction": "Read the question. Write your answer (max 3 words or a number).",
                "number": data["short"]["number"],
                "question": data["short"]["question"],
                "answer": data["short"]["answer"],
                "acceptable_answers": data["short"]["acceptable_answers"],
            },
        },
    }

    ANSWER_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    path = ANSWER_KEYS_DIR / f"{level}-entry-ticket-{test_number}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(key, f, indent=2, ensure_ascii=False)
    print(f"  Answer key: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Grammar question bank
# ---------------------------------------------------------------------------

# Bank of T/F and short-answer questions per grammar focus.
# Each entry: {"tf": [Q1, Q2], "short": {Q3}}.
# Questions are selected by seeded random using the grammar focus + test number.

GRAMMAR_BANK = {
    "compound sentences": {
        "tf_pool": [
            {
                "statement": 'The following sentence is compound: "My friend and I went to Paris last year."',
                "answer": "F",
                "explanation": "Simple sentence (one subject 'my friend and I', one predicate 'went'). A compound sentence has two independent clauses joined by a conjunction.",
            },
            {
                "statement": 'This sentence is punctuated correctly: "My sister likes chocolate but I prefer icecream."',
                "answer": "F",
                "explanation": "Missing comma before 'but'. Should be: '...chocolate, but I...'",
            },
            {
                "statement": 'The following is a compound sentence: "She opened the door and the cat ran out."',
                "answer": "T",
                "explanation": "Two independent clauses ('She opened the door' + 'the cat ran out') joined by 'and'.",
            },
            {
                "statement": 'This sentence contains a coordinating conjunction: "I like tea but my brother prefers coffee."',
                "answer": "T",
                "explanation": "'But' is a coordinating conjunction joining two independent clauses.",
            },
            {
                "statement": 'The following is a simple sentence: "We went to the beach and we swam in the sea."',
                "answer": "F",
                "explanation": "This is a compound sentence — two independent clauses joined by 'and'.",
            },
            {
                "statement": 'This sentence needs a comma: "He studied hard so he passed the exam."',
                "answer": "T",
                "explanation": "Compound sentence needs a comma before 'so'. Should be: '...hard, so he...'",
            },
        ],
        "short_pool": [
            {
                "question": 'How many clauses does this sentence have? "My friend is a wise and courageous person."',
                "answer": "1",
                "acceptable_answers": ["1", "one", "1 clause", "one clause"],
            },
            {
                "question": 'Is this a compound sentence? Answer yes or no: "She sings and dances beautifully."',
                "answer": "no",
                "acceptable_answers": ["no", "n", "false", "f", "simple"],
            },
            {
                "question": 'What conjunction joins these clauses? "I wanted to go but I was too tired."',
                "answer": "but",
                "acceptable_answers": ["but"],
            },
            {
                "question": 'How many independent clauses does a compound sentence need?',
                "answer": "2",
                "acceptable_answers": ["2", "two"],
            },
        ],
    },
    "sentence fragments and run-ons": {
        "tf_pool": [
            {
                "statement": 'The following is a complete sentence: "Because she was tired after the long journey."',
                "answer": "F",
                "explanation": "This is a sentence fragment (dependent clause). A complete sentence needs an independent clause.",
            },
            {
                "statement": 'This is a run-on sentence: "I love reading books I could spend all day in a library."',
                "answer": "T",
                "explanation": "Two independent clauses joined without punctuation or conjunction — a fused sentence (run-on).",
            },
            {
                "statement": 'The following is a complete sentence: "When the bell rang."',
                "answer": "F",
                "explanation": "This is a fragment — 'when' makes it a dependent clause. Needs an independent clause.",
            },
            {
                "statement": 'This sentence is correct: "She went to the store and bought milk eggs and bread."',
                "answer": "F",
                "explanation": "Missing commas in a list. Should be: 'milk, eggs, and bread.'",
            },
            {
                "statement": 'The following is a complete sentence: "She ran."',
                "answer": "T",
                "explanation": "A complete sentence needs only a subject and a verb. 'She ran' has both.",
            },
            {
                "statement": 'This is a run-on sentence: "The weather was cold we stayed inside."',
                "answer": "T",
                "explanation": "Two independent clauses run together without punctuation or conjunction.",
            },
        ],
        "short_pool": [
            {
                "question": 'Sentence or fragment? "Although the movie was long and boring."',
                "answer": "fragment",
                "acceptable_answers": ["fragment", "sentence fragment", "F", "frag"],
            },
            {
                "question": 'Sentence or fragment? "She smiled."',
                "answer": "sentence",
                "acceptable_answers": ["sentence", "complete sentence", "S", "T"],
            },
            {
                "question": 'Is this a run-on? Answer yes or no: "I went home then I had dinner."',
                "answer": "yes",
                "acceptable_answers": ["yes", "y", "true", "t", "run-on"],
            },
            {
                "question": 'What is missing in this sentence? "I like reading I like writing too."',
                "answer": "punctuation",
                "acceptable_answers": ["punctuation", "a conjunction", "conjunction", "comma", "period"],
            },
        ],
    },
    "first conditional": {
        "tf_pool": [
            {
                "statement": 'This sentence is correct: "If it will rain, I stay home."',
                "answer": "F",
                "explanation": "First conditional uses present simple in the if-clause, not 'will'. Correct: 'If it rains, I will stay home.'",
            },
            {
                "statement": 'This is a correct first conditional: "If she studies, she will pass the exam."',
                "answer": "T",
                "explanation": "Present simple in the if-clause ('studies'), will + infinitive in the main clause ('will pass').",
            },
        ],
        "short_pool": [
            {
                "question": 'Complete: "If you heat ice, it ___." (fill with one word)',
                "answer": "melts",
                "acceptable_answers": ["melts", "will melt"],
            },
        ],
    },
}


def select_grammar_questions(grammar_focus: str, test_number: int, seed_base: str) -> dict:
    """Select T/F and short-answer questions from the bank for a given grammar focus."""
    key = grammar_focus.lower().strip()
    bank = GRAMMAR_BANK.get(key)
    if not bank:
        print(f"  WARNING: No grammar bank for '{grammar_focus}'. Using generic questions.")
        return {
            "tf": [
                {"number": 5, "statement": 'Grammar question 1 — check with your teacher.', "answer": "?", "explanation": "Bank not found"},
                {"number": 6, "statement": 'Grammar question 2 — check with your teacher.', "answer": "?", "explanation": "Bank not found"},
            ],
            "short": {"number": 7, "question": 'Grammar question — check with your teacher.', "answer": "?", "acceptable_answers": ["?"]},
        }

    rng = random.Random(f"{seed_base}-grammar-{key}")

    # Select 2 T/F questions (without replacement)
    tf_pool = bank["tf_pool"]
    rng.shuffle(tf_pool)
    selected_tf = tf_pool[:2]
    for i, q in enumerate(selected_tf):
        q["number"] = 5 + i

    # Select 1 short-answer question
    short_pool = bank["short_pool"]
    rng.shuffle(short_pool)
    selected_short = short_pool[0].copy()
    selected_short["number"] = 7

    return {"tf": selected_tf, "short": selected_short}


def main():
    # Parse CLI arguments
    import argparse
    parser = argparse.ArgumentParser(description="Build entry ticket test slideshow")
    parser.add_argument("--m2-grammar", help="Grammar focus for M2 (B1 level)")
    parser.add_argument("--m3-grammar", help="Grammar focus for M3 (B2 level)")
    args = parser.parse_args()

    # Determine test number
    test_number = 1
    if ANSWER_KEYS_DIR.exists():
        existing = list(ANSWER_KEYS_DIR.glob("*-entry-ticket-*.json"))
        if existing:
            nums = []
            for p in existing:
                m = re.search(r"(\d+)\.json$", p.name)
                if m:
                    nums.append(int(m.group(1)))
            if nums:
                test_number = max(nums) + 1

    print(f"Building Entry Ticket Number {test_number}")
    print()

    # Grammar focus: accept from CLI or prompt interactively
    m2_grammar = args.m2_grammar or input("M2 grammar focus? (B1 level) [Compound sentences]: ").strip() or "Compound sentences"
    m3_grammar = args.m3_grammar or input("M3 grammar focus? (B2 level) [Sentence fragments and run-ons]: ").strip() or "Sentence fragments and run-ons"

    global GRAMMAR
    GRAMMAR.clear()
    GRAMMAR["M2"] = {"focus": m2_grammar, "level": "B1"}
    GRAMMAR["M3"] = {"focus": m3_grammar, "level": "B2"}

    # Step 1: Extract word lists
    print("Extracting B1 words from Oxford 3000...")
    b1_words = extract_words_by_level(OXFORD_3000_CEFR_URL, "B1")
    print(f"  Found {len(b1_words)} B1 words")

    print("Extracting B2 words from Oxford 3000...")
    b2_words = extract_words_by_level(OXFORD_3000_CEFR_URL, "B2")
    print(f"  Found {len(b2_words)} B2 words")

    print()

    # Step 2: Collect previously used words from all earlier answer keys
    def get_used_words() -> set:
        """Scan ANSWER_KEYS/ for all words used in previous tests."""
        used = set()
        if not ANSWER_KEYS_DIR.exists():
            return used
        for f in sorted(ANSWER_KEYS_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for sec_key, sec_val in data.get("sections", {}).items():
                    items = sec_val.get("items", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        word = item.get("word", "")
                        if word:
                            used.add(word.lower())
            except (json.JSONDecodeError, KeyError):
                continue
        return used

    used_words = get_used_words()
    if used_words:
        print(f"  Excluding {len(used_words)} previously used word(s): {', '.join(sorted(used_words))}")

    # Select words for each level (filtered to those with available definitions, excluding used words)
    today = __import__("datetime").datetime.now().strftime("%m%d%y")
    seed_base = f"{today}-{test_number}"
    
    # Only use words that have definitions in our bank
    b1_with_defs = [w for w in b1_words if w in WORD_MEANINGS and w.lower() not in used_words]
    b2_with_defs = [w for w in b2_words if w in WORD_MEANINGS and w.lower() not in used_words]
    
    if len(b1_with_defs) < 6:
        print(f"  WARNING: Only {len(b1_with_defs)} B1 words with definitions available")
    if len(b2_with_defs) < 6:
        print(f"  WARNING: Only {len(b2_with_defs)} B2 words with definitions available")

    m2_word_pool = select_words(b1_with_defs, 6, f"{seed_base}-m2")
    m3_word_pool = select_words(b2_with_defs, 6, f"{seed_base}-m3")

    # Assign words to sections
    m2_data = {
        "phonemic": [{"number": 1, "word": m2_word_pool[0]}, {"number": 2, "word": m2_word_pool[1]}],
        "dictation": {"number": 3, "word": m2_word_pool[2]},
        "mc": {"number": 4, "word": m2_word_pool[3]},
        "tf": [],
        "short": {},
    }
    m3_data = {
        "phonemic": [{"number": 1, "word": m3_word_pool[0]}, {"number": 2, "word": m3_word_pool[1]}],
        "dictation": {"number": 3, "word": m3_word_pool[2]},
        "mc": {"number": 4, "word": m3_word_pool[3]},
        "tf": [],
        "short": {},
    }

    # Step 3: Generate phonemic transcriptions
    print("Generating phonemic transcriptions...")
    for level, data in [("M2", m2_data), ("M3", m3_data)]:
        for item in data["phonemic"]:
            ph = get_phonemic(item["word"])
            if ph:
                item["phonemic"] = ph
                print(f"  {level} phonemic {item['word']}: {ph}")
            else:
                print(f"  WARNING: No phonemic transcription for {item['word']}")
                item["phonemic"] = item["word"]  # fallback

    # Step 3b: Build MC items with level-appropriate definitions
    print("\nBuilding MC items with level-appropriate definitions...")
    for level, data in [("M2", m2_data), ("M3", m3_data)]:
        word = data["mc"]["word"]
        mc_seed = f"{seed_base}-{level.lower()}-mc-{data['mc']['number']}"
        data["mc"]["mc"] = build_mc_item(word, mc_seed)
        if data["mc"]["mc"]["correct"] != "?":
            print(f"  {level} MC {word}: correct={data['mc']['mc']['correct']}")
            print(f"    A. {data['mc']['mc']['options']['A'][:50]}...")
            print(f"    B. {data['mc']['mc']['options']['B'][:50]}...")
            print(f"    C. {data['mc']['mc']['options']['C'][:50]}...")
        else:
            print(f"  WARNING: No definition for {level} MC word '{word}'")

    # Step 4: True/False and Short Answer questions from grammar bank
    print(f"\nBuilding grammar questions ({GRAMMAR['M2']['focus']} / {GRAMMAR['M3']['focus']})...")
    for level, data in [("M2", m2_data), ("M3", m3_data)]:
        focus = GRAMMAR[level]["focus"]
        result = select_grammar_questions(focus, test_number, seed_base)
        data["tf"] = result["tf"]
        data["short"] = result["short"]
        for q in data["tf"]:
            print(f"  {level} T/F {q['number']}: {q['statement'][:60]}... → {q['answer']}")
        print(f"  {level} short: {data['short']['question'][:60]}... → {data['short']['answer']}")

    # Step 5: Generate TTS dictation audio
    print("\nGenerating TTS dictation audio...")
    test_dir = SLIDES_DIR / f"entry-ticket-{test_number}"
    test_assets = test_dir / "assets"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_assets.mkdir(exist_ok=True)

    for level, data in [("M2", m2_data), ("M3", m3_data)]:
        word = data["dictation"]["word"]
        num = data["dictation"]["number"]
        out = test_assets / f"{level.lower()}_dictation_{word}.mp3"
        generate_dictation_audio(word, num, level.lower(), out)

    # Step 6: Build slides
    print("\nBuilding slides HTML...")
    sections_html = build_all_slides(m2_data, m3_data, test_number)
    slides_html = splice_into_template(sections_html, test_number)

    index_path = test_dir / "index.html"
    index_path.write_text(slides_html, encoding="utf-8")
    print(f"  Slides: {index_path}")

    # Step 7: Generate root index.html (TOC listing all test versions)
    build_root_toc()

    # Step 8: Write answer keys
    print("\nWriting answer keys...")
    write_answer_key("M2", m2_data, test_number)
    write_answer_key("M3", m3_data, test_number)

    # Summary
    print("\n" + "=" * 50)
    print(f"Entry Ticket Number {test_number} build complete!")
    print(f"  Slides: {index_path}")
    print(f"  Answer keys: {ANSWER_KEYS_DIR / f'M2-entry-ticket-{test_number}.json'}")
    print(f"  Answer keys: {ANSWER_KEYS_DIR / f'M3-entry-ticket-{test_number}.json'}")
    print("=" * 50)

    # Print word selections for reference
    for level, data in [("M2", m2_data), ("M3", m3_data)]:
        phonemic_str = "; ".join(f"{i['number']}. {i['word']}" for i in data["phonemic"])
        print(f"\n{level} word selections:")
        print(f"  Phonemic: {phonemic_str}")
        print(f"  Dictation: {data['dictation']['number']}. {data['dictation']['word']}")
        print(f"  MC: {data['mc']['number']}. {data['mc']['word']}")
        print(f"  Grammar: {GRAMMAR[level]['focus']}")


if __name__ == "__main__":
    main()
