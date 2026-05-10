# Brand/Style Presets Reference

> Load this on-demand when the user asks about presets or brand consistency.

## Preset Storage

Presets are stored as JSON files at `~/.banana/presets/NAME.json`.
Created automatically when you run `/banana preset save NAME`.

## Preset Structure

```json
{
  "name": "my-brand",
  "description": "Brand description",
  "colorPalette": ["#2563EB", "#FFFFFF", "#1E293B"],
  "illustrationStyle": "flat vector, isometric 3D",
  "typography": "bold geometric sans-serif",
  "lighting": "soft diffused studio lighting",
  "mood": ["professional", "trustworthy", "modern"],
  "defaults": {
    "aspectRatio": "16:9",
    "resolution": "2K",
    "model": "gemini-3.1-flash-image-preview"
  }
}
```

## Built-in Presets

### tech-saas
Professional aesthetics with minimalist design.
- **Palette:** Blue (#2563EB), White (#FFFFFF), Slate (#1E293B)
- **Style:** Flat vector illustrations, glassmorphism, geometric sans-serif
- **Mood:** Trustworthy, professional, clean
- **Defaults:** 16:9, 1K, Nano Banana 2

### luxury-brand
Sophisticated visual language establishing exclusivity.
- **Palette:** Black (#0A0A0A), Gold (#C9A84C), Cream (#F5F0E8)
- **Style:** Rich photographic textures, elegant serif typography
- **Mood:** Exclusive, aspirational, refined
- **Defaults:** 4:5, 2K, Nano Banana 2

### editorial-magazine
Bold visual impact for contemporary editorial work.
- **Palette:** Red (#E63946), Black (#1A1A1A), White (#FFFFFF)
- **Style:** Strong geometric composition, condensed headlines
- **Mood:** Bold, contemporary, impactful
- **Defaults:** 3:2, 2K, Nano Banana 2

## Preset Commands

```bash
# List all presets
python3 skills/banana/scripts/presets.py list

# Show preset details
python3 skills/banana/scripts/presets.py show tech-saas

# Create preset interactively
python3 skills/banana/scripts/presets.py create my-brand

# Remove preset
python3 skills/banana/scripts/presets.py remove my-brand
```

## How Presets Work

When a preset is loaded, its values become the defaults for subsequent
generations. User instructions always override preset values.

The preset is applied to the Reasoning Brief as style foundation:
- Color descriptions are drawn from the palette
- Style anchors come from the illustrationStyle field
- Aspect ratio and resolution defaults are applied automatically
- Mood descriptors influence the overall tone of crafted prompts
