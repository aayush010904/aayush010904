#!/usr/bin/env python3
"""
github-neofetch — render a neofetch-style SVG panel populated with
live GitHub stats.

Reads:
    profile.yml    who to fetch, and which rows to render
    theme.yml      colors + layout constants
    ascii-art.txt  the art shown on the left

Writes:
    output/neofetch.svg  (path is configurable via profile.yml: output)

Usage:
    python3 generate.py
    GITHUB_TOKEN=ghp_xxx python3 generate.py   # higher rate limit +
                                                # unlocks the commit-
                                                # contributions row
"""

import html
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent

GITHUB_TOKEN = (
    os.getenv("GITHUB_TOKEN")
    or os.getenv("GH_TOKEN")
)

if GITHUB_TOKEN is None:
    token_file = ROOT / ".token"

    if token_file.exists():
        GITHUB_TOKEN = token_file.read_text().strip()


import requests
import yaml

ROOT = Path(__file__).parent

# ======================= CONFIG =======================

PROFILE = yaml.safe_load((ROOT / "profile.yml").read_text())
THEME = yaml.safe_load((ROOT / "theme.yml").read_text())
ASCII_ART_PATH = ROOT / "ascii-art.txt"
OUTPUT_PATH = ROOT / PROFILE.get("output", "output/neofetch.svg")

FONT_SIZE = THEME["font_size"]
LINE_H = THEME["line_height"]
CHAR_W = FONT_SIZE * 0.6            # monospace character width approximation
PAD_TOP = 30
PAD_RIGHT = 15
ASCII_X = 15
ASCII_GAP = THEME["ascii_gap"]
KV_WIDTH = 46                       # character budget for "Key: ..... Value" rows
PANEL_MIN_CHARS = 55              # panel never compresses below this
MIN_W = 760
MIN_H = 300

BG_COLOR = THEME["background"]
FG_COLOR = THEME["foreground"]
KEY_COLOR = THEME["key"]
VALUE_COLOR = THEME["value"]
DOT_COLOR = THEME["dots"]



# ========================================================


def esc(s):
    return html.escape(str(s), quote=False)


def dotted_kv(key, value, width=KV_WIDTH):
    """Build a (key, dot-leader, value) triple that fills `width` chars."""
    used = len(key) + 1 + len(str(value))
    dots = max(3, width - used)
    return key, "." * dots, str(value)


def rule_after(text, total_chars):
    """Em-dash fill remaining space after `text` up to total_chars."""
    remaining = max(3, total_chars - len(text) - 1)
    return "-" + ("\u2014" * (remaining - 2)) + "-"


# --------------------- GitHub data ---------------------

