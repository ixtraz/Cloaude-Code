#!/usr/bin/env python3
"""Image generation — Gemini direct API or kie.ai unified backend."""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_DEFAULT_MODEL = "gemini-3.1-flash-image-preview"

# ── kie.ai ────────────────────────────────────────────────────────────────────
KIE_API_BASE = "https://api.kie.ai/api/v1"
KIE_CREATE_TASK = f"{KIE_API_BASE}/jobs/createTask"
KIE_TASK_STATUS = f"{KIE_API_BASE}/jobs/recordInfo"
KIE_DEFAULT_MODEL = "nano-banana-pro"
KIE_POLL_INTERVAL = 5   # seconds between polls
KIE_MAX_WAIT = 300      # bail out after 5 minutes

KIE_MODELS = [
    "nano-banana-pro",      # Gemini 3 Pro (4K, best quality)
    "nano-banana-2",        # Gemini 2.5 Flash (budget)
    "flux-kontext-pro",     # Flux.1 Kontext Pro
    "flux-kontext-dev",     # Flux.1 Kontext Dev (faster)
    "4o-image",             # GPT-Image-1 / GPT-4o
    "midjourney",           # Midjourney v7
    "grok-imagine",         # Grok Imagine (xAI)
    "seedream",             # Bytedance Seedream
]

