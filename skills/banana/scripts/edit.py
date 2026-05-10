#!/usr/bin/env python3
"""Image editing — Gemini direct API or kie.ai unified backend."""

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

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_DEFAULT_MODEL = "gemini-3.1-flash-image-preview"

KIE_API_BASE = "https://api.kie.ai/api/v1"
KIE_CREATE_TASK = f"{KIE_API_BASE}/jobs/createTask"
KIE_TASK_STATUS = f"{KIE_API_BASE}/jobs/recordInfo"
KIE_DEFAULT_MODEL = "nano-banana-pro"
KIE_POLL_INTERVAL = 5
KIE_MAX_WAIT = 300

OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
SUPPORTED_FORMATS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".webp": "image/webp", ".gif": "image/gif"}


def _json_request(url, payload=None, headers=None, method=None):
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
                print(f"Rate limited. Retrying {label} in {delay}s…", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            _die(e.code, body)
        except Exception as exc:
            print(f"Request error: {exc}", file=sys.stderr)
            sys.exit(1)
    print("Rate limit exceeded.", file=sys.stderr)
    sys.exit(1)


def _die(code, body):
    if code == 401:
        print("ERROR 401: Invalid API key.", file=sys.stderr)
    elif code == 402:
        print("ERROR 402: Insufficient credits. Top up at https://kie.ai/", file=sys.stderr)
    elif code == 422:
        print(f"ERROR 422: Invalid parameters — {body[:300]}", file=sys.stderr)
    elif code == 400 and "FAILED_PRECONDITION" in body:
        print("ERROR: Billing not enabled in Google AI Studio.", file=sys.stderr)
    else:
        print(f"HTTP {code}: {body[:400]}", file=sys.stderr)
    sys.exit(1)


def _save(data_or_url, prefix="banana_edit"):
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


def _load_local(image_path):
    path = Path(image_path).expanduser()
    if not path.exists():
        print(f"ERROR: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)
    mime = SUPPORTED_FORMATS.get(path.suffix.lower())
    if not mime:
        print(f"ERROR: Unsupported format '{path.suffix}'.", file=sys.stderr)
        sys.exit(1)
    return base64.b64encode(path.read_bytes()).decode("utf-8"), mime


# ── Gemini ────────────────────────────────────────────────────────────────────

def edit_gemini(args):
    key = args.api_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: Set GOOGLE_AI_API_KEY or pass --api-key.", file=sys.stderr)
        sys.exit(1)
    model = args.model or GEMINI_DEFAULT_MODEL
    image_b64, mime = _load_local(args.image)
    payload = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime, "data": image_b64}},
            {"text": args.prompt},
        ]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={key}"
    resp = _retry(lambda: _json_request(url, payload), label="Gemini edit")

    candidates = resp.get("candidates", [])
    if not candidates:
        print("ERROR: No candidates.", file=sys.stderr)
        sys.exit(1)
    finish = candidates[0].get("finishReason", "UNKNOWN")
    if finish in ("IMAGE_SAFETY", "PROHIBITED_CONTENT", "SAFETY", "RECITATION"):
        print(f"ERROR: Blocked ({finish}). Rephrase.", file=sys.stderr)
        sys.exit(1)
    parts = candidates[0].get("content", {}).get("parts", [])
    b64 = next((p["inlineData"]["data"] for p in parts if "inlineData" in p), None)
    text = next((p["text"] for p in parts if "text" in p), None)
    if not b64:
        print("ERROR: No image in response.", file=sys.stderr)
        sys.exit(1)
    return {"image_path": _save(b64), "backend": "gemini", "model": model,
            "source_image": args.image, "text_response": text}


# ── kie.ai ────────────────────────────────────────────────────────────────────

def _kie_headers(key):
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _kie_poll(key, task_id):
    deadline = time.time() + KIE_MAX_WAIT
    while time.time() < deadline:
        url = f"{KIE_TASK_STATUS}?taskId={task_id}"
        resp = _retry(lambda: _json_request(url, headers=_kie_headers(key), method="GET"),
                      label="kie.ai poll")
        data = resp.get("data") or {}
        status = data.get("status", "pending")
        print(f"  [{status}] taskId={task_id}", file=sys.stderr)
        if status == "succeed":
            candidates = [
                data.get("resultUrl"), data.get("imageUrl"),
                (data.get("resultJson") or {}).get("imageUrl"),
                (data.get("resultJson") or {}).get("url"),
            ]
            if isinstance(data.get("resultJson"), list) and data["resultJson"]:
                candidates.append(data["resultJson"][0].get("url"))
            image_url = next((u for u in candidates if u), None)
            if not image_url:
                print(f"ERROR: No image URL in result: {json.dumps(data)[:400]}", file=sys.stderr)
                sys.exit(1)
            return image_url
        if status in ("failed", "error"):
            print(f"ERROR: Task failed — {data.get('failReason', 'unknown')}", file=sys.stderr)
            sys.exit(1)
        time.sleep(KIE_POLL_INTERVAL)
    print(f"ERROR: Timeout after {KIE_MAX_WAIT}s.", file=sys.stderr)
    sys.exit(1)


def _kie_upload(key, image_path):
    """Upload local file to kie.ai and return remote URL."""
    path = Path(image_path).expanduser()
    mime = SUPPORTED_FORMATS.get(path.suffix.lower(), "image/png")
    boundary = "BananaBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = urllib.request.Request(
        f"{KIE_API_BASE}/upload", data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    url = (data.get("data") or {}).get("url") or data.get("url")
    if not url:
        print(f"ERROR: Upload failed: {json.dumps(data)[:300]}", file=sys.stderr)
        sys.exit(1)
    return url


def edit_kie(args):
    key = args.api_key or os.environ.get("KIE_API_KEY") or os.environ.get("KIE_AI_API_KEY")
    if not key:
        print("ERROR: Set KIE_API_KEY or pass --api-key.", file=sys.stderr)
        sys.exit(1)
    model = args.model or KIE_DEFAULT_MODEL

    # kie.ai edit requires a remote URL — upload the local file first
    print("Uploading source image to kie.ai…", file=sys.stderr)
    image_url = _kie_upload(key, args.image)
    print(f"Uploaded: {image_url}", file=sys.stderr)

    payload = {
        "model": model,
        "input": {
            "prompt": args.prompt,
            "image_url": image_url,
        },
    }
    resp = _retry(lambda: _json_request(KIE_CREATE_TASK, payload, _kie_headers(key)),
                  label="kie.ai createTask")
    task_id = (resp.get("data") or {}).get("taskId") or resp.get("taskId")
    if not task_id:
        print(f"ERROR: No taskId: {json.dumps(resp)[:300]}", file=sys.stderr)
        sys.exit(1)

    print(f"Task created: {task_id}. Polling…", file=sys.stderr)
    result_url = _kie_poll(key, task_id)
    return {"image_path": _save(result_url), "backend": "kie", "model": model,
            "source_image": args.image, "task_id": task_id}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Edit images — Gemini or kie.ai backend")
    parser.add_argument("--image", required=True, help="Path to source image")
    parser.add_argument("--prompt", required=True, help="Editing instructions")
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--backend", choices=["gemini", "kie"], default="gemini",
                        help="gemini = direct Google API (default); kie = kie.ai proxy")
    args = parser.parse_args()

    result = edit_kie(args) if args.backend == "kie" else edit_gemini(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
