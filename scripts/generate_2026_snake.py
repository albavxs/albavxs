#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

GITHUB_USER = os.environ.get("GITHUB_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
YEAR = int(os.environ.get("CONTRIBUTION_YEAR", "2026"))

if not GITHUB_USER or not GITHUB_TOKEN:
    print("GITHUB_USER/GITHUB_TOKEN are required", file=sys.stderr)
    sys.exit(1)

now = datetime.now(timezone.utc)
start = f"{YEAR}-01-01T00:00:00Z"
if now.year == YEAR:
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
else:
    end = f"{YEAR}-12-31T23:59:59Z"

query = """
query ContributionCalendar($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            weekday
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""

payload = json.dumps({
    "query": query,
    "variables": {"login": GITHUB_USER, "from": start, "to": end},
}).encode("utf-8")

request = urllib.request.Request(
    "https://api.github.com/graphql",
    data=payload,
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "github-profile-2026-snake",
    },
    method="POST",
)

with urllib.request.urlopen(request, timeout=30) as response:
    data = json.load(response)

if data.get("errors"):
    raise RuntimeError(json.dumps(data["errors"], indent=2))

user = data.get("data", {}).get("user")
if not user:
    raise RuntimeError(f"GitHub user {GITHUB_USER!r} was not found")

calendar = user["contributionsCollection"]["contributionCalendar"]
weeks = calendar["weeks"]
total = calendar["totalContributions"]

LIGHT = {
    "NONE": "#ebedf0",
    "FIRST_QUARTILE": "#9be9a8",
    "SECOND_QUARTILE": "#40c463",
    "THIRD_QUARTILE": "#30a14e",
    "FOURTH_QUARTILE": "#216e39",
}
DARK = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}

CELL = 10
GAP = 3
STEP = CELL + GAP
LEFT = 22
TOP = 34
BOTTOM = 18
DURATION = 14.0

points = []
days = []
for x, week in enumerate(weeks):
    ordered = sorted(
        [d for d in week["contributionDays"] if d["date"].startswith(f"{YEAR}-")],
        key=lambda d: d["weekday"],
    )
    iterable = ordered if x % 2 == 0 else list(reversed(ordered))
    for day in iterable:
        cx = LEFT + x * STEP + CELL / 2
        cy = TOP + day["weekday"] * STEP + CELL / 2
        points.append((cx, cy, day["date"]))
    for day in ordered:
        days.append((x, day))

if not points:
    raise RuntimeError(f"No contribution days returned for {YEAR}")

width = LEFT * 2 + max(1, len(weeks)) * STEP
height = TOP + 7 * STEP + BOTTOM

point_order = {date: i for i, (_, _, date) in enumerate(points)}
path_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in points)

def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def render(palette, dark=False):
    bg = "#0d1117" if dark else "#ffffff"
    text = "#8b949e" if dark else "#57606a"
    snake = "#58a6ff" if dark else "#0969da"

    rects = []
    active = []
    for x, day in days:
        px = LEFT + x * STEP
        py = TOP + day["weekday"] * STEP
        level = day["contributionLevel"]
        fill = palette.get(level, palette["NONE"])
        count = day["contributionCount"]
        idx = point_order.get(day["date"], 0)
        ratio = idx / max(1, len(points) - 1)

        anim = ""
        if count > 0:
            eat = min(0.86, 0.04 + 0.78 * ratio)
            after = min(0.90, eat + 0.012)
            anim = (
                f'<animate attributeName="opacity" dur="{DURATION}s" repeatCount="indefinite" '
                f'values="1;1;0;0;1" keyTimes="0;{eat:.4f};{after:.4f};0.94;1" />'
            )
            active.append(count)

        rects.append(
            f'<rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}">'
            f'<title>{esc(day["date"])} — {count} contributions</title>{anim}</rect>'
        )

    label = f"{YEAR} · {total} contributions"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="{bg}" rx="8"/>
  <text x="{LEFT}" y="19" fill="{text}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">{esc(label)}</text>
  <g>
    {''.join(rects)}
  </g>
  <path d="{path_d}" fill="none" stroke="{snake}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"
        pathLength="1" stroke-dasharray="0.065 0.935" opacity="0.96">
    <animate attributeName="stroke-dashoffset" values="0;-1" dur="{DURATION}s" repeatCount="indefinite"/>
  </path>
</svg>'''

os.makedirs("dist", exist_ok=True)
with open("dist/github-contribution-grid-snake.svg", "w", encoding="utf-8") as f:
    f.write(render(LIGHT, dark=False))
with open("dist/github-contribution-grid-snake-dark.svg", "w", encoding="utf-8") as f:
    f.write(render(DARK, dark=True))

print(f"Generated {YEAR} snake for {GITHUB_USER}: {total} contributions across {len(weeks)} weeks")
