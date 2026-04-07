# openclaw-video-assistant

This repository is now a single OpenClaw skill repository.

The skill content is kept in sync with the version currently used by bot4 in the local OpenClaw workspace:

- Active local source:
  - `D:\openclaw_workspace_bot4\skills\movo-video-generator`

## What is included

- [SKILL.md](./SKILL.md)
- [agents/openai.yaml](./agents/openai.yaml)
- [references/movo-request-reference.md](./references/movo-request-reference.md)
- [scripts/movo_video_api.py](./scripts/movo_video_api.py)

## What this skill does

`movo-video-generator` submits Movo template-video and veo3.1 video jobs, then polls until completion using the bundled Python helper instead of long inline `curl` commands.

It supports:

- template video modes such as `vid-ad-basic`, `vid-ad-story-24s`, `vid-operation-9x16`, `vid-talk-9x16`
- veo3.1 modes such as `llm-veo31-fast`, `llm-veo31-fast-fl`, `llm-veo31`, `llm-veo31-fl`
- stable polling through `scripts/movo_video_api.py`

## Recommended installation

Install this skill into the current OpenClaw workspace's `skills` directory, not as a global system skill.

Example target:

```text
<current-workspace>/skills/movo-video-generator
```

## Notes

- This repository no longer ships the old workspace wrapper files or installer scripts.
- The repository is intentionally aligned to the skill currently used in OpenClaw, not to the earlier `video-agent` workspace package layout.
