"""Update the generated statistics table in the profile README."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
START_MARKER = "<!-- STATS:START -->"
END_MARKER = "<!-- STATS:END -->"


def github_headers() -> dict[str, str]:
    """Build headers for public API access, optionally using Actions' token."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "lukasmateju-profile-readme",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_public_repositories(username: str) -> list[dict]:
    """Fetch every public repository owned by the configured user."""
    repositories: list[dict] = []
    page = 1

    while True:
        query = urlencode(
            {
                "type": "owner",
                "sort": "pushed",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            }
        )
        request = Request(
            f"{API_ROOT}/users/{username}/repos?{query}",
            headers=github_headers(),
        )
        with urlopen(request, timeout=30) as response:
            batch = json.load(response)

        if not isinstance(batch, list):
            raise RuntimeError(f"GitHub returned an unexpected response: {batch}")

        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return repositories


def display_date() -> str:
    """Return a readable UTC date without platform-specific formatting."""
    today = datetime.now(timezone.utc)
    return f"{today.strftime('%B')} {today.day}, {today.year}"


def build_stats_table(username: str, repositories: list[dict]) -> str:
    """Build the Markdown block shown on the profile."""
    projects = [
        repository
        for repository in repositories
        if not repository.get("fork")
        and repository.get("name", "").casefold() != username.casefold()
    ]

    project_count = len(projects)
    star_count = sum(
        int(repository.get("stargazers_count", 0)) for repository in projects
    )

    if projects:
        latest = max(projects, key=lambda repository: repository.get("pushed_at") or "")
        latest_project = f"[{latest['name']}]({latest['html_url']})"
    else:
        latest_project = "—"

    return "\n".join(
        [
            START_MARKER,
            "| Public projects | Stars received | Most recently pushed | Generated |",
            "| ---: | ---: | :--- | :--- |",
            f"| **{project_count}** | **{star_count}** | {latest_project} | {display_date()} |",
            END_MARKER,
        ]
    )


def replace_stats_block(readme: str, replacement: str) -> str:
    """Replace exactly one marked statistics block."""
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )
    updated, replacement_count = pattern.subn(replacement, readme)
    if replacement_count != 1:
        raise RuntimeError(
            f"Expected one statistics block in README.md; found {replacement_count}."
        )
    return updated


def main() -> None:
    """Fetch public data and refresh README.md."""
    username = os.getenv("GITHUB_USERNAME", "lukasmateju")
    repositories = fetch_public_repositories(username)
    current_readme = README_PATH.read_text(encoding="utf-8")
    updated_readme = replace_stats_block(
        current_readme,
        build_stats_table(username, repositories),
    )
    README_PATH.write_text(updated_readme, encoding="utf-8")
    print(f"Updated public profile statistics for {username}.")


if __name__ == "__main__":
    main()
