# Idea from Andrew6rant's neofetch-style profile.
#
# Run locally:
#   pip install pillow
#   GITHUB_TOKEN=<token> python card/generate.py

import json
import os
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

USERNAME = "georgielovejuice"

# Left side: about me. A row with None as the key starts a new section.
ABOUT = [
    ("OS", "macOS, Windows, Linux"),
    ("Host", "KMITL"),
    ("Kernel", "Computer Engineering (Intl.), Class of 2028"),
    ("IDE", "VS Code"),
    (None, "Languages"),
    ("Languages.Programming", "Python, TypeScript, SQL, Bash"),
    ("Languages.Real", "Thai, English"),
    (None, "Hobbies"),
    ("Hobbies.Infra", "Homelab, Networking, Self-hosting"),
    ("Hobbies.Hardware", "PC building, Mechanical keyboards"),
]

PHOTO = ""        # empty = use my GitHub avatar, or e.g. "card/photo.png"
REMOVE_BACKGROUND = True  # works best with a plain wall behind me
ART_WIDTH = 60    # how many characters wide the portrait is
TEXT_WIDTH = 56   # how many characters wide the info column is

# Characters from light to heavy. More ink = brighter on a dark card.
SHADES = " .:-=+*#%@"

COLORS = {
    "dark": {
        "bg": "#0d1117", "border": "#30363d", "art": "#c9d1d9",
        "title": "#58a6ff", "line": "#3d444d", "key": "#ffa657",
        "dots": "#484f58", "value": "#c9d1d9", "number": "#79c0ff",
    },
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "art": "#24292f",
        "title": "#0969da", "line": "#d0d7de", "key": "#953800",
        "dots": "#8c959f", "value": "#24292f", "number": "#0550ae",
    },
}


QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    avatarUrl(size: 400)
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10) { edges { size node { name } } }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
    }
  }
}
"""


def ask_github(token):
    body = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"Bearer {token}", "User-Agent": USERNAME},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)["data"]["user"]


def account_age(created_at):
    start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    years = now.year - start.year
    months = now.month - start.month
    days = now.day - start.day

    # borrow from the bigger unit when we go negative, like subtraction by hand
    if days < 0:
        months -= 1
        days += 30
    if months < 0:
        years -= 1
        months += 12

    return f"{years} years, {months} months, {days} days"


def top_languages(repos):
    # add up bytes of code per language across all my repos
    total = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            total[name] = total.get(name, 0) + edge["size"]

    all_bytes = sum(total.values())
    if all_bytes == 0:
        return "-"

    top3 = sorted(total, key=total.get, reverse=True)[:3]
    return ", ".join(f"{name} {total[name] * 100 // all_bytes}%" for name in top3)


def get_stats(user):
    repos = user["repositories"]["nodes"]
    work = user["contributionsCollection"]
    return {
        "Uptime": account_age(user["createdAt"]),
        "Top languages": top_languages(repos),
        "Repos": user["repositories"]["totalCount"],
        "Stars": sum(repo["stargazerCount"] for repo in repos),
        "Followers": user["followers"]["totalCount"],
        "Commits (1y)": work["totalCommitContributions"],
        "PRs (1y)": work["totalPullRequestContributions"],
    }

def load_photo(user):
    if PHOTO:
        return Image.open(PHOTO)
    with urllib.request.urlopen(user["avatarUrl"]) as response:
        return Image.open(BytesIO(response.read()))


def is_close(color1, color2):
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    return abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2) < 60


def photo_to_ascii(photo, theme):
    photo = photo.convert("RGB")

    # a character is about twice as tall as it is wide, so use half the rows
    rows = int(ART_WIDTH * photo.height / photo.width / 2)
    small = photo.resize((ART_WIDTH, rows))
    gray = ImageOps.autocontrast(small.convert("L"))

    # guess the background from the top-left corner and leave it blank,
    # otherwise a white wall turns into a solid block of @@@@
    background = small.getpixel((0, 0))

    lines = []
    for y in range(rows):
        line = ""
        for x in range(ART_WIDTH):
            if REMOVE_BACKGROUND and is_close(small.getpixel((x, y)), background):
                line += " "
                continue
            brightness = gray.getpixel((x, y)) / 255
            if theme == "light":
                brightness = 1 - brightness  # dark ink on white paper
            index = int(brightness * (len(SHADES) - 1))
            line += SHADES[index]
        lines.append(line)
    return lines

def dotted_row(key, value, width):
    value = str(value)
    dots = "." * max(2, width - len(key) - len(value) - 6)
    return [(". " + key + ": ", "key"), (dots, "dots"), (" " + value, "value")]


def info_rows(stats):
    rows = []

    def title(text):
        label = f" {text} "
        rows.append([("─", "line"), (label, "title"), ("─" * (TEXT_WIDTH - len(label) - 1), "line")])

    title(f"{USERNAME}@github")
    for key, value in ABOUT:
        if key is None:
            rows.append([])
            title(value)
        else:
            rows.append(dotted_row(key, value, TEXT_WIDTH))

    rows.append([])
    title("GitHub Stats")
    rows.append(dotted_row("Uptime", stats["Uptime"], TEXT_WIDTH))
    rows.append(dotted_row("Top languages", stats["Top languages"], TEXT_WIDTH))

    # numbers come in pairs, two per line: "Repos ... 24 | Stars ... 4"
    half = (TEXT_WIDTH - 3) // 2
    pairs = [("Repos", "Stars"), ("Followers", "Commits (1y)")]
    for left, right in pairs:
        row = dotted_row(left, stats[left], half) + [(" | ", "line")] + dotted_row(right, stats[right], half)
        rows.append([(text, "number" if part == "value" else part) for text, part in row])
    rows.append(dotted_row("PRs (1y)", stats["PRs (1y)"], TEXT_WIDTH))
    return rows


def make_svg(art, rows, theme):
    color = COLORS[theme]
    pad = 28
    font = "Consolas, Menlo, 'DejaVu Sans Mono', monospace"

    # monospace fonts are about 0.6x as wide as their size
    art_x, art_size, art_line = pad, 8, 9.6
    text_x = pad + ART_WIDTH * art_size * 0.6 + 32
    text_size, text_line = 16, 20

    width = int(text_x + TEXT_WIDTH * text_size * 0.6 + pad)
    height = int(max(len(art) * art_line, len(rows) * text_line) + pad * 2)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" '
        f'fill="{color["bg"]}" stroke="{color["border"]}"/>',
        f'<g font-family="{font}" xml:space="preserve">',
    ]

    art_top = (height - len(art) * art_line) / 2
    for i, line in enumerate(art):
        y = art_top + (i + 1) * art_line
        svg.append(f'<text x="{art_x}" y="{y:.1f}" font-size="{art_size}" fill="{color["art"]}">{escape(line)}</text>')

    text_top = (height - len(rows) * text_line) / 2
    for i, row in enumerate(rows):
        y = text_top + (i + 1) * text_line - 5
        spans = "".join(f'<tspan fill="{color[part]}">{escape(text)}</tspan>' for text, part in row)
        svg.append(f'<text x="{text_x:.1f}" y="{y:.1f}" font-size="{text_size}">{spans}</text>')

    svg.append("</g></svg>")
    return "\n".join(svg)


if __name__ == "__main__":
    user = ask_github(os.environ["GITHUB_TOKEN"])
    stats = get_stats(user)
    photo = load_photo(user)
    rows = info_rows(stats)

    for theme in ["dark", "light"]:
        art = photo_to_ascii(photo, theme)
        with open(f"{theme}_mode.svg", "w", encoding="utf-8") as f:
            f.write(make_svg(art, rows, theme))
        print("made", f"{theme}_mode.svg")