#!/usr/bin/env python3
"""One-way CSharness-Docs MDX to the matching Notion pages.

Run with --dry-run to validate the source tree without an API key.
The Notion page IDs are public-doc mirror destinations, not credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "scripts" / "notion-docs-map.json"
API = "https://api.notion.com/v1"
VERSION = "2026-03-11"
REPO = "https://github.com/csharness/CSharness-Docs"


def git_blob_sha(data):
    header = b"blob " + str(len(data)).encode() + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def convert_mdx(source):
    """Keep written content, removing Mintlify-only presentation wrappers."""
    body = re.sub(r"\A---\n.*?\n---\n", "", source, count=1, flags=re.S)
    body = re.sub(r"^\s*<Step title=\"([^\"]+)\"[^>]*>\s*$", r"### \1", body, flags=re.M)
    body = re.sub(r"^\s*<Card title=\"([^\"]+)\"[^>]*>\s*$", r"### \1", body, flags=re.M)
    body = re.sub(r"^\s*<Update label=\"([^\"]+)\"[^>]*>\s*$", r"## Update: \1", body, flags=re.M)
    body = re.sub(r"^\s*<Note>\s*$", "> Note:", body, flags=re.M)
    body = re.sub(r"^\s*</?(?:Steps|Step|CardGroup|Card|Update|Note|CodeGroup)>\s*$", "", body, flags=re.M)
    return body.strip() + "\n"


def render(path, data):
    sha = git_blob_sha(data)
    source_url = f"{REPO}/blob/main/{path}.mdx"
    header = f"Source: [CSharness-Docs/{path}.mdx]({source_url})\nSource blob: `{sha}`. Mirrored from GitHub; edit the MDX source to change this page.\n\n"
    return sha, header + convert_mdx(data.decode("utf-8"))


def notion_request(method, endpoint, key, payload=None):
    encoded = json.dumps(payload).encode() if payload is not None else None
    req = Request(API + endpoint, data=encoded, method=method, headers={
        "Authorization": "Bearer " + key,
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    })
    for attempt in range(5):
        try:
            with urlopen(req, timeout=45) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            if error.code in (429, 500, 502, 503, 504) and attempt < 4:
                delay = int(error.headers.get("Retry-After", "0") or "0")
                time.sleep(max(delay, 2 ** attempt))
                continue
            raise RuntimeError(f"Notion HTTP {error.code} on {endpoint}: {detail}") from error
        except URLError as error:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Notion network error on {endpoint}: {error}") from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Validate files and print planned destinations without calling Notion")
    parser.add_argument("--force", action="store_true", help="Rebuild every mapped page, even when its source blob is unchanged")
    args = parser.parse_args()
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    if len(mapping) != len(set(mapping.values())):
        raise RuntimeError("Multiple source pages map to one Notion page")
    key = os.environ.get("NOTION_API_KEY")
    if not args.dry_run and not key:
        raise RuntimeError("Set NOTION_API_KEY as a GitHub Actions repository secret")
    changed = skipped = 0
    for path, page_id in mapping.items():
        file = ROOT / (path + ".mdx")
        if not file.is_file():
            raise RuntimeError(f"Missing docs source: {file}")
        sha, content = render(path, file.read_bytes())
        if args.dry_run:
            print(f"VALID {path}.mdx -> {page_id} ({sha})")
            continue
        current = notion_request("GET", f"/pages/{page_id}/markdown", key)
        current_md = current.get("markdown", "")
        old = re.search(r"Source blob: `([0-9a-f]{40})`", current_md)
        if not old:
            raise RuntimeError(f"Refusing to overwrite {path}: source marker missing in Notion page {page_id}")
        if old.group(1) == sha and not args.force:
            skipped += 1
            print(f"UNCHANGED {path}")
            continue
        notion_request("PATCH", f"/pages/{page_id}/markdown", key, {
            "type": "replace_content",
            "replace_content": {"new_str": content},
        })
        changed += 1
        print(f"SYNCED {path}: {old.group(1)} -> {sha}")
    print(f"Done: {changed} synced, {skipped} unchanged, {len(mapping)} mapped")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
