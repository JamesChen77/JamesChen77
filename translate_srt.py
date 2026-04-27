#!/usr/bin/env python3
"""
Translate an English SRT file to Simplified Chinese using the Claude API.
Timestamps are preserved exactly; only text lines are translated.

Usage:
    python3 translate_srt.py input.en.srt output.zh.srt
"""

import sys
import re
import os
import anthropic

BATCH_SIZE = 40  # subtitle blocks per API call


def parse_srt(path: str) -> list[dict]:
    """Parse SRT into list of {index, timestamp, text} dicts."""
    blocks = []
    with open(path, encoding="utf-8") as f:
        content = f.read()

    raw_blocks = re.split(r"\n\n+", content.strip())
    for block in raw_blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        index = lines[0].strip()
        timestamp = lines[1].strip()
        text = "\n".join(lines[2:]).strip()
        blocks.append({"index": index, "timestamp": timestamp, "text": text})
    return blocks


def write_srt(path: str, blocks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for b in blocks:
            f.write(f"{b['index']}\n{b['timestamp']}\n{b['text']}\n\n")


def translate_batch(client: anthropic.Anthropic, texts: list[str]) -> list[str]:
    """Send a batch of English subtitle texts; return Simplified Chinese translations."""
    numbered = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))
    prompt = (
        "You are a professional subtitle translator. Translate the following numbered English subtitle lines "
        "into natural, fluent Simplified Chinese (Mandarin). "
        "Rules:\n"
        "- Output ONLY the translated lines, each prefixed with [N] matching the input number.\n"
        "- Keep the same number of lines as the input.\n"
        "- Preserve proper nouns, technical terms, and names as appropriate.\n"
        "- Use natural spoken Chinese suitable for subtitles — concise and clear.\n"
        "- Do NOT add explanations, notes, or any extra text.\n\n"
        f"{numbered}"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text.strip()

    translations = []
    for line in response_text.splitlines():
        m = re.match(r"\[(\d+)\]\s*(.*)", line)
        if m:
            translations.append(m.group(2).strip())

    if len(translations) != len(texts):
        print(
            f"  WARNING: Expected {len(texts)} translations, got {len(translations)}. "
            "Using original text for missing entries.",
            file=sys.stderr,
        )
        while len(translations) < len(texts):
            translations.append(texts[len(translations)])

    return translations


def main():
    if len(sys.argv) < 3:
        print("Usage: translate_srt.py input.en.srt output.zh.srt")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"  Parsing {input_path}...")
    blocks = parse_srt(input_path)
    print(f"  {len(blocks)} subtitle blocks found.")

    translated_blocks = []
    total = len(blocks)
    for start in range(0, total, BATCH_SIZE):
        batch = blocks[start : start + BATCH_SIZE]
        texts = [b["text"] for b in batch]
        end_idx = min(start + BATCH_SIZE, total)
        print(f"  Translating blocks {start+1}–{end_idx} / {total}...")
        zh_texts = translate_batch(client, texts)
        for block, zh in zip(batch, zh_texts):
            translated_blocks.append(
                {"index": block["index"], "timestamp": block["timestamp"], "text": zh}
            )

    write_srt(output_path, translated_blocks)
    print(f"  Translation complete → {output_path}")


if __name__ == "__main__":
    main()
