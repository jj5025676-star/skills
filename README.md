# skills

This repository stores multiple local OpenClaw/Codex skills.

Each top-level skill directory should normally contain:

- `SKILL.md`
- `scripts/`
- `agents/` (optional)
- `references/` (optional)

## Current skills

- [add-feishu-bot-agent-skill](./add-feishu-bot-agent-skill)
  - Add a new Feishu bot account into OpenClaw and bind it to a dedicated agent/workspace.
- [install-openclaw-video-assistant](./install-openclaw-video-assistant)
  - Install the `openclaw-video-assistant` package into the current OpenClaw workspace and register a `video-agent`.
- [openclaw-video-assistant](./openclaw-video-assistant)
  - The active `movo-video-generator` skill synchronized from the local bot4 workspace.

## Usage principles

- Prefer installing skills into the current chat page's workspace `skills/` directory.
- Do not default to global installation.
- Keep management skills in a trusted admin workspace whenever possible.

## Suggested structure

```text
skills/
├─ README.md
├─ .gitignore
├─ add-feishu-bot-agent-skill/
├─ install-openclaw-video-assistant/
└─ openclaw-video-assistant/
```
