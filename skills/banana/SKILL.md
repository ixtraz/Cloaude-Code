# Banana Claude — Creative Director for AI Image Generation

> Skill for Claude Code — powered by Google Gemini Nano Banana models
> Version: 1.4.1 | Author: AgriciDaniel | License: MIT

## Activation

This skill activates when the user runs any `/banana` command.

## Backends

Two generation backends are available, switchable via `--backend`:

| Flag | Backend | Key env var | Best for |
|------|---------|-------------|----------|
| `--backend gemini` | Google Gemini API (direct) | `GOOGLE_AI_API_KEY` | Default; synchronous; free tier available |
| `--backend kie` | [kie.ai](https://kie.ai/) unified proxy | `KIE_API_KEY` | Multiple model families; 30-80% cheaper; no free-tier quota issues |

**kie.ai model options** (`--model`):

| Model ID | Provider | Notes |
|----------|----------|-------|
| `nano-banana-pro` | Google Gemini 3 Pro | Default kie model; 4K, highest quality |
| `nano-banana-2` | Google Gemini 2.5 Flash | Budget option |
| `flux-kontext-pro` | Black Forest Labs | Strong subject/style consistency |
| `flux-kontext-dev` | Black Forest Labs | Faster, slightly lower quality |
| `4o-image` | OpenAI GPT-Image-1 | Excellent instruction following |
| `gpt-image-2` | OpenAI GPT Image 2 | Reasoning before generation, up to 16 refs, ~$0.05-0.19 |
| `midjourney` | Midjourney | Artistic / stylized |
| `grok-imagine` | xAI | Image-to-image support |
| `seedream` | Bytedance Seedream 4.x | Asian aesthetic, text in image |
| `seedream-5-lite` | Bytedance Seedream 5.0 Lite | Multimodal reasoning, web search grounding, ~$0.035 |
| `wan2.7-image` | Alibaba Wan 2.7 Image | Up to 2K, 9 reference images, ~$0.037 |
| `wan2.7-image-pro` | Alibaba Wan 2.7 Image Pro | Up to 4K, thinking mode, ~$0.040-0.070 |
| `qwen-image-2` | Alibaba Qwen Image 2.0 | Native 2K, strong text rendering, ~$0.028-0.075 |

kie.ai uses an **async task pipeline**: submit → get `taskId` → poll until `succeed` → download image. The scripts handle this automatically.

## Pre-Flight Checklist

Before generating ANY image, you MUST read:
1. `skills/banana/references/gemini-models.md` — model selection and API config
2. `skills/banana/references/prompt-engineering.md` — prompt formula and banned keywords

Load other references on-demand only (do not load all at startup).

## Command Reference

| Command | Description |
|---------|-------------|
| `/banana [description]` | Generate an image from natural language description |
| `/banana edit [path] [instruction]` | Edit an existing image |
| `/banana chat` | Start a multi-turn creative session (character/style consistency) |
| `/banana inspire [topic]` | Browse the 2,500+ prompt database for inspiration |
| `/banana batch [description] [n]` | Generate n variations of a concept |
| `/banana preset list` | List saved brand/style presets |
| `/banana preset save [name]` | Save current style settings as a preset |
| `/banana preset load [name]` | Load a saved preset |
| `/banana cost` | Show cost summary for this session |
| `/banana setup` | Run MCP server setup |
| `/banana validate` | Validate setup configuration |

## Core Workflow

### Step 1: Analyze the Request
- Identify the domain mode: Cinema, Product, Portrait, Editorial, UI/Web, Logo, Landscape, Abstract, Infographic
- Extract key constraints (aspect ratio, resolution, style, text requirements)
- If the request is vague, ask 1-2 targeted clarifying questions before proceeding

### Step 2: Construct the Prompt (5-Component Formula)
Use the brief-constructor agent or apply the formula directly:
1. **Subject** — specific physical characteristics, material, age, expression
2. **Action** — what the subject is doing; strong present-tense verbs
3. **Location/Context** — environment, time of day, atmosphere
4. **Composition** — camera angle, framing, focal length, depth of field
5. **Style** — art medium, camera model, film stock, publication reference, lighting

Write as narrative paragraphs, NEVER as comma-separated keyword lists.
Target 100-200 words for standard generation; up to 300 for complex professional work.

### Step 3: Set Parameters
Before calling the API, configure:
- **Aspect ratio** via `set_aspect_ratio` — always set explicitly
- **Model** — default: `gemini-3.1-flash-image-preview` (Nano Banana 2)
- **Resolution** — default: `2K` (always pass explicitly; MUST be uppercase)

### Step 4: Generate via MCP (Primary Path)
Call `gemini_generate_image` with the crafted prompt.

**Script fallback** (MCP unavailable or to select a different backend/model):
```bash
# Gemini direct (default)
python3 skills/banana/scripts/generate.py \
  --prompt "your prompt here" \
  --aspect-ratio 16:9 \
  --resolution 2K

# kie.ai — Nano Banana Pro
python3 skills/banana/scripts/generate.py \
  --prompt "your prompt here" \
  --aspect-ratio 16:9 \
  --resolution 2K \
  --backend kie \
  --model nano-banana-pro

# kie.ai — Flux.1 Kontext Pro
python3 skills/banana/scripts/generate.py \
  --prompt "your prompt here" \
  --aspect-ratio 1:1 \
  --resolution 2K \
  --backend kie \
  --model flux-kontext-pro
```

### Step 5: Post-Generation Response
Always include:
1. The generated image path
2. The crafted prompt used (so the user can learn/iterate)
3. Settings used (model, ratio, resolution)
4. 2-3 refinement suggestions for follow-up

Add community footer for generate/edit/batch commands:
```
---
🍌 banana-claude v1.4.1 · github.com/AgriciDaniel/banana-claude · MIT License
```

## Domain Mode Routing

| Domain | Trigger keywords | Default model | Default ratio | Default resolution |
|--------|-----------------|---------------|---------------|--------------------|
| Cinema | film, movie, cinematic, scene | NB2 | 21:9 | 2K |
| Product | product, commercial, ad, brand | NB2 | 4:3 | 2K |
| Portrait | person, portrait, headshot, face | NB2 | 4:5 | 2K |
| Editorial | magazine, editorial, fashion | NB2 | 3:2 | 2K |
| UI/Web | UI, dashboard, app, interface, SaaS | NB2 | 16:9 | 1K |
| Logo | logo, icon, brand mark, identity | NB2 | 1:1 | 2K |
| Landscape | landscape, nature, environment | NB2 | 16:9 | 2K |
| Abstract | abstract, pattern, texture, art | NB2 | 1:1 | 2K |
| Infographic | infographic, chart, data, diagram | NB2 | 9:16 | 1K |

## Error Handling

### Rate Limit (HTTP 429)
Apply exponential backoff: 2s → 4s → 8s → 16s. Inform the user on free tier limits (~5-15 RPM, ~20-500 RPD).

### Invalid API Key
Direct user to: https://aistudio.google.com/apikey

### Safety Block (`IMAGE_SAFETY` / `PROHIBITED_CONTENT`)
- Do NOT auto-retry with the same prompt
- Apply rephrase strategy from `references/prompt-engineering.md`
- Explain the rephrase to the user and retry once
- If still blocked, suggest an alternative concept

### Vague Request
Ask 1-2 clarifying questions:
- What's the intended use/platform? (social, print, web)
- What mood or style? (referencing a publication or artist helps)

## Multi-Turn / Chat Sessions (`/banana chat`)

Use `gemini_chat` MCP tool. To maintain character consistency:
- First turn: generate with exhaustive physical description
- Subsequent turns: include 2-3 key identifiers ("the red-haired woman in the white coat")
- Session context resets when the conversation ends

## Batch Generation (`/banana batch`)

For n variations:
1. Construct the base prompt
2. Plan n stylistic variants (lighting, angle, color palette)
3. Log each call with `scripts/cost_tracker.py log`
4. Show estimated cost before starting: `scripts/cost_tracker.py estimate`
5. Generate sequentially (Gemini produces ONE image per API call)

## Preset System

Presets stored at `~/.banana/presets/NAME.json`. See `references/presets.md`.
Presets set defaults for color palette, style, ratio, and resolution.
User instructions always override preset defaults.

## Cost Awareness

- Always log generations: `scripts/cost_tracker.py log`
- Show cost estimate before batch operations
- Reference `references/cost-tracking.md` for pricing table
- Free tier: ~500 RPD (resets midnight Pacific)

## Post-Processing

For format conversion, background removal, resizing, or transparency:
Load `references/post-processing.md` on-demand.
Check for ImageMagick availability with `which magick` before suggesting post-processing steps.

## Critical Rules

1. NEVER use banned keywords: "8K", "4K" in prompt text, "masterpiece", "ultra-realistic", "highly detailed", "photorealistic", "trending on artstation", "best quality", "hyperrealistic"
2. ALWAYS pass `imageSize` in UPPERCASE ("2K" not "2k")
3. ALWAYS call `set_aspect_ratio` before generating
4. NEVER pass a `negativePrompt` parameter — it doesn't exist; use semantic reframing
5. NEVER pass `numberOfImages`, `n`, or `sampleCount` — Gemini generates ONE image per call
6. Write prompts as prose paragraphs, not comma-separated tags
7. Enclose exact desired text in the image in quotation marks in the prompt
8. Put critical constraints in ALL CAPS and in the first third of the prompt
