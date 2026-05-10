# psycho

## Objective

Build a repeatable AI-assisted production system for psychology education YouTube videos.

The channel format is slideshow video: static illustrated frames, Ken Burns movement, calm narration, no traditional animation.

## Audience

Adults 25-45 who identify as introverted, emotionally perceptive, socially selective, intellectually curious, and "different" without having language for it.

Core emotional promise:

> Someone sees me, and what they see is not a defect.

## External Folders

- `D:\Development\SileroTTS` - main production pipeline and GUI.
- `D:\Windows folders\Desktop\youtube` - episodes, generated assets, scripts, audio, video.
- `D:\Work\Active\Content-AI` - shortcut hub.

## Current Production System

`SileroTTS / Yellow Sweater Pipeline` is the active toolchain:

- structured script ingestion
- visual architecture
- frame direction
- Imagen/Gemini image generation
- upscaling
- Ken Burns segments
- Gemini/Kokoro TTS
- Faster-Whisper timing
- API key management
- GUI tabs for production steps

## Core Notes

- [[_Psycho logic]]
- [[prompts/CHANNEL CONTEXT BRIEF — AI AGENT REFERENCE]]
- [[prompts/CHANNEL STYLE BRIEF]]
- [[Описание персонажа для генерации]]
- [[archive/Мастер-промпт]]

## Prompt System

- [[prompts/master prompt script writer]]
- [[prompts/v3 scriptwriter]]
- [[prompts/codex_topic selector]]
- [[prompts/codex_script writer]]
- [[prompts/codex_report generator]]
- [[prompts/top 20 scripts analysis + maste prompt]]
- [[prompts/визуал советы]]

## Current Open Work

- [ ] include pauses into scene timing
- [ ] music and sound generation
- [ ] auto post-processing
- [ ] upload upscale flow
- [ ] script text directly in app
- [ ] in-app image prompt maker
- [ ] thumbnail generator
- [ ] improve thumbnail readability and CTR workflow

## Decisions

- Yellow sweater character is the stable identity marker.
- Character stays simple and featureless for viewer projection.
- Backgrounds carry emotional context; character carries readable emotional state.
- Ken Burns movement means every frame must be compositionally safe for crop/zoom.
- Raw AI output should not become final notes without compression.

## Risks

- Too many prompt variants can create contradiction.
- Generated assets and final assets are mixed across folders.
- Some paths are hardcoded around `D:\Windows folders\Desktop\youtube\episodes`.
- Pipeline complexity is growing; each new feature should connect to the production sequence, not become an isolated experiment.

## Best AI Commands

```text
Read Projects/psycho and D:\Development\SileroTTS docs. Update this INDEX with stale files, active files, and next actions.
```

```text
Compare CHANNEL STYLE BRIEF, CHANNEL CONTEXT BRIEF, and v3 scriptwriter. Find contradictions and propose one canonical prompt hierarchy.
```

