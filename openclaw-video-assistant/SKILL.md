---
name: movo-video-generator
description: Generate videos with Movo template-video APIs and veo3.1 APIs from prompts or reference images. Use when the user wants to turn text, product photos, character images, or first/last-frame references into a video and needs the assistant to choose the right Movo mode, confirm before execution, submit the real request, poll until completion, and return the real result URL or failure.
---

# Movo Video Generator

Use this skill as a self-contained package. Do not depend on AGENTS.md, SOUL.md, TOOLS.md, or other workspace files.

Before building any live request body, read `references/movo-request-reference.md`. Do not guess field names or payload shapes from memory.

## Operating rules

- Understand the request, choose the right mode, confirm once, then execute.
- Never invent task ids, statuses, result URLs, or successful completion.
- Never hardcode a real API key into files. Read `X-Movo-API-Key` from the current turn or ask for it.
- If the API key is missing, ask only for the key.
- Prefer real delivery over abstract advice. If execution is blocked, say exactly why.
- Restore protocol accuracy before brevity. When a request involves payload assembly, polling fields, or result extraction, consult the bundled reference file first.

## Modes

Template video modes:

- `vid-ad-basic`: product-only ad video.
- `vid-ad-story-24s`: ad-story video with product plus person.
- `vid-operation-9x16`: operation or explainer video with product plus person.
- `vid-talk-9x16`: straight presenter or talk-to-camera video.

veo3.1 modes:

- `llm-veo31-fast`: default text-to-video or image-to-video.
- `llm-veo31-fast-fl`: first-frame or first-plus-last-frame controlled video.
- `llm-veo31`: slower higher-quality text-to-video or image-to-video.
- `llm-veo31-fl`: slower higher-quality first-frame or first-plus-last-frame controlled video.

## Choose the mode

- Use a template mode when the user clearly wants a packaged ad or presenter format.
- Use a veo mode when the user wants freer prompt-led generation, more cinematic control, or explicit reference-image control.
- Use a fast veo variant by default.
- Upgrade from fast to non-fast only when the user explicitly prefers quality over speed.
- Use an `-fl` mode only when the user explicitly wants the opening frame or both the opening and ending frames controlled.

## Confirm before execution

Before calling the API, send one short confirmation in this pattern:

```text
I understand the goal is: <one-sentence summary>. I recommend using <mode> / <service id>. Please confirm and I will run it.
```

If the request is still ambiguous, ask exactly one short follow-up question for the missing choice.

## Required inputs

Before execution, make sure you have:

- `X-Movo-API-Key`
- the chosen mode or service id
- required images as a URL or a `data:image/...;base64,...` string
- any required prompt or text fields

For veo modes, `size` must be one of:

- `720x1280`
- `1280x720`

If the user provides a local image path, read the file and convert it to a data URL before calling the API, or ask the user for a reachable URL if local file access is not available.

## HTTP rules

Send every request with:

- `X-Movo-API-Key: <key>`
- `Content-Type: application/json`

Template video endpoints:

- submit: `POST https://mtapi.movoai.top/v1/videos`
- poll: `GET https://mtapi.movoai.top/v1/videos/search/{id}`

veo3.1 endpoints:

- submit: `POST https://mtapi.movoai.top/v1/llms/video`
- poll: `GET https://mtapi.movoai.top/v1/llms/search/video/{conversation_id}`

Prefer the bundled Python helper instead of assembling long `curl` commands in chat:

```bash
python {baseDir}/scripts/movo_video_api.py submit-template ...
python {baseDir}/scripts/movo_video_api.py submit-veo ...
python {baseDir}/scripts/movo_video_api.py poll --kind template --identifier 31 --watch
python {baseDir}/scripts/movo_video_api.py poll --kind veo --identifier 123 --watch
```

Use the request-body patterns from `references/movo-request-reference.md`. If a live response indicates a schema mismatch, let the Python helper retry with the documented compatibility body instead of inventing a third shape.

## Template mode notes

- `vid-ad-basic` needs one product image.
- `vid-ad-story-24s` needs a product image and a person image.
- `vid-operation-9x16` needs a product image and a person image.
- `vid-talk-9x16` needs a product image and a person image.
- For `input_texts`, collect the fields required by the chosen template such as brand name, product info, and segment count. If the user has not given enough information, ask only for the missing fields.
- Template bodies normally use `service_id`, `input_image_urls`, and `input_texts`. Follow the exact examples in the reference file.

## veo mode notes

- Standard veo mode can use only a prompt or a prompt plus reference images.
- Standard image-to-video mode can use up to 6 reference images.
- First-frame mode uses 1 image.
- First-plus-last-frame mode uses 2 images.
- Use `720x1280` for vertical output and `1280x720` for horizontal output unless the user says otherwise.
- Prefer the `messages` plus `ref_images` body shown in the reference file for `/v1/llms/video`.
- If the live API rejects `messages` or `ref_images` with a validation error, retry once with the compatibility body that uses `input_texts` and `input_image_urls`.

## Execute and poll

After submission:

- For template modes, read `data.id` from the response.
- For veo modes, prefer `data.conversation_id`. If it is missing, fall back to `data.user_sequence_id` only as a secondary identifier.
- Poll every 60 seconds until a terminal state is reached.
- Use `scripts/movo_video_api.py poll ... --watch` for polling so long prompts or image payloads do not leak back into a giant shell command.

Template terminal states:

- `success`
- `failed`
- `error`
- `cancelled`

veo terminal states:

- `completed`
- `failed`
- `error`
- `cancelled`

Success extraction:

- Template modes: read `output_video_urls`.
- veo modes: extract from `messages[*].video.url`.
- If veo completion returns a different but obviously equivalent video field in the live response, report what the API actually returned and note the difference.

## Report format

Always report:

- selected mode and service or model id
- whether submission succeeded
- returned ids
- final status
- final video URL or exact failure reason

## Error handling

- `524 Origin Time-out`: treat this as a submit-time timeout, explain it, and offer one retry.
- `404` during polling: verify that the poll endpoint and identifier type are correct.
- failed task with no detailed reason: say the API did not return a more specific failure reason.
- shell error `Argument list too long`: stop using inline `curl` and switch to the bundled Python helper immediately.

## Important reminders

- Do not mix template polling endpoints with veo polling endpoints.
- If documentation and live behavior conflict, follow the live API behavior that actually works.
- If execution cannot complete, say so plainly instead of fabricating a result.
- The bundled reference file is part of this skill. Use it whenever body shape or field naming matters.
