#!/usr/bin/env python3
"""Fallback image editing script using Gemini REST API (no external dependencies)."""

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
SUPPORTED_FORMATS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".webp": "image/webp", ".gif": "image/gif"}


def get_api_key(args_key):
    key = args_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: No API key found. Set GOOGLE_AI_API_KEY or pass --api-key.", file=sys.stderr)
        print("Get a free key at: https://aistudio.google.com/apikey", file=sys.stderr)
        sys.exit(1)
    return key


def load_image(image_path):
    path = Path(image_path).expanduser()
    if not path.exists():
        print(f"ERROR: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)
    suffix = path.suffix.lower()
    mime = SUPPORTED_FORMATS.get(suffix)
    if not mime:
        print(f"ERROR: Unsupported format '{suffix}'. Use: {', '.join(SUPPORTED_FORMATS)}", file=sys.stderr)
        sys.exit(1)
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime


def call_api(model, api_key, payload, retries=4):
    url = f"{API_BASE}/{model}:generateContent?key={api_key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    delay = 2
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                if attempt < retries:
                    print(f"Rate limited (429). Retrying in {delay}s...", file=sys.stderr)
                    time.sleep(delay)
                    delay *= 2
                    continue
                print(f"Rate limit exceeded after {retries} retries.", file=sys.stderr)
            elif e.code == 400 and "FAILED_PRECONDITION" in body:
                print("ERROR: Billing not enabled. Enable billing in Google AI Studio.", file=sys.stderr)
            else:
                print(f"HTTP {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Request error: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Edit images via Gemini API")
    parser.add_argument("--image", required=True, help="Path to the image to edit")
    parser.add_argument("--prompt", required=True, help="Editing instructions")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", help="Google AI API key")
    args = parser.parse_args()

    api_key = get_api_key(args.api_key)
    image_b64, mime_type = load_image(args.image)

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                {"text": args.prompt},
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    response = call_api(args.model, api_key, payload)

    candidates = response.get("candidates", [])
    if not candidates:
        print("ERROR: No candidates in response.", file=sys.stderr)
        sys.exit(1)

    finish_reason = candidates[0].get("finishReason", "UNKNOWN")
    if finish_reason in ("IMAGE_SAFETY", "PROHIBITED_CONTENT", "SAFETY", "RECITATION"):
        print(f"ERROR: Generation blocked ({finish_reason}). Rephrase your prompt.", file=sys.stderr)
        sys.exit(1)

    parts = candidates[0].get("content", {}).get("parts", [])
    image_data = None
    text_response = None
    for part in parts:
        if "inlineData" in part:
            image_data = part["inlineData"]["data"]
        elif "text" in part:
            text_response = part["text"]

    if not image_data:
        print("ERROR: No image in response.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"banana_edit_{timestamp}.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(image_data))

    result = {
        "image_path": str(out_path),
        "model": args.model,
        "source_image": args.image,
        "text_response": text_response,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
