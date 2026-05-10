#!/usr/bin/env python3
"""Fallback image generation script using Gemini REST API (no external dependencies)."""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_RESOLUTION = "2K"
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"

VALID_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2",
    "4:5", "5:4", "21:9", "1:4", "4:1", "1:8", "8:1",
]
VALID_RESOLUTIONS = ["512", "1K", "2K", "4K"]
VALID_THINKING_LEVELS = ["minimal", "low", "medium", "high"]


def get_api_key(args_key):
    key = args_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: No API key found. Set GOOGLE_AI_API_KEY or pass --api-key.", file=sys.stderr)
        print("Get a free key at: https://aistudio.google.com/apikey", file=sys.stderr)
        sys.exit(1)
    return key


def build_payload(prompt, aspect_ratio, resolution, thinking_level, image_only):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"] if image_only else ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": resolution,
            },
        },
    }
    if thinking_level:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level}
    return payload


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


def save_image(image_b64, aspect_ratio, resolution, model):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUT_DIR / f"banana_{timestamp}.png"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(image_b64))
    return str(filename)


def main():
    parser = argparse.ArgumentParser(description="Generate images via Gemini API")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--aspect-ratio", default="1:1", choices=VALID_ASPECT_RATIOS)
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, choices=VALID_RESOLUTIONS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", help="Google AI API key")
    parser.add_argument("--thinking", choices=VALID_THINKING_LEVELS, help="Thinking level")
    parser.add_argument("--image-only", action="store_true", help="Return image only (no text)")
    args = parser.parse_args()

    api_key = get_api_key(args.api_key)
    payload = build_payload(args.prompt, args.aspect_ratio, args.resolution, args.thinking, args.image_only)
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
        print("ERROR: No image in response. Check responseModalities.", file=sys.stderr)
        sys.exit(1)

    path = save_image(image_data, args.aspect_ratio, args.resolution, args.model)
    result = {
        "image_path": path,
        "model": args.model,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "text_response": text_response,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
