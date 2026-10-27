#!/usr/bin/env python3
"""Manage events and build The Computation Society website.

Events are stored in events.json. Pages are rendered from templates/ into
site/, which is the folder to publish.

Usage:
    python events.py add                  # prompts for each field
    python events.py add --title "Hack Night" --date 2026-11-20 \
        --time "6:00 PM" --location "Room 101" --description "Bring a laptop."
    python events.py list                 # numbered list of all events
    python events.py remove 3             # remove event #3 from the list
    python events.py build                # regenerate site/ (add/remove do this too)

Only the Python standard library is used.
"""

import argparse
import html
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS_FILE = ROOT / "events.json"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "site"

SITE_NAME = "The Computation Society"
FIELDS = ["title", "date", "time", "location", "description", "link"]
REQUIRED = {"title", "date"}


# Events data
# ---------------------------------------------------------------------------

def load_events():
    if not EVENTS_FILE.exists():
        return []
    with EVENTS_FILE.open(encoding="utf-8") as f:
        events = json.load(f)
    for i, event in enumerate(events, 1):
        parse_date(event.get("date", ""), f"event #{i} ({event.get('title', 'untitled')})")
    return sorted(events, key=lambda e: e["date"])


def save_events(events):
    events = sorted(events, key=lambda e: e["date"])
    with EVENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_date(value, where=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        context = f" in {where}" if where else ""
        sys.exit(f"Error: invalid date '{value}'{context}; expected YYYY-MM-DD (e.g. 2026-11-20).")


# Rendering
# ---------------------------------------------------------------------------

def render(template_name, **values):
    """Fill {{ name }} placeholders in a template file."""
    text = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")

    def replace(match):
        key = match.group(1)
        if key not in values:
            sys.exit(f"Error: {template_name} uses {{{{ {key} }}}} but no value was given.")
        return str(values[key])

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replace, text)


def format_date(event):
    d = parse_date(event["date"])
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def event_card(event, past=False):
    e = {k: html.escape(str(event.get(k, "")).strip()) for k in FIELDS}
    meta = [format_date(event)]
    if e["time"]:
        meta.append(e["time"])
    if e["location"]:
        meta.append(e["location"])
    meta_html = " &middot; ".join(meta)

    parts = [
        f'<article class="event{" event-past" if past else ""}">',
        f'    <time class="event-date" datetime="{e["date"]}">{meta_html}</time>',
        f'    <h2 class="event-title">{e["title"]}</h2>',
    ]
    if e["description"]:
        parts.append(f'    <p class="event-description">{e["description"]}</p>')
    if e["link"] and not past:
        parts.append(f'    <a class="btn btn-secondary btn-small" href="{e["link"]}">More info</a>')
    parts.append("</article>")
    return "\n".join(" " * 16 + line for line in parts)


def next_event_card(upcoming):
    if upcoming:
        event = upcoming[0]
        title = html.escape(event["title"])
        when = format_date(event)
        if event.get("time"):
            when += f" &middot; {html.escape(event['time'])}"
        body = f"<strong>{title}</strong><br>{when}"
    else:
        body = "Stay tuned for upcoming events and activities. We look forward to seeing you at our next meeting!"
    return "\n".join([
        '                <article class="card card-featured">',
        '                    <p class="card-label">1.3 &emsp; Next up</p>',
        f"                    <p>{body}</p>",
        '                    <a class="btn btn-primary btn-small" href="events.html">All events</a>',
        "                </article>",
    ])


def empty_note(text):
    return f'                <p class="empty">{text}</p>'


def build():
    events = load_events()
    today = date.today()
    upcoming = [e for e in events if parse_date(e["date"]) >= today]
    past = [e for e in events if parse_date(e["date"]) < today][::-1]  # most recent first

    pages = {
        "index.html": dict(
            page_title=SITE_NAME,
            nav_home=" is-current",
            nav_events="",
            content=render("index.html", next_event_card=next_event_card(upcoming)),
        ),
        "events.html": dict(
            page_title=f"Events | {SITE_NAME}",
            nav_home="",
            nav_events=" is-current",
            content=render(
                "events.html",
                upcoming_events="\n".join(event_card(e) for e in upcoming)
                or empty_note("No upcoming events yet. Check back soon!"),
                past_events="\n".join(event_card(e, past=True) for e in past)
                or empty_note("No past events."),
            ),
        ),
    }

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")
    for filename, values in pages.items():
        page = render("base.html", year=today.year, **values)
        (OUTPUT_DIR / filename).write_text(page, encoding="utf-8")

    print(f"Built {len(pages)} pages into {OUTPUT_DIR.relative_to(ROOT)}/ "
          f"({len(upcoming)} upcoming, {len(past)} past events).")


# Commands
# ---------------------------------------------------------------------------

def cmd_add(args):
    event = {}
    for field in FIELDS:
        value = getattr(args, field)
        if value is None:
            label = field.capitalize()
            if field == "date":
                label += " (YYYY-MM-DD)"
            if field not in REQUIRED:
                label += " (optional)"
            value = input(f"{label}: ")
        value = value.strip()
        if field in REQUIRED and not value:
            sys.exit(f"Error: {field} is required.")
        if field == "date":
            parse_date(value)
        event[field] = value

    events = load_events()
    events.append(event)
    save_events(events)
    print(f"Added '{event['title']}' on {event['date']}.")
    build()


def cmd_list(args):
    events = load_events()
    if not events:
        print("No events.")
        return
    today = date.today()
    for i, e in enumerate(events, 1):
        tag = "" if parse_date(e["date"]) >= today else "  (past)"
        print(f"{i:>3}. {e['date']}  {e['title']}{tag}")


def cmd_remove(args):
    events = load_events()
    if not 1 <= args.number <= len(events):
        sys.exit(f"Error: no event #{args.number}. Run 'python events.py list' to see numbers.")
    removed = events.pop(args.number - 1)
    save_events(events)
    print(f"Removed '{removed['title']}' ({removed['date']}).")
    build()


def main():
    parser = argparse.ArgumentParser(description="Manage events and build the website.")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add", help="add an event (prompts for any field not given)")
    for field in FIELDS:
        add.add_argument(f"--{field}")
    add.set_defaults(func=cmd_add)

    sub.add_parser("list", help="list all events").set_defaults(func=cmd_list)

    remove = sub.add_parser("remove", help="remove an event by its number from 'list'")
    remove.add_argument("number", type=int)
    remove.set_defaults(func=cmd_remove)

    sub.add_parser("build", help="regenerate the site/ folder").set_defaults(func=lambda a: build())

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
