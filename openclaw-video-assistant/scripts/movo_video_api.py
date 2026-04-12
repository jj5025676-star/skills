#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_BASE_URL = os.environ.get("MOVO_API_BASE_URL", "https://mtapi.1movo.com").rstrip("/")
DEFAULT_API_KEY_ENV = "MOVO_API_KEY"
DEFAULT_DOWNLOAD_MIN_BYTES = 1024
VIDEO_CONTENT_TYPE_PREFIXES = ("video/", "application/octet-stream")
VIDEO_CONTENT_TYPE_HINTS = ("mp4", "mpeg", "quicktime", "octet-stream")

TEMPLATE_SUBMIT_URL = f"{DEFAULT_BASE_URL}/v1/videos"
TEMPLATE_POLL_URL = f"{DEFAULT_BASE_URL}/v1/videos/search/{{identifier}}"
VEO_SUBMIT_URL = f"{DEFAULT_BASE_URL}/v1/llms/video"
VEO_POLL_URL = f"{DEFAULT_BASE_URL}/v1/llms/search/video/{{identifier}}"
DEFAULT_POLL_INTERVAL = 60

SERVICE_ID_MAP = {
    "veo3.1-fast": "llm-veo31-fast",
    "veo3.1": "llm-veo31",
    "veo3.1-fl": "llm-veo31-fl",
    "veo3.1-fast-fl": "llm-veo31-fast-fl",
}

TEMPLATE_TERMINAL = {"success", "failed", "error", "cancelled"}
VEO_TERMINAL = {"completed", "failed", "error", "cancelled"}


def normalize_service_id(service_id: str) -> str:
    return SERVICE_ID_MAP.get(service_id, service_id)


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


def resolve_api_key(args: argparse.Namespace) -> str:
    direct = getattr(args, "api_key", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    env_name = getattr(args, "api_key_env", DEFAULT_API_KEY_ENV) or DEFAULT_API_KEY_ENV
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        return env_value
    raise ValueError(
        f"Movo API key is required. Set --api-key, or export {env_name} in the environment."
    )


def make_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "X-Movo-API-Key": api_key,
            "Content-Type": "application/json",
        }
    )
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def fail_json(message: str, **extra: object) -> int:
    payload = {"ok": False, "error": message}
    payload.update(extra)
    print_json(payload)
    return 1


