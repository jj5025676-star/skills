# Movo Request Reference

Read this file before assembling any request body for the live Movo APIs.

## Shared headers

All direct requests use:

```text
X-Movo-API-Key: <key>
Content-Type: application/json
```

## Template video requests

Template submit endpoint:

```text
POST https://mtapi.1movo.com/v1/videos
```

Template poll endpoint:

```text
GET https://mtapi.1movo.com/v1/videos/search/{id}
```

Observed request shape for template-style video creation is:

```json
{
  "service_id": "vid-ad-basic",
  "input_image_urls": [
    "data:image/png;base64,..."
  ],
  "input_texts": [
    "2",
    "Brand name",
    "Product info"
  ]
}
```

Use these field rules:

- `service_id`: one of the template ids.
- `input_image_urls`: array of image URLs or `data:image/...;base64,...` strings.
- `input_texts[0]`: segment count or number of 8-second clips.
- remaining `input_texts`: template-specific business inputs in the documented order.

Template-specific constraints:

- `vid-ad-basic`
  - images: exactly 1 product image
  - `input_texts`: `[segment_count, brand_name, product_info]`
  - `segment_count >= 2`
- `vid-ad-story-24s`
  - images: product image + person image
  - `input_texts`: `[segment_count, brand_name, product_info]`
  - `segment_count >= 2`
- `vid-operation-9x16`
  - images: product image + person image
  - `input_texts`: `[segment_count, brand_name, product_info]`
  - `segment_count` must be `2` or `3`
- `vid-talk-9x16`
  - images: product image + person image
  - `input_texts`: `[segment_count, brand_name, product_info]`
  - `segment_count` must be `1`, `2`, or `3`

## veo3.1 requests

veo submit endpoint:

```text
POST https://mtapi.1movo.com/v1/llms/video
```

veo poll endpoint:

```text
GET https://mtapi.1movo.com/v1/llms/search/video/{conversation_id}
```

### Live body

Current live API accepts this body for `/v1/llms/video`:

```json
{
  "service_id": "llm-veo31-fast",
  "size": "720x1280",
  "prompt": "Create a 9:16 product video with soft camera motion.",
  "ref_images": [
    "data:image/png;base64,..."
  ]
}
```

Field rules:

- `service_id`: one of `llm-veo31-fast`, `llm-veo31-fast-fl`, `llm-veo31`, `llm-veo31-fl`
- `size`: `720x1280` or `1280x720`
- `prompt`: the full user prompt string
- `ref_images`: optional string array

Reference-image limits:

- normal text/image-to-video: up to 6 images
- first-frame mode: 1 image
- first-plus-last-frame mode: 2 images

Observed note:

- live tests now reject `messages` and `input_texts` for this endpoint with an error equivalent to `prompt cannot be empty`
- use `prompt` as the source of truth unless the vendor documents a breaking change

## Local image handling

When the user gives a local image path:

1. read the file bytes
2. base64-encode them
3. build a `data:image/<ext>;base64,...` string
4. place that string into `input_image_urls` or `ref_images`

Do not send raw filesystem paths to the API.

## Response handling

### Template submit

Prefer these fields after submit:

```json
{
  "data": {
    "id": "123"
  }
}
```

Poll until one of:

- `success`
- `failed`
- `error`
- `cancelled`

On success, extract `output_video_urls`.

### veo submit

Prefer these fields after submit:

```json
{
  "data": {
    "message_id": 596,
    "user_sequence_id": 13,
    "conversation_id": 13
  }
}
```

Identifier priority:

1. `data.conversation_id`
2. `data.user_sequence_id` only if `conversation_id` is missing

Poll until one of:

- `completed`
- `failed`
- `error`
- `cancelled`

On success, first try:

- `messages[*].video.url`

If the live payload uses another obviously equivalent video-url field, use the real field and mention which field appeared.

## Confirmation pattern

Use this before submission:

```text
我理解你的需求是：<一句话总结>。我建议使用：<模式名> / <service_id>。请确认，我再执行。
```

## Failure handling

- `524 Origin Time-out`
  - treat as submit-time timeout
  - explain it and offer one retry
- `404` while polling
  - first verify the endpoint family and identifier type
- schema validation failure
  - for veo requests, do not invent alternate field names
  - return the exact API error instead of guessing a new schema