# ── shared ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
VALID_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2",
    "4:5", "5:4", "21:9", "1:4", "4:1", "1:8", "8:1",
]
VALID_RESOLUTIONS = ["512", "1K", "2K", "4K"]
VALID_THINKING = ["minimal", "low", "medium", "high"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _json_request(url, payload=None, headers=None, method=None):
    """Single HTTP call; returns parsed JSON. Raises urllib.error.HTTPError on failure."""
    if method is None:
        method = "POST" if payload is not None else "GET"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _retry(fn, retries=4, label="request"):
    delay = 2
    for attempt in range(retries + 1):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < retries:
                print(f"Rate limited (429). Retrying {label} in {delay}s…", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            _die_on_http(e.code, body)
        except Exception as exc:
            print(f"Request error: {exc}", file=sys.stderr)
            sys.exit(1)
    print(f"Rate limit exceeded after {retries} retries.", file=sys.stderr)
    sys.exit(1)


def _die_on_http(code, body):
    if code == 401:
        print("ERROR 401: Invalid API key.", file=sys.stderr)
    elif code == 402:
        print("ERROR 402: Insufficient credits on kie.ai. Top up at https://kie.ai/", file=sys.stderr)
    elif code == 422:
        print(f"ERROR 422: Invalid parameters — {body[:300]}", file=sys.stderr)
    elif code == 400 and "FAILED_PRECONDITION" in body:
        print("ERROR: Billing not enabled in Google AI Studio.", file=sys.stderr)
    else:
        print(f"HTTP {code}: {body[:400]}", file=sys.stderr)
    sys.exit(1)


def _save_image(data_or_url, prefix="banana"):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_DIR / f"{prefix}_{ts}.png"
    if data_or_url.startswith("http"):
        req = urllib.request.Request(data_or_url, headers={"User-Agent": "banana-claude/1.4"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out.write_bytes(r.read())
    else:
        out.write_bytes(base64.b64decode(data_or_url))
    return str(out)


# ── Gemini backend ────────────────────────────────────────────────────────────

def _gemini_key(args_key):
    key = args_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: Set GOOGLE_AI_API_KEY or pass --api-key.", file=sys.stderr)
        print("Free key: https://aistudio.google.com/apikey", file=sys.stderr)
        sys.exit(1)
    return key


def generate_gemini(args):
    api_key = _gemini_key(args.api_key)
    model = args.model or GEMINI_DEFAULT_MODEL
    payload = {
        "contents": [{"parts": [{"text": args.prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"] if args.image_only else ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": args.aspect_ratio,
                "imageSize": args.resolution,
            },
        },
    }
    if args.thinking:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": args.thinking}

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    response = _retry(lambda: _json_request(url, payload), label="Gemini generate")

    candidates = response.get("candidates", [])
    if not candidates:
        print("ERROR: No candidates in response.", file=sys.stderr)
        sys.exit(1)

    finish = candidates[0].get("finishReason", "UNKNOWN")
    if finish in ("IMAGE_SAFETY", "PROHIBITED_CONTENT", "SAFETY", "RECITATION"):
        print(f"ERROR: Blocked ({finish}). Rephrase your prompt.", file=sys.stderr)
        sys.exit(1)

    parts = candidates[0].get("content", {}).get("parts", [])
    image_b64 = next((p["inlineData"]["data"] for p in parts if "inlineData" in p), None)
    text = next((p["text"] for p in parts if "text" in p), None)

    if not image_b64:
        print("ERROR: No image in response.", file=sys.stderr)
        sys.exit(1)

    path = _save_image(image_b64)
    return {"image_path": path, "backend": "gemini", "model": model,
            "aspect_ratio": args.aspect_ratio, "resolution": args.resolution,
            "text_response": text}


# ── kie.ai backend ────────────────────────────────────────────────────────────

def _kie_key(args_key):
    key = args_key or os.environ.get("KIE_API_KEY") or os.environ.get("KIE_AI_API_KEY")
    if not key:
        print("ERROR: Set KIE_API_KEY or pass --api-key.", file=sys.stderr)
        print("Get a key at: https://kie.ai/", file=sys.stderr)
        sys.exit(1)
    return key


def _kie_headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _kie_submit(api_key, model, prompt, aspect_ratio, resolution):
    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        },
    }
    headers = _kie_headers(api_key)
    resp = _retry(
        lambda: _json_request(KIE_CREATE_TASK, payload, headers),
        label="kie.ai createTask",
    )
    task_id = (resp.get("data") or {}).get("taskId") or resp.get("taskId")
    if not task_id:
        print(f"ERROR: No taskId in kie.ai response: {json.dumps(resp)[:300]}", file=sys.stderr)
        sys.exit(1)
    return task_id


def _kie_poll(api_key, task_id):
    headers = _kie_headers(api_key)
    deadline = time.time() + KIE_MAX_WAIT
    while time.time() < deadline:
        url = f"{KIE_TASK_STATUS}?taskId={task_id}"
        resp = _retry(lambda: _json_request(url, headers=headers, method="GET"), label="kie.ai poll")
        data = resp.get("data") or {}
        status = data.get("status", "pending")
        print(f"  [{status}] taskId={task_id}", file=sys.stderr)

        if status == "succeed":
            # result URL lives in various places depending on model
            url_candidates = [
                data.get("resultUrl"),
                data.get("imageUrl"),
                (data.get("resultJson") or {}).get("imageUrl"),
                (data.get("resultJson") or {}).get("url"),
            ]
            # some models return a list
            if isinstance(data.get("resultJson"), list) and data["resultJson"]:
                url_candidates.append(data["resultJson"][0].get("url"))

            image_url = next((u for u in url_candidates if u), None)
            if not image_url:
                print(f"ERROR: Task succeeded but no image URL found: {json.dumps(data)[:400]}", file=sys.stderr)
                sys.exit(1)
            return image_url

        if status in ("failed", "error"):
            msg = data.get("failReason") or data.get("message") or "unknown error"
            print(f"ERROR: kie.ai task failed — {msg}", file=sys.stderr)
            sys.exit(1)

        time.sleep(KIE_POLL_INTERVAL)

    print(f"ERROR: Timed out after {KIE_MAX_WAIT}s waiting for kie.ai task {task_id}.", file=sys.stderr)
    sys.exit(1)


def generate_kie(args):
    api_key = _kie_key(args.api_key)
    model = args.model or KIE_DEFAULT_MODEL
    print(f"Submitting to kie.ai [{model}]…", file=sys.stderr)
    task_id = _kie_submit(api_key, model, args.prompt, args.aspect_ratio, args.resolution)
    print(f"Task created: {task_id}. Polling…", file=sys.stderr)
    image_url = _kie_poll(api_key, task_id)
    path = _save_image(image_url)
    return {"image_path": path, "backend": "kie", "model": model,
            "aspect_ratio": args.aspect_ratio, "resolution": args.resolution,
            "task_id": task_id}


# ── cost helpers ─────────────────────────────────────────────────────────────

def _lookup_price(model, resolution):
    """Return estimated cost per image in USD."""
    import importlib.util, sys as _sys
    spec = importlib.util.spec_from_file_location(
        "cost_tracker", SCRIPT_DIR / "cost_tracker.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.lookup_price(model, resolution)


def _print_cost(model, resolution, backend):
    try:
        price = _lookup_price(model, resolution)
        print(f"  💰 Est. cost: ~${price:.3f}  ({backend} / {model} / {resolution})", file=sys.stderr)
    except Exception:
        pass


def _log_cost(model, resolution, backend, prompt):
    try:
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "cost_tracker.py"),
             "log", "--model", model, "--resolution", resolution,
             "--prompt", prompt[:80]],
            capture_output=True,
        )
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate images — Gemini or kie.ai backend")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--aspect-ratio", default="1:1", choices=VALID_ASPECT_RATIOS)
    parser.add_argument("--resolution", default="2K", choices=VALID_RESOLUTIONS)
    parser.add_argument("--model", default=None,
                        help="Model ID. Gemini default: gemini-3.1-flash-image-preview. "
                             f"kie.ai options: {', '.join(KIE_MODELS)}")
    parser.add_argument("--api-key", help="API key (GOOGLE_AI_API_KEY or KIE_API_KEY)")
    parser.add_argument("--backend", choices=["gemini", "kie"], default="gemini",
                        help="gemini = direct Google API (default); kie = kie.ai unified proxy")
    # Gemini-only flags
    parser.add_argument("--thinking", choices=VALID_THINKING, help="[gemini] Thinking level")
    parser.add_argument("--image-only", action="store_true", help="[gemini] Image-only output")
    args = parser.parse_args()

    effective_model = args.model or (KIE_DEFAULT_MODEL if args.backend == "kie" else GEMINI_DEFAULT_MODEL)
    _print_cost(effective_model, args.resolution, args.backend)

    if args.backend == "kie":
        result = generate_kie(args)
    else:
        result = generate_gemini(args)

    _log_cost(effective_model, args.resolution, args.backend, args.prompt)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