def normalize_payload_error(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("error", "message", "msg", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("error", "message", "msg", "detail"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def payload_business_ok(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    code = payload.get("code")
    if isinstance(code, int) and code != 0:
        return False
    success = payload.get("success")
    if isinstance(success, bool) and not success:
        return False
    ok = payload.get("ok")
    if isinstance(ok, bool) and not ok:
        return False
    return True


def validate_template_inputs(service_id: str, images: list[str], input_texts: list[str]) -> None:
    expected_images = {
        "vid-ad-basic": 1,
        "vid-ad-story-24s": 2,
        "vid-operation-9x16": 2,
        "vid-talk-9x16": 2,
    }
    expected = expected_images.get(service_id)
    if expected is not None and len(images) != expected:
        raise ValueError(f"{service_id} requires exactly {expected} image(s); got {len(images)}")
    if len(input_texts) < 3:
        raise ValueError(
            "template mode requires at least 3 input_text values: segment_count, brand_name, product_info"
        )
    segment_count_raw = input_texts[0]
    if not re.fullmatch(r"\d+", segment_count_raw):
        raise ValueError(f"segment_count must be an integer string; got {segment_count_raw!r}")
    segment_count = int(segment_count_raw)
    if service_id in {"vid-ad-basic", "vid-ad-story-24s"} and segment_count < 2:
        raise ValueError(f"{service_id} requires segment_count >= 2; got {segment_count}")
    if service_id == "vid-operation-9x16" and segment_count not in {2, 3}:
        raise ValueError("vid-operation-9x16 requires segment_count to be 2 or 3")
    if service_id == "vid-talk-9x16" and segment_count not in {1, 2, 3}:
        raise ValueError("vid-talk-9x16 requires segment_count to be 1, 2, or 3")


def validate_veo_inputs(service_id: str, images: list[str]) -> None:
    if service_id.endswith("-fl"):
        if len(images) not in {1, 2}:
            raise ValueError(
                f"{service_id} requires 1 image (first-frame) or 2 images (first-plus-last-frame); got {len(images)}"
            )
        return
    if len(images) > 6:
        raise ValueError(f"{service_id} supports at most 6 reference images; got {len(images)}")


def response_payload(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {"http_status": resp.status_code, "text": resp.text}


def request_with_fallback(
    session: requests.Session,
    method: str,
    url: str,
    *,
    body: dict | None = None,
    timeout: int,
) -> tuple[int, dict, str]:
    try:
        if method == "POST":
            resp = session.post(url, json=body, timeout=timeout)
        else:
            resp = session.get(url, timeout=timeout)
        return resp.status_code, response_payload(resp), "requests"
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as err:
        sys.stderr.write(f"{method} {url} via requests failed: {err}; falling back to curl\n")
        return request_via_curl(method, url, session.headers.get("X-Movo-API-Key", ""), body, timeout)


def request_via_curl(
    method: str,
    url: str,
    api_key: str,
    body: dict | None,
    timeout: int,
) -> tuple[int, dict, str]:
    body_file_path: str | None = None
    try:
        if body is not None:
            body_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
            with body_file:
                json.dump(body, body_file, ensure_ascii=False)
            body_file_path = body_file.name
        config_lines = [
            "silent",
            "show-error",
            f'request = "{method}"',
            f'url = "{url}"',
            'header = "Content-Type: application/json"',
            f'header = "X-Movo-API-Key: {api_key}"',
            f"max-time = {timeout}",
            'write-out = "\\n__HTTP_STATUS__:%{http_code}"',
        ]
        if body_file_path:
            escaped_body_path = body_file_path.replace("\\", "\\\\")
            config_lines.append(f'data-binary = "@{escaped_body_path}"')
        result = subprocess.run(
            ["curl", "--config", "-"],
            input="\n".join(config_lines) + "\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl fallback failed: {result.stderr.strip() or result.stdout.strip()}")
        marker = "\n__HTTP_STATUS__:"
        payload_text, _, status_text = result.stdout.rpartition(marker)
        try:
            payload = json.loads(payload_text) if payload_text else {}
        except json.JSONDecodeError:
            payload = {"text": payload_text}
        return int(status_text or 0), payload, "curl_fallback"
    finally:
        if body_file_path:
            try:
                Path(body_file_path).unlink(missing_ok=True)
            except OSError:
                pass


def build_submit_output(kind: str, request_url: str, request_body: dict | None, status: int, payload: dict, transport: str) -> dict:
    data = (payload or {}).get("data") or {}
    return {
        "kind": kind,
        "request_url": request_url,
        "request_body": request_body,
        "http_status": status,
        "ok": 200 <= status < 300,
        "transport": transport,
        "response": payload,
        "identifier": data.get("id") or data.get("conversation_id") or data.get("user_sequence_id"),
        "message_id": data.get("message_id"),
    }


def validate_submit_output(out: dict) -> tuple[bool, str | None]:
    if not out["ok"]:
        return False, normalize_payload_error(out.get("response")) or f"HTTP {out['http_status']}"
    if not payload_business_ok(out.get("response")):
        return False, normalize_payload_error(out.get("response")) or "API reported a business-level failure"
    identifier = out.get("identifier")
    if not isinstance(identifier, (str, int)) or not str(identifier).strip():
        return False, "Submit response did not include a valid task identifier"
    return True, None


def validate_poll_output(out: dict) -> tuple[bool, str | None]:
    if not out["ok"]:
        return False, normalize_payload_error(out.get("response")) or f"HTTP {out['http_status']}"
    if not payload_business_ok(out.get("response")):
        return False, normalize_payload_error(out.get("response")) or "API reported a business-level failure"
    status = out.get("status")
    if status is None or (isinstance(status, str) and not status.strip()):
        return False, "Poll response did not include a valid status"
    return True, None


def submit_template(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key(args)
        service_id = normalize_service_id(args.service_id)
        images = [normalize_image(v) for v in args.image]
        validate_template_inputs(service_id, images, args.input_text)
    except (FileNotFoundError, ValueError) as err:
        return fail_json(str(err))

    body = {
        "service_id": service_id,
        "input_image_urls": images,
        "input_texts": args.input_text,
    }
    session = make_session(api_key)
    try:
        http_status, payload, transport = request_with_fallback(
            session, "POST", TEMPLATE_SUBMIT_URL, body=body, timeout=args.timeout
        )
    except RuntimeError as err:
        return fail_json(str(err))

    out = build_submit_output(
        "template",
        TEMPLATE_SUBMIT_URL,
        body if args.show_request else None,
        http_status,
        payload,
        transport,
    )
    submit_ok, error_message = validate_submit_output(out)
    if not submit_ok:
        out["ok"] = False
        out["error"] = error_message
    print_json(out)
    return 0 if submit_ok else 1


def submit_veo(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key(args)
        service_id = normalize_service_id(args.service_id)
        images = [normalize_image(v) for v in args.image]
        validate_veo_inputs(service_id, images)
    except (FileNotFoundError, ValueError) as err:
        return fail_json(str(err))

    body = {
        "service_id": service_id,
        "size": args.size,
        "prompt": args.prompt,
    }
    if images:
        body["ref_images"] = images

    session = make_session(api_key)
    try:
        http_status, payload, transport = request_with_fallback(
            session, "POST", VEO_SUBMIT_URL, body=body, timeout=args.timeout
        )
    except RuntimeError as err:
        return fail_json(str(err))

    out = build_submit_output(
        "veo",
        VEO_SUBMIT_URL,
        body if args.show_request else None,
        http_status,
        payload,
        transport,
    )
    submit_ok, error_message = validate_submit_output(out)
    if not submit_ok:
        out["ok"] = False
        out["error"] = error_message
    print_json(out)
    return 0 if submit_ok else 1


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
    urls: list[str] = []
    data = (payload or {}).get("data")
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
        for key in ("status", "state", "conversation_status"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    for key in ("status", "state", "conversation_status"):
        value = (payload or {}).get(key)
        if isinstance(value, str):
            return value
    return None


def extract_veo_result(payload: dict) -> list[str]:
    candidates: list[str] = []
    containers: list[dict] = []
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        containers.append(data)
    containers.append(payload or {})
    for container in containers:
        messages = container.get("messages")
        if not isinstance(messages, list):
            continue
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


def poll_once(
    session: requests.Session,
    kind: str,
    identifier: str,
    timeout: int,
) -> tuple[int, dict, str]:
    url = TEMPLATE_POLL_URL.format(identifier=identifier) if kind == "template" else VEO_POLL_URL.format(identifier=identifier)
    return request_with_fallback(session, "GET", url, timeout=timeout)


def infer_output_filename(url: str, identifier: str) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix or ".mp4"
    return f"movo_result_{identifier}{suffix}"


def is_video_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    normalized = content_type.split(";", 1)[0].strip().lower()
    if any(normalized.startswith(prefix) for prefix in VIDEO_CONTENT_TYPE_PREFIXES):
        return True
    return any(hint in normalized for hint in VIDEO_CONTENT_TYPE_HINTS)


def download_result_file(url: str, identifier: str, timeout: int) -> str:
    target_dir = Path.home() / ".openclaw" / "media" / "outbound"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / infer_output_filename(url, identifier)
    fd, temp_path_raw = tempfile.mkstemp(prefix=f"{target_path.stem}_", suffix=target_path.suffix, dir=target_dir)
    os.close(fd)
    temp_path = Path(temp_path_raw)
    bytes_written = 0
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type")
            if not is_video_content_type(content_type):
                raise requests.RequestException(f"unexpected content type: {content_type or 'missing'}")
            with temp_path.open("wb") as handle:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        handle.write(chunk)
                        bytes_written += len(chunk)
        if bytes_written < DEFAULT_DOWNLOAD_MIN_BYTES:
            raise requests.RequestException(
                f"downloaded file is too small to be a valid video ({bytes_written} bytes)"
            )
        temp_path.replace(target_path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return str(target_path)


def status(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key(args)
    except ValueError as err:
        return fail_json(str(err), kind=args.kind, identifier=args.identifier)
    session = make_session(api_key)
    extractor = extract_template_status if args.kind == "template" else extract_veo_status
    result_extractor = extract_template_result if args.kind == "template" else extract_veo_result
    try:
        http_status, payload, transport = poll_once(session, args.kind, args.identifier, args.timeout)
    except RuntimeError as err:
        return fail_json(str(err), kind=args.kind, identifier=args.identifier)

    out = {
        "kind": args.kind,
        "identifier": args.identifier,
        "http_status": http_status,
        "ok": 200 <= http_status < 300,
        "transport": transport,
        "status": extractor(payload),
        "response": payload,
        "result_urls": result_extractor(payload),
        "elapsed_seconds": 0,
    }
    status_ok, error_message = validate_poll_output(out)
    if not status_ok:
        out["ok"] = False
        out["error"] = error_message
    print_json(out)
    return 0 if status_ok else 1


def poll(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key(args)
    except ValueError as err:
        return fail_json(str(err), kind=args.kind, identifier=args.identifier)
    session = make_session(api_key)
    terminal = TEMPLATE_TERMINAL if args.kind == "template" else VEO_TERMINAL
    extractor = extract_template_status if args.kind == "template" else extract_veo_status
    result_extractor = extract_template_result if args.kind == "template" else extract_veo_result
    started = time.time()

    while True:
        try:
            http_status, payload, transport = poll_once(session, args.kind, args.identifier, args.timeout)
        except RuntimeError as err:
            return fail_json(str(err), kind=args.kind, identifier=args.identifier)

        status = extractor(payload)
        elapsed = int(time.time() - started)
        result_urls = result_extractor(payload)

        out = {
            "kind": args.kind,
            "identifier": args.identifier,
            "http_status": http_status,
            "ok": 200 <= http_status < 300,
            "transport": transport,
            "status": status,
            "response": payload,
            "result_urls": result_urls,
            "elapsed_seconds": elapsed,
        }
        poll_ok, error_message = validate_poll_output(out)
        if not poll_ok:
            out["ok"] = False
            out["error"] = error_message
        print_json(out)

        if not poll_ok:
            return 1

        if status in terminal:
            if args.download and result_urls:
                try:
                    local_media = download_result_file(result_urls[0], args.identifier, args.timeout)
                    print(json.dumps({"downloaded_file": local_media}, ensure_ascii=False, indent=2), flush=True)
                except requests.RequestException as err:
                    return fail_json(
                        f"Result download failed: {err}",
                        kind=args.kind,
                        identifier=args.identifier,
                        status=status,
                        result_url=result_urls[0],
                    )
            return 0 if out["ok"] else 1

        if args.max_wait and time.time() - started >= args.max_wait:
            return fail_json(
                "Polling exceeded max wait",
                kind=args.kind,
                identifier=args.identifier,
                status=status,
                elapsed_seconds=elapsed,
            )

        time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stable Movo video submit/poll helper.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-key", help="Movo API key. Prefer using the environment instead of CLI args.")
    common.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV, help=f"Environment variable name for the Movo API key (default: {DEFAULT_API_KEY_ENV})")
    common.add_argument("--timeout", type=int, default=60)
    common.add_argument("--show-request", action="store_true")

    p_template = sub.add_parser("submit-template", parents=[common])
    p_template.add_argument("--service-id", required=True)
    p_template.add_argument(
        "--image", action="append", required=True, help="URL, data URL, or local file path"
    )
    p_template.add_argument("--input-text", action="append", required=True)
    p_template.set_defaults(func=submit_template)

    p_veo = sub.add_parser("submit-veo", parents=[common])
    p_veo.add_argument("--service-id", required=True)
    p_veo.add_argument("--size", required=True, choices=["720x1280", "1280x720"])
    p_veo.add_argument("--prompt", required=True)
    p_veo.add_argument(
        "--image", action="append", default=[], help="URL, data URL, or local file path"
    )
    p_veo.set_defaults(func=submit_veo)

    p_status = sub.add_parser("status", parents=[common])
    p_status.add_argument("--kind", required=True, choices=["template", "veo"])
    p_status.add_argument("--identifier", required=True)
    p_status.set_defaults(func=status)

    p_poll = sub.add_parser("poll", parents=[common])
    p_poll.add_argument("--kind", required=True, choices=["template", "veo"])
    p_poll.add_argument("--identifier", required=True)
    p_poll.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL)
    p_poll.add_argument("--download", action="store_true")
    p_poll.add_argument("--max-wait", type=int, default=0, help="0 means no limit")
    p_poll.set_defaults(func=poll)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
    sys.exit(main())
