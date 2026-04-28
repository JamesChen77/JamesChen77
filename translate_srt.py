#!/usr/bin/env python3
"""
Translate an English SRT file to Simplified Chinese.
Timestamps are preserved exactly; only text lines are translated.

Pick your translator by setting the TRANSLATOR environment variable:

    TRANSLATOR=google   (default — free, no account needed)
    TRANSLATOR=deepl    (free up to 500k chars/month, needs DEEPL_API_KEY)
    TRANSLATOR=gemini   (generous free tier, needs GEMINI_API_KEY)
    TRANSLATOR=ollama   (runs on your computer, totally free, needs Ollama installed)
    TRANSLATOR=claude   (paid, highest quality, needs ANTHROPIC_API_KEY)

Usage:
    python3 translate_srt.py input.en.srt output.zh.srt
"""

import sys
import re
import os

BATCH_SIZE = 40
OLLAMA_BATCH_SIZE = 10  # smaller batches for local CPU
OLLAMA_TIMEOUT = 300    # 5 minutes per batch
TRANSLATOR = os.environ.get("TRANSLATOR", "google").lower()


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_srt(path: str) -> list[dict]:
    blocks = []
    with open(path, encoding="utf-8") as f:
        content = f.read()
    for block in re.split(r"\n\n+", content.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        blocks.append({
            "index": lines[0].strip(),
            "timestamp": lines[1].strip(),
            "text": "\n".join(lines[2:]).strip(),
        })
    return blocks


def write_srt(path: str, blocks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for b in blocks:
            f.write(f"{b['index']}\n{b['timestamp']}\n{b['text']}\n\n")


# ── Translation backends ──────────────────────────────────────────────────────

def translate_google(texts: list[str]) -> list[str]:
    """Free Google Translate via deep-translator. No account needed."""
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source="en", target="zh-CN")
    results = []
    for text in texts:
        try:
            results.append(translator.translate(text) or text)
        except Exception as e:
            print(f"  WARNING: translation failed for '{text[:30]}...': {e}", file=sys.stderr)
            results.append(text)
    return results


def translate_deepl(texts: list[str]) -> list[str]:
    """DeepL free tier — up to 500k characters/month. Needs DEEPL_API_KEY."""
    import deepl
    api_key = os.environ.get("DEEPL_API_KEY")
    if not api_key:
        sys.exit("ERROR: Set DEEPL_API_KEY environment variable (get a free key at deepl.com/pro-api)")
    translator = deepl.Translator(api_key)
    results = translator.translate_text(texts, source_lang="EN", target_lang="ZH")
    return [r.text for r in results]


def translate_gemini(texts: list[str]) -> list[str]:
    """Google Gemini free tier. Needs GEMINI_API_KEY from aistudio.google.com."""
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("ERROR: Set GEMINI_API_KEY environment variable (free at aistudio.google.com)")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    numbered = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))
    prompt = (
        "Translate these numbered English subtitle lines into natural Simplified Chinese (Mandarin). "
        "Output ONLY the translated lines with [N] prefix. No extra text.\n\n" + numbered
    )
    response = model.generate_content(prompt)
    return _parse_numbered_response(response.text, texts)


def translate_ollama(texts: list[str]) -> list[str]:
    """Ollama running locally — free forever. Install from ollama.com, then run: ollama pull qwen2.5:7b"""
    import urllib.request, json
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    numbered = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))
    prompt = (
        "Translate these numbered English subtitle lines into natural Simplified Chinese (Mandarin). "
        "Output ONLY the translated lines with [N] prefix. No extra text.\n\n" + numbered
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read())
        return _parse_numbered_response(data["response"], texts)
    except Exception as e:
        sys.exit(f"ERROR: Could not reach Ollama at localhost:11434. Is it running? Details: {e}")


def translate_claude(texts: list[str]) -> list[str]:
    """Anthropic Claude API — paid, highest quality. Needs ANTHROPIC_API_KEY."""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: Set ANTHROPIC_API_KEY environment variable.")
    client = anthropic.Anthropic(api_key=api_key)
    numbered = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))
    prompt = (
        "You are a professional subtitle translator. Translate the following numbered English subtitle lines "
        "into natural, fluent Simplified Chinese (Mandarin). "
        "Output ONLY the translated lines, each prefixed with [N]. No extra text.\n\n" + numbered
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_numbered_response(message.content[0].text, texts)


def _parse_numbered_response(response_text: str, original_texts: list[str]) -> list[str]:
    """Extract [N] prefixed lines from an LLM response."""
    translations = []
    for line in response_text.strip().splitlines():
        m = re.match(r"\[(\d+)\]\s*(.*)", line)
        if m:
            translations.append(m.group(2).strip())
    if len(translations) != len(original_texts):
        print(
            f"  WARNING: Expected {len(original_texts)} translations, got {len(translations)}.",
            file=sys.stderr,
        )
        while len(translations) < len(original_texts):
            translations.append(original_texts[len(translations)])
    return translations


# ── Main ──────────────────────────────────────────────────────────────────────

BACKENDS = {
    "google": translate_google,
    "deepl":  translate_deepl,
    "gemini": translate_gemini,
    "ollama": translate_ollama,
    "claude": translate_claude,
}


def main():
    if len(sys.argv) < 3:
        print("Usage: translate_srt.py input.en.srt output.zh.srt")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    if TRANSLATOR not in BACKENDS:
        sys.exit(f"ERROR: Unknown TRANSLATOR '{TRANSLATOR}'. Choose: {', '.join(BACKENDS)}")

    # Install missing packages automatically
    _ensure_deps()

    translate_fn = BACKENDS[TRANSLATOR]
    print(f"  Using translator: {TRANSLATOR}")

    blocks = parse_srt(input_path)
    print(f"  {len(blocks)} subtitle blocks found in {input_path}")

    translated_blocks = []
    total = len(blocks)

    # Use smaller batches for local models; Google one at a time for rate limits
    if TRANSLATOR == "google":
        batch_size = 1
    elif TRANSLATOR == "ollama":
        batch_size = OLLAMA_BATCH_SIZE
    else:
        batch_size = BATCH_SIZE

    for start in range(0, total, batch_size):
        batch = blocks[start: start + batch_size]
        texts = [b["text"] for b in batch]
        end_idx = min(start + batch_size, total)
        print(f"  Translating {start+1}–{end_idx} / {total}...", end="\r")
        zh_texts = translate_fn(texts)
        for block, zh in zip(batch, zh_texts):
            translated_blocks.append({
                "index": block["index"],
                "timestamp": block["timestamp"],
                "text": zh,
            })

    print()
    write_srt(output_path, translated_blocks)
    print(f"  Translation complete → {output_path}")


def _ensure_deps():
    """Auto-install the library needed for the chosen translator."""
    packages = {
        "google": ("deep_translator", "deep-translator"),
        "deepl":  ("deepl",           "deepl"),
        "gemini": ("google.generativeai", "google-generativeai"),
        "ollama": (None,              None),   # uses stdlib only
        "claude": ("anthropic",       "anthropic"),
    }
    module, pip_name = packages.get(TRANSLATOR, (None, None))
    if module is None:
        return
    try:
        __import__(module)
    except ImportError:
        import subprocess
        print(f"  Installing {pip_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name, "-q"])


if __name__ == "__main__":
    main()
