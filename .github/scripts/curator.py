#!/usr/bin/env python3
"""
Autonomous Curator for FOSS Virtualization & Containerization.
Enforces strict OSI license whitelist, anti-crack/piracy/NSFW blacklist, and liveness checks.
"""

from datetime import datetime, timezone
import json
import os
import sys
import urllib.parse
import urllib.request

MIN_STARS = 1500
MAX_PUSH_AGE_DAYS = 180

BLACKLIST_KEYWORDS = [
    "activation", "crack", "patch", "keygen", "reset-trial",
    "trial-reset", "license-key", "kms", "bypass", "pirate", "tracker",
    "fuckingfast", "nsfw", "porn", "xxx", "adult", "hentai", "18+"
]

ALLOWED_LICENSES = {
    "gpl-3.0", "gpl-2.0", "agpl-3.0", "lgpl-3.0",
    "apache-2.0", "mit", "mpl-2.0", "bsd-3-clause", "bsd-2-clause"
}


def get_headers():
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FOSS-Virtualization-Curator"
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_json(url):
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def is_blacklisted(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in BLACKLIST_KEYWORDS)


def is_alive_and_active(repo):
    if repo.get("archived") or repo.get("disabled"):
        return False
    pushed_at_str = repo.get("pushed_at")
    if not pushed_at_str:
        return False
    try:
        pushed_date = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - pushed_date).days
        return age_days <= MAX_PUSH_AGE_DAYS
    except Exception:
        return True


def scan_repositories():
    existing = open("README.md", encoding="utf-8").read().lower() if os.path.exists("README.md") else ""
    queries = [
        f"topic:virtualization stars:>={MIN_STARS}",
        f"topic:proxmox stars:>={MIN_STARS}",
        f"topic:containers stars:>={MIN_STARS}"
    ]
    candidates = []
    seen = set()
    for q in queries:
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page=15"
        data = fetch_json(url)
        if not data or "items" not in data:
            continue
        for item in data["items"]:
            full_name = item["full_name"]
            if full_name in seen:
                continue
            seen.add(full_name)
            if item["html_url"].lower() in existing or item["name"].lower() in existing:
                continue
            desc = (item.get("description") or "").strip()
            if is_blacklisted(item["name"]) or is_blacklisted(desc):
                continue
            license_info = item.get("license") or {}
            license_key = (license_info.get("key") or "").lower()
            if license_key not in ALLOWED_LICENSES or not is_alive_and_active(item):
                continue
            candidates.append({
                "name": item["name"],
                "url": item["html_url"],
                "stars": item["stargazers_count"],
                "license": license_info.get("spdx_id") or license_key.upper(),
                "description": desc
            })
    return candidates


def generate_report(candidates, output_file="curator_summary.md"):
    if not candidates:
        return False
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("### 🤖 Autonomous Curator — Verified FOSS Virtualization & Container Findings\n\n")
        f.write("| Project | Stars | License | Description |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for c in candidates:
            f.write(f"| [**{c['name']}**]({c['url']}) | ⭐ {c['stars']:,} | `{c['license']}` | {c['description']} |\n")
    return True


if __name__ == "__main__":
    items = scan_repositories()
    found = generate_report(items)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if found else 'false'}\n")
            f.write(f"count={len(items)}\n")
