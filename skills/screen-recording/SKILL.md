---
name: screen-recording
description: Use when the user wants to create a polished screen recording from a single prompt — automating browser or Mac app capture, dead-time trimming, smooth zooms, and gradient backgrounds without manual video editing.
---

# Screen Recording

## Overview

Automates polished screen recordings from a single prompt. Supports two modes — **browser** (Steel Dev) and **Mac app** (AppleScript + cliclick + ffmpeg) — with auto-detection. Both feed into **Remotion** for post-processing: dead time is cut, clips are merged or split, zooms are keyframed, and gradient backgrounds are applied.

## Prerequisites

### Shared
- **Remotion** — code-based video editor (processes moments + MP4 into final output)
- Install Remotion: `npx create-video@latest` inside your video project

### Browser Mode
- **Steel Dev** — headless browser that records the session and emits `moments.json`
- Install Steel: `npm install steel-sdk` (or `pip install steel-python`)

### Mac App Mode
- **ffmpeg** — screen capture via avfoundation: `brew install ffmpeg`
- **cliclick** — CLI mouse/keyboard automation: `brew install cliclick`
- **macOS Accessibility permissions** — required for cliclick (System Settings → Privacy & Security → Accessibility)

## When to Use

- User asks: "record this flow", "make a screen recording of X", "demo this feature"
- Recording a browser-based app OR a native Mac application
- Replacing Screen Studio, Loom, or similar subscription tools
- Embedding demo videos in threads, docs, or launch posts

## Mode Auto-Detection

The skill automatically picks the right pipeline based on the prompt:

| Prompt contains | Mode | Pipeline |
|---|---|---|
| URL (e.g. `https://...`, `localhost:...`) | **Browser** | Steel Dev → Remotion |
| App name (e.g. "Finder", "Notes", "Figma") | **Mac App** | ffmpeg + AppleScript + cliclick → Remotion |

No flags needed — the user just describes what to record.

## Architecture

```
Prompt (auto-detect: URL → browser | app name → mac-app)
  │
  ├── [Browser Mode] Steel Dev
  │     ├── records browser session → raw.mp4
  │     └── emits moments.json
  │
  ├── [Mac App Mode]
  │     ├── ffmpeg -f avfoundation → raw.mp4 (capture window or full screen)
  │     ├── AppleScript launches & interacts with target app
  │     ├── cliclick executes mouse/keyboard actions
  │     └── action logger emits moments.json (timestamps + coordinates)
  │
  └── Remotion (shared pipeline)
        ├── reads moments.json + raw.mp4
        ├── trims / merges / splits clips
        ├── builds zoom keyframes
        └── renders → polished.mp4
```

---

## Browser Mode — Steps

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

---

## Mac App Mode — Steps

| Step | What Happens |
|------|-------------|
| 1 | Write prompt describing the app and flow to record |
| 2 | **Launch app** — `osascript -e 'tell application "AppName" to activate'` |
| 3 | **Get window info** — `osascript` to get window bounds for targeted capture |
| 4 | **Start capture** — `ffmpeg -f avfoundation -i "<device>:none" -r 30 -vf "crop=W:H:X:Y" raw.mp4` (background process) |
| 5 | **Execute actions** — AppleScript commands + `cliclick` calls drive the app |
| 6 | **Log moments** — each action is logged to `moments.json` with `Date.now()` timestamp, x/y coordinates, and action type |
| 7 | **Stop capture** — send SIGINT to ffmpeg background process |
| 8 | **Trim dead time** — start each clip 500ms before action, end 1s after |
| 9 | **Merge clips** — if gap between clips < 2s, merge into one |
| 10 | **Split gaps** — if gap > 3s, cut into separate clips |
| 11 | **Build camera keyframes** — smooth zoom-in/out around each action area |
| 12 | **Apply gradient background** — fills letterbox areas around app window |
| 13 | Pass clips + keyframes to Remotion composition |
| 14 | Remotion renders final polished MP4 |

### Mac App Interaction Commands

**Launching and focusing apps:**
```bash
# Launch and bring to front
osascript -e 'tell application "Notes" to activate'

# Get window position and size for ffmpeg crop
osascript -e 'tell application "System Events" to tell process "Notes" to get {position, size} of window 1'
```

**Mouse and keyboard via cliclick:**
```bash
# Click at coordinates
cliclick c:640,400

# Double-click
cliclick dc:640,400

# Type text
cliclick t:"hello world"

# Keystroke (cmd+s)
cliclick kp:cmd-s

# Move mouse
cliclick m:640,400

# Click and drag
cliclick dd:100,100 du:300,300
```

**Logging moments from cliclick actions:**
```bash
# Wrapper pattern: log timestamp + action, then execute
TIMESTAMP=$(date +%s%3N)
echo "{\"timestamp\": $TIMESTAMP, \"type\": \"click\", \"x\": 640, \"y\": 400, \"label\": \"Save button\"}" >> moments.jsonl
cliclick c:640,400
```

### ffmpeg Capture Commands

```bash
# List available avfoundation devices
ffmpeg -f avfoundation -list_devices true -i ""

# Capture full screen (device index 1 is typically the main display)
ffmpeg -f avfoundation -framerate 30 -i "1:none" -c:v libx264 -pix_fmt yuv420p raw.mp4

# Capture with crop (specific window area)
ffmpeg -f avfoundation -framerate 30 -i "1:none" -vf "crop=1200:800:100:50" -c:v libx264 -pix_fmt yuv420p raw.mp4

# Stop recording: send SIGINT to the ffmpeg process
kill -INT $FFMPEG_PID
```

---

## Shared: Key Timing Constants

```js
const CLIP_START_OFFSET_MS = 500;   // start clip before action
const CLIP_END_OFFSET_MS   = 1000;  // end clip after action
const MERGE_GAP_THRESHOLD  = 2000;  // merge clips closer than 2s
const SPLIT_GAP_THRESHOLD  = 3000;  // split into new clip if gap > 3s
```

## Shared: moments.json Schema

Both modes produce the same format:

```json
[
  { "timestamp": 1234, "type": "click", "x": 640, "y": 400, "label": "Submit button" },
  { "timestamp": 2890, "type": "scroll", "x": 0, "y": 300 },
  { "timestamp": 5120, "type": "keystroke", "value": "cmd+s" },
  { "timestamp": 7800, "type": "type", "value": "hello world" }
]
```

## Shared: Remotion Integration

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

---

## Installation in Claude Code

1. Add the skill to `.claude/skills/screen-recording/SKILL.md`
2. For browser mode: ensure Steel Dev and Remotion are in the project's dependencies
3. For Mac app mode: `brew install ffmpeg cliclick` and grant Accessibility permissions
4. Invoke: "Create a screen recording of [URL or App] showing [flow]"

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
| cliclick "not permitted" | Grant Accessibility permission in System Settings → Privacy & Security |
| ffmpeg "no device found" | Run `ffmpeg -f avfoundation -list_devices true -i ""` to find correct device index |
| App window not captured fully | Use `osascript` to get exact window bounds, pass to ffmpeg crop filter |
| Moments timestamps drift from video | Start moment logging AFTER ffmpeg confirms capture has begun |
