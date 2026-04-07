#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests


TEMPLATE_SUBMIT_URL = "https://mtapi.movoai.top/v1/videos"
TEMPLATE_POLL_URL = "https://mtapi.movoai.top/v1/videos/search/{identifier}"
VEO_SUBMIT_URL = "https://mtapi.movoai.top/v1/llms/video"
VEO_POLL_URL = "https://mtapi.movoai.top/v1/llms/search/video/{identifier}"

TEMPLATE_TERMINAL = {"success", "failed", "error", "cancelled"}
VEO_TERMINAL = {"completed", "failed", "error", "cancelled"}


def is_probably_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:"))


def path_to_data_url(path_str: str) -> str:
    path = Path(path_str).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Local file not found: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        mime = "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def normalize_image(value: str) -> str:
    return value if is_probably_url(value) else path_to_data_url(value)


def make_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "X-Movo-API-Key": api_key,
            "Content-Type": "application/json",
        }
    )
    return session


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def response_payload(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {
            "http_status": resp.status_code,
            "text": resp.text,
        }


def submit_template(args: argparse.Namespace) -> int:
    images = [normalize_image(v) for v in args.image]
    body = {
        "service_id": args.service_id,
        "input_image_urls": images,
        "input_texts": args.input_text,
    }
    session = make_session(args.api_key)
    resp = session.post(TEMPLATE_SUBMIT_URL, json=body, timeout=args.timeout)
    payload = response_payload(resp)
    out = {
        "kind": "template",
        "request_url": TEMPLATE_SUBMIT_URL,
        "request_body": body if args.show_request else None,
        "http_status": resp.status_code,
        "ok": resp.ok,
        "response": payload,
        "identifier": (((payload or {}).get("data") or {}).get("id")),
    }
    print_json(out)
    return 0 if resp.ok else 1


def veo_preferred_body(args: argparse.Namespace, images: list[str]) -> dict:
    body = {
        "service_id": args.service_id,
        "size": args.size,
        "messages": [{"role": "user", "content": args.prompt}],
    }
    if images:
        body["ref_images"] = images
    return body


def veo_compatibility_body(args: argparse.Namespace, images: list[str]) -> dict:
    body = {
        "service_id": args.service_id,
        "size": args.size,
        "input_texts": [args.prompt],
    }
    if images:
        body["input_image_urls"] = images
    return body


def submit_veo(args: argparse.Namespace) -> int:
    images = [normalize_image(v) for v in args.image]
    session = make_session(args.api_key)
    first_body = veo_preferred_body(args, images)
    resp = session.post(VEO_SUBMIT_URL, json=first_body, timeout=args.timeout)
    payload = response_payload(resp)

    retried = False
    if not resp.ok and args.retry_compat:
        error_text = json.dumps(payload, ensure_ascii=False)
        if "messages" in error_text or "ref_images" in error_text or "validation" in error_text.lower():
            retried = True
            second_body = veo_compatibility_body(args, images)
            resp = session.post(VEO_SUBMIT_URL, json=second_body, timeout=args.timeout)
            payload = response_payload(resp)
            request_body = second_body
        else:
            request_body = first_body
    else:
        request_body = first_body

    data = (payload or {}).get("data") or {}
    identifier = data.get("conversation_id") or data.get("user_sequence_id")
    out = {
        "kind": "veo",
        "request_url": VEO_SUBMIT_URL,
        "request_body": request_body if args.show_request else None,
        "http_status": resp.status_code,
        "ok": resp.ok,
        "retried_with_compatibility_body": retried,
        "response": payload,
        "identifier": identifier,
        "message_id": data.get("message_id"),
    }
    print_json(out)
    return 0 if resp.ok else 1


def extract_template_status(payload: dict) -> str | None:
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        for key in ("status", "task_status", "state"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    for key in ("status", "task_status", "state"):
        value = (payload or {}).get(key)
        if isinstance(value, str):
            return value
    return None


def extract_template_result(payload: dict) -> list[str]:
    data = (payload or {}).get("data")
    urls = []
    if isinstance(data, dict):
        value = data.get("output_video_urls")
        if isinstance(value, list):
            urls.extend([v for v in value if isinstance(v, str)])
    value = (payload or {}).get("output_video_urls")
    if isinstance(value, list):
        urls.extend([v for v in value if isinstance(v, str)])
    return urls


def extract_veo_status(payload: dict) -> str | None:
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        for key in ("status", "state"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    for key in ("status", "state"):
        value = (payload or {}).get(key)
        if isinstance(value, str):
            return value
    return None


def extract_veo_result(payload: dict) -> list[str]:
    candidates = []
    containers = []
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        containers.append(data)
    containers.append(payload or {})
    for container in containers:
        messages = container.get("messages")
        if isinstance(messages, list):
            for item in messages:
                if not isinstance(item, dict):
                    continue
                video = item.get("video")
                if isinstance(video, dict) and isinstance(video.get("url"), str):
                    candidates.append(video["url"])
                for key in ("video_url", "url"):
                    value = item.get(key)
                    if isinstance(value, str) and value.startswith("http"):
                        candidates.append(value)
    return candidates


def poll_once(session: requests.Session, kind: str, identifier: str, timeout: int) -> tuple[requests.Response, dict]:
    if kind == "template":
        url = TEMPLATE_POLL_URL.format(identifier=identifier)
    else:
        url = VEO_POLL_URL.format(identifier=identifier)
    resp = session.get(url, timeout=timeout)
    return resp, response_payload(resp)


def poll(args: argparse.Namespace) -> int:
    session = make_session(args.api_key)
    terminal = TEMPLATE_TERMINAL if args.kind == "template" else VEO_TERMINAL
    extractor = extract_template_status if args.kind == "template" else extract_veo_status
    result_extractor = extract_template_result if args.kind == "template" else extract_veo_result
    started = time.time()

    while True:
        resp, payload = poll_once(session, args.kind, args.identifier, args.timeout)
        status = extractor(payload)
        out = {
            "kind": args.kind,
            "identifier": args.identifier,
            "http_status": resp.status_code,
            "ok": resp.ok,
            "status": status,
            "response": payload,
            "result_urls": result_extractor(payload),
            "elapsed_seconds": int(time.time() - started),
        }
        print_json(out)

        if not args.watch:
            return 0 if resp.ok else 1
        if status in terminal:
            return 0 if resp.ok else 1
        if args.max_wait and time.time() - started >= args.max_wait:
            return 2
        time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stable Movo video submit/poll helper.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-key", required=True)
    common.add_argument("--timeout", type=int, default=60)
    common.add_argument("--show-request", action="store_true")

    p_template = sub.add_parser("submit-template", parents=[common])
    p_template.add_argument("--service-id", required=True)
    p_template.add_argument("--image", action="append", required=True, help="URL, data URL, or local file path")
    p_template.add_argument("--input-text", action="append", required=True)
    p_template.set_defaults(func=submit_template)

    p_veo = sub.add_parser("submit-veo", parents=[common])
    p_veo.add_argument("--service-id", required=True)
    p_veo.add_argument("--size", required=True, choices=["720x1280", "1280x720"])
    p_veo.add_argument("--prompt", required=True)
    p_veo.add_argument("--image", action="append", default=[], help="URL, data URL, or local file path")
    p_veo.add_argument("--retry-compat", action="store_true", default=True)
    p_veo.set_defaults(func=submit_veo)

    p_poll = sub.add_parser("poll", parents=[common])
    p_poll.add_argument("--kind", required=True, choices=["template", "veo"])
    p_poll.add_argument("--identifier", required=True)
    p_poll.add_argument("--watch", action="store_true")
    p_poll.add_argument("--interval", type=int, default=60)
    p_poll.add_argument("--max-wait", type=int, default=0, help="0 means no limit")
    p_poll.set_defaults(func=poll)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