def fmt_uptime(created_at_iso):
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    months_total = (now.year - created.year) * 12 + (now.month - created.month)
    years, months = divmod(max(months_total, 0), 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    parts.append(f"{months} month{'s' if months != 1 else ''}")
    return ", ".join(parts)


# def rest_get(url, token):
#     headers = {
#         "Accept": "application/vnd.github+json",
#         "User-Agent": "github-neofetch",
#     }
#     if token:
#         headers["Authorization"] = f"Bearer {token}"
#     resp = requests.get(url, headers=headers, timeout=15)
#     resp.raise_for_status()
#     return resp.json()


# def graphql_contributions(username, token):
#     """Total commit contributions in the last year. Requires a token;
#     returns None (rendered as "N/A") if no token is configured or the
#     call fails for any reason — this row is a nice-to-have, not a hard
#     dependency."""
#     if not token:
#         return None
#     query = """
#     query($login: String!) {
#       user(login: $login) {
#         contributionsCollection {
#           contributionCalendar { totalContributions }
#         }
#       }
#     }
#     """
#     try:
#         resp = requests.post(
#             "https://api.github.com/graphql",
#             json={"query": query, "variables": {"login": username}},
#             headers={"Authorization": f"Bearer {token}"},
#             timeout=15,
#         )
#         resp.raise_for_status()
#         data = resp.json()
#         return data["data"]["user"]["contributionsCollection"][
#             "contributionCalendar"
#         ]["totalContributions"]
#     except Exception:
#         return None


# def github_stats(username, token):
#     user = rest_get(f"https://api.github.com/users/{username}", token)

#     repos = []
#     page = 1
#     while True:
#         batch = rest_get(
#             f"https://api.github.com/users/{username}/repos"
#             f"?per_page=100&page={page}&type=owner",
#             token,
#         )
#         if not batch:
#             break
#         repos.extend(batch)
#         if len(batch) < 100:
#             break
#         page += 1

#     stars = sum(r.get("stargazers_count", 0) for r in repos if isinstance(r, dict))
#     contributions = graphql_contributions(username, token)

#     return {
#         "username": user.get("login", username),
#         "name": user.get("name") or user.get("login", username),
#         "repos": user.get("public_repos", len(repos)),
#         "followers": user.get("followers", 0),
#         "following": user.get("following", 0),
#         "stars": stars,
#         "contributions": contributions if contributions is not None else "N/A",
#         "uptime": fmt_uptime(user["created_at"]),
#     }
GRAPHQL_QUERY = """
query($login: String!) {

  user(login: $login) {

    login
    name
    bio
    company
    location
    websiteUrl
    avatarUrl
    createdAt

    followers {
      totalCount
    }

    following {
      totalCount
    }

    repositories(
      ownerAffiliations: OWNER
      first: 100
      privacy: PUBLIC
      orderBy: {
        field: UPDATED_AT
        direction: DESC
      }
    ) {

      totalCount

      nodes {

        name

        stargazerCount

        forkCount

        primaryLanguage {
          name
        }

      }

    }

    contributionsCollection {

      contributionCalendar {

        totalContributions

      }

    }

  }

}
"""
# print("Token found:", TOKEN is not None)
# print("First 10 chars:", TOKEN[:10] if TOKEN else "None")


def github_stats(username, token):

    response = requests.post(
        "https://api.github.com/graphql",

        headers={
            "Authorization": f"Bearer {token}"
        },

        json={
            "query": GRAPHQL_QUERY,
            "variables": {
                "login": username
            }
        },

        timeout=15,
    )

    # print("Status:", response.status_code)
    # print(response.text)

    response.raise_for_status()

    user = response.json()["data"]["user"]

    repos = user["repositories"]["nodes"]

    stars = sum(
        repo["stargazerCount"]
        for repo in repos
    )

    forks = sum(
        repo["forkCount"]
        for repo in repos
    )

    languages = {}

    for repo in repos:

        lang = repo["primaryLanguage"]

        if lang is None:
            continue

        name = lang["name"]

        languages[name] = languages.get(name, 0) + 1

    top_language = max(
        languages,
        key=languages.get,
        default="N/A"
    )

    return {

        # Profile
        "username": user["login"],
        "name": user["name"] or user["login"],
        "bio": user["bio"] or "",
        "company": user["company"] or "",
        "location": user["location"] or "",
        "website": user["websiteUrl"] or "",
        "avatar": user["avatarUrl"],

        # GitHub
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "stars": stars,
        "forks": forks,
        "contributions": (
            user["contributionsCollection"]
                ["contributionCalendar"]
                ["totalContributions"]
        ),

        # Misc
        "uptime": fmt_uptime(user["createdAt"]),
        "top_language": top_language,

    }
def apply_placeholders(text, stats):
    for k, v in stats.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


# --------------------- row building ---------------------

def build_rows(profile_rows, stats):
    """Turn profile.yml's row spec into the ('kv'|'section'|'blank', ...)
    tuples the renderer expects, substituting {{placeholders}} in values."""
    rows = []
    for i, item in enumerate(profile_rows):
        if not isinstance(item, dict):
            raise ValueError(
                f"profile.yml rows[{i}] must be a mapping like "
                f"'key: ... / value: ...', 'section: ...', or 'blank: true' "
                f"— got: {item!r}"
            )
        if "blank" in item:
            rows.append(("blank",))
        elif "section" in item:
            rows.append(("section", apply_placeholders(item["section"], stats)))
        elif "key" in item and "value" in item:
            key = apply_placeholders(item["key"], stats)
            value = apply_placeholders(item["value"], stats)
            rows.append(("kv", key, value))
        else:
            raise ValueError(
                f"profile.yml rows[{i}] is missing 'key'/'value' "
                f"(or 'section', or 'blank: true') — got: {item!r}"
            )
    return rows


# --------------------- SVG rendering ---------------------

def render(ascii_lines, header, rows):
    ascii_cols = max((len(l) for l in ascii_lines), default=0)
    ascii_w = ASCII_X + int(ascii_cols * CHAR_W)
    panel_x = ascii_w + ASCII_GAP
    panel_chars = PANEL_MIN_CHARS
    panel_w_px = int(panel_chars * CHAR_W) + PAD_RIGHT
    total_w = max(MIN_W, panel_x + panel_w_px)

    # Header occupies the first panel row; content rows start below it.
    panel_svg = []
    row = 1  # row 0 is the header
    for item in rows:
        kind = item[0]
        yy = PAD_TOP + row * LINE_H

        if kind == "blank":
            row += 1
            continue

        elif kind == "kv":
            key, dots, value = dotted_kv(item[1], item[2])
            panel_svg.append(
                f'<text x="{panel_x}" y="{yy}" fill="{FG_COLOR}">. '
                f'<tspan fill="{KEY_COLOR}">{esc(key)}</tspan>:'
                f'<tspan fill="{DOT_COLOR}"> {esc(dots)} </tspan>'
                f'<tspan fill="{VALUE_COLOR}">{esc(value)}</tspan></text>'
            )

        elif kind == "section":
            title = "- " + item[1]
            rule = rule_after(title, panel_chars)
            panel_svg.append(
                f'<text x="{panel_x}" y="{yy}" fill="{FG_COLOR}" font-weight="bold">{esc(title)}'
                f'<tspan font-weight="normal"> {esc(rule)}</tspan></text>'
            )

        row += 1

    header_rule = rule_after(header, panel_chars)
    header_svg = (
        f'<text x="{panel_x}" y="{PAD_TOP}" fill="{FG_COLOR}" font-weight="bold">{esc(header)}'
        f'<tspan font-weight="normal"> {esc(header_rule)}</tspan></text>'
    )

    content_h = PAD_TOP + row * LINE_H + 20
    ascii_h = len(ascii_lines) * LINE_H
    total_h = max(MIN_H, content_h, PAD_TOP + ascii_h + 20)
    ascii_y0 = PAD_TOP + max(0, (total_h - PAD_TOP * 2 - ascii_h) // 2)

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'font-family="ConsolasFallback, Consolas, monospace" '
        f'width="{total_w}px" height="{total_h:.0f}px" font-size="{FONT_SIZE}px">'
    )
    out.append("<style>")
    out.append(
        "@font-face { src: local('Consolas'), local('Consolas Bold'); "
        "font-family: 'ConsolasFallback'; font-display: swap; "
        "-webkit-size-adjust: 109%; size-adjust: 109%; }"
    )
    out.append("text, tspan { white-space: pre; }")
    out.append("</style>")
    out.append(f'<rect width="{total_w}px" height="{total_h:.0f}px" fill="{BG_COLOR}" rx="15"/>')

    out.append(f'<text x="{ASCII_X}" y="{ascii_y0}" fill="{FG_COLOR}">')
    for i, line in enumerate(ascii_lines):
        yy = ascii_y0 + i * LINE_H
        out.append(f'<tspan x="{ASCII_X}" y="{yy}">{esc(line)}</tspan>')
    out.append("</text>")

    out.append(header_svg)
    out.extend(panel_svg)
    out.append("</svg>")

    return "\n".join(out), total_w, total_h


def main():
    username = PROFILE["github"]["username"]

    try:
        stats = github_stats(username, GITHUB_TOKEN)
    except requests.HTTPError as e:
        print(f"GitHub API error: {e}", file=sys.stderr)
        sys.exit(1)

    header = apply_placeholders(PROFILE["header"], stats)
    rows = build_rows(PROFILE["rows"], stats)

    ascii_lines = ASCII_ART_PATH.read_text(encoding="utf-8").splitlines()
    while ascii_lines and ascii_lines[-1].strip() == "":
        ascii_lines.pop()

    svg, w, h = render(ascii_lines, header, rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}  ({w}x{h:.0f}px)")


if __name__ == "__main__":
    main()