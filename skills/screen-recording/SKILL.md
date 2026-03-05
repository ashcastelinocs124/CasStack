---
name: screen-recording
description: Use when the user wants to create a polished screen recording from a single prompt — automating browser capture, dead-time trimming, smooth zooms, and gradient backgrounds without manual video editing.
---

# Screen Recording

## Overview

Automates polished screen recordings from a single prompt using **Steel Dev** (browser automation + raw capture) and **Remotion** (code-based video editor). Eliminates manual editing: dead time is cut automatically, clips are merged or split, zooms are keyframed, and gradient backgrounds are applied.

## Prerequisites

- **Steel Dev** — headless browser that records the session and emits `moments.json`
- **Remotion** — code-based video editor (processes moments + MP4 into final output)
- Install Steel: `npm install steel-sdk` (or `pip install steel-python`)
- Install Remotion: `npx create-video@latest` inside your video project

## When to Use

- User asks: "record this flow", "make a screen recording of X", "demo this feature"
- Replacing Screen Studio, Loom, or similar subscription tools
- Embedding demo videos in threads, docs, or launch posts

## Architecture

```
Prompt
  └── Steel Dev
        ├── records browser session → raw.mp4
        └── emits moments.json (timestamped actions)
  └── Remotion
        ├── reads moments.json + raw.mp4
        ├── trims / merges / splits clips
        ├── builds zoom keyframes
        └── renders → polished.mp4
```

## 11-Step Process

| Step | What Happens |
|------|-------------|
| 1 | Write prompt describing the flow to record |
| 2 | Steel Dev opens browser, executes actions |
| 3 | Steel records raw MP4 of entire session |
| 4 | Steel emits `moments.json` — each action with timestamp |
| 5 | **Trim dead time** — start each clip 500ms before action, end 1s after |
| 6 | **Merge clips** — if gap between clips < 2s, merge into one |
| 7 | **Split gaps** — if gap > 3s, cut into separate clips |
| 8 | **Build camera keyframes** — smooth zoom-in/out around each action area |
| 9 | **Apply gradient background** — fills letterbox areas around browser window |
| 10 | Pass clips + keyframes to Remotion composition |
| 11 | Remotion renders final polished MP4 |

## Key Timing Constants

```js
const CLIP_START_OFFSET_MS = 500;   // start clip before action
const CLIP_END_OFFSET_MS   = 1000;  // end clip after action
const MERGE_GAP_THRESHOLD  = 2000;  // merge clips closer than 2s
const SPLIT_GAP_THRESHOLD  = 3000;  // split into new clip if gap > 3s
```

## moments.json Shape

```json
[
  { "timestamp": 1234, "type": "click", "x": 640, "y": 400, "label": "Submit button" },
  { "timestamp": 2890, "type": "scroll", "x": 0,   "y": 300 },
  { "timestamp": 5120, "type": "type",  "value": "hello world" }
]
```

## Remotion Integration (minimal)

```ts
// composition.tsx
import { useCurrentFrame, interpolate, Video } from 'remotion';

export const Recording: React.FC<{ moments: Moment[]; src: string }> = ({ moments, src }) => {
  const frame = useCurrentFrame();
  const zoom = buildZoom(moments, frame); // keyframes from moments
  return (
    <div style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <Video src={src} style={{ transform: `scale(${zoom})` }} />
    </div>
  );
};
```

## Installation in Claude Code

1. Add the skill to `.claude/skills/screen-recording/SKILL.md`
2. Ensure Steel Dev and Remotion are in the project's dependencies
3. Invoke: "Create a screen recording of [URL] showing [flow]"

## Combining with Other Skills

This skill composes well with:
- `linkedin-post` — embed the rendered video in a LinkedIn post
- `landing-page` — drop demo video into hero section
- `frontend-design` — record a component interaction as a demo

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Clips start too early / abrupt | `CLIP_START_OFFSET_MS` too small — increase to 500–800ms |
| Too many cuts / choppy | `MERGE_GAP_THRESHOLD` too small — increase to 2000–3000ms |
| Single long video, no pauses cut | `SPLIT_GAP_THRESHOLD` too large — decrease to 2000–3000ms |
| Zoom feels jerky | Reduce keyframe density; use easing (e.g. `spring()` in Remotion) |
| Background shows browser chrome | Set browser viewport to match Remotion canvas; hide scrollbars |
