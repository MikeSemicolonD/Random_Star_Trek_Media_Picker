"""Updater for the Random Star Trek Media Picker.

Pulls episode and film data from Wikipedia's MediaWiki API as raw *wikitext*
and parses the {{Episode list}} templates and section headings. Wikitext
templates expose data as named parameters, so a single code path works for
every show -- no per-show, per-table HTML scraping.

Output is written to data.json; the picker loads that file at startup. The
updater never edits StarTrekMediaPicker.py, so a bad scrape cannot corrupt the
program logic. Results are validated before anything is written.

Requires: mwparserfromhell  (everything else is the standard library)
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

import mwparserfromhell
from mwparserfromhell.nodes import Heading, Template

API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "StarTrekMediaPicker-Updater/2.0 "
    "(https://github.com/legoguy217/StarTrekMediaPicker)"
)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
README_FILE = os.path.join(HERE, "README.md")

# Each TV series: (menu label, Wikipedia "List of ... episodes" page title).
# Adding a new show is a single line here -- no parser changes needed.
SERIES = [
    ("The Original Series", "List of Star Trek: The Original Series episodes"),
    ("The Animated Series", "List of Star Trek: The Animated Series episodes"),
    ("The Next Generation", "List of Star Trek: The Next Generation episodes"),
    ("Deep Space Nine", "List of Star Trek: Deep Space Nine episodes"),
    ("Voyager", "List of Star Trek: Voyager episodes"),
    ("Enterprise", "List of Star Trek: Enterprise episodes"),
    ("Discovery", "List of Star Trek: Discovery episodes"),
    ("Short Treks", "List of Star Trek: Short Treks episodes"),
    ("Picard", "List of Star Trek: Picard episodes"),
    ("Lower Decks", "List of Star Trek: Lower Decks episodes"),
    ("Prodigy", "List of Star Trek: Prodigy episodes"),
    ("Strange New Worlds", "List of Star Trek: Strange New Worlds episodes"),
]

FILM_PAGE = "Star Trek (film series)"

# data.json series labels are prefixed with the franchise name.
SERIES_LABEL_PREFIX = "Star Trek: "

# A title may end with footnote markers like "[a]" or "[1]" -- strip them.
_FOOTNOTE = re.compile(r"\s*\[[a-z0-9]+\]\s*$", re.IGNORECASE)
_SEASON_NUM = re.compile(r"season\s+(\d+)", re.IGNORECASE)
_YEAR = re.compile(r"\(\d{4}\)")


def fetch_wikitext(page):
    """Return the raw wikitext of a Wikipedia page (follows redirects)."""
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "redirects": 1,
        "format": "json",
        "formatversion": 2,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(
                    "API error for %r: %s"
                    % (page, data["error"].get("info", "unknown"))
                )
            return data["parse"]["wikitext"]
        except Exception as err:  # noqa: BLE001 - retry any transient failure
            last_error = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("failed to fetch %r: %s" % (page, last_error))


def clean_text(raw):
    """Reduce a wikitext fragment to plain display text.

    Strips <ref> citations, wikilinks (keeping the visible label), italics,
    bold, HTML entities, non-breaking spaces and trailing footnote markers.
    """
    code = mwparserfromhell.parse(str(raw))
    for tag in code.filter_tags():
        if str(tag.tag).strip().lower() == "ref":
            try:
                code.remove(tag)
            except ValueError:
                pass
    text = code.strip_code(normalize=True, collapse=True)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"“”")
    while _FOOTNOTE.search(text):
        text = _FOOTNOTE.sub("", text).strip()
    return text


def template_param(template, name):
    """Return a template parameter's value, or '' if it is absent."""
    try:
        return template.get(name).value
    except ValueError:
        return ""


def episode_list_templates(code):
    """Yield every {{Episode list}} (and /sublist variant) template in code."""
    for template in code.filter_templates():
        name = str(template.name).strip().lower()
        if name == "episode list" or name.startswith("episode list/"):
            yield template


def parse_show(label, page):
    """Fetch and parse one TV series; return a list of 'S#E## Title' strings.

    Handles both layouts: episodes listed inline on the page, and episodes
    transcluded from per-season articles via {{:Star Trek: <Show> season N}}.
    """
    print("  fetching %s" % page)
    code = mwparserfromhell.parse(fetch_wikitext(page))

    seasons = {}  # season number -> ordered list of episode titles
    current_season = 1

    # Walk headings and templates in document order. A recursive walk is
    # required: on some pages the episode tables are nested inside other
    # markup, so a top-level-only walk would miss them.
    for node in code.ifilter(recursive=True):
        if isinstance(node, Heading):
            heading = clean_text(node.title)
            match = _SEASON_NUM.search(heading)
            if match:
                current_season = int(match.group(1))
            elif "pilot" in heading.lower():
                current_season = 0
        elif isinstance(node, Template):
            name = str(node.name).strip()
            lower = name.lower()
            # {{:Star Trek: <Show> season N}} -> transcluded season article
            if name.startswith(":") and _SEASON_NUM.search(lower):
                season_no = int(_SEASON_NUM.search(lower).group(1))
                print("    season %d <- %s" % (season_no, name[1:]))
                sub = mwparserfromhell.parse(fetch_wikitext(name[1:]))
                bucket = seasons.setdefault(season_no, [])
                for episode in episode_list_templates(sub):
                    title = clean_text(template_param(episode, "Title"))
                    if title:
                        bucket.append(title)
                time.sleep(0.1)
            # Episodes listed directly on this page
            elif lower == "episode list" or lower.startswith("episode list/"):
                title = clean_text(template_param(node, "Title"))
                if title:
                    seasons.setdefault(current_season, []).append(title)

    episodes = []
    for season_no in sorted(seasons):
        for index, title in enumerate(seasons[season_no], start=1):
            episodes.append("S%dE%02d %s" % (season_no, index, title))
    print("  -> %s: %d episodes across %d season(s)"
          % (label, len(episodes), len(seasons)))
    return episodes


def parse_films(page):
    """Parse the film-series page; return [{'label':.., 'films':[..]}, ...].

    Films are pure heading structure: '== <Era> films ==' contains one
    '=== <Title> (YYYY) ===' heading per released film.
    """
    print("  fetching %s" % page)
    code = mwparserfromhell.parse(fetch_wikitext(page))

    eras = []
    current_films = None  # the 'films' list of the era currently being read
    for node in code.nodes:
        if not isinstance(node, Heading):
            continue
        text = clean_text(node.title)
        if node.level == 2:
            if "film" in text.lower():
                current_films = []
                eras.append({"label": text, "films": current_films})
            else:
                current_films = None  # left films section (Reception, Future)
        elif node.level == 3 and _YEAR.search(text) and current_films is not None:
            current_films.append(text)

    eras = [era for era in eras if era["films"]]
    for era in eras:
        print("  -> %s: %d film(s)" % (era["label"], len(era["films"])))
    return eras


def validate(series, movies):
    """Return a list of human-readable problems with the scraped data."""
    errors = []

    if len(series) < 10:
        errors.append("expected at least 10 TV series, got %d" % len(series))

    total_episodes = 0
    for show in series:
        if not show["episodes"]:
            errors.append("series %r has no episodes" % show["label"])
        for episode in show["episodes"]:
            parts = episode.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                errors.append(
                    "blank episode title in %r: %r" % (show["label"], episode)
                )
        total_episodes += len(show["episodes"])

    if not movies:
        errors.append("no film eras found")
    for era in movies:
        if not era["films"]:
            errors.append("film era %r is empty" % era["label"])

    # Guard against a partial scrape silently shrinking the catalogue.
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as handle:
                previous = json.load(handle)
        except (OSError, ValueError):
            previous = None
        if previous:
            prev_total = sum(
                len(s.get("episodes", [])) for s in previous.get("series", [])
            )
            if prev_total and total_episodes < prev_total * 0.9:
                errors.append(
                    "episode count dropped sharply: %d -> %d (>10%% loss)"
                    % (prev_total, total_episodes)
                )

    return errors


def update_readme(stamp):
    """Refresh the 'Data Last Updated' date in README.md, preserving markup."""
    if not os.path.exists(README_FILE):
        return
    with open(README_FILE, encoding="utf-8") as handle:
        readme = handle.read()
    new_readme = re.sub(
        r'<strong id="date">.*?</strong>',
        '<strong id="date">%s</strong>' % stamp,
        readme,
    )
    if new_readme != readme:
        with open(README_FILE, "w", encoding="utf-8") as handle:
            handle.write(new_readme)
        print("Updated README.md date stamp")


def main():
    series = []
    for label, page in SERIES:
        series.append({"label": SERIES_LABEL_PREFIX + label,
                       "episodes": parse_show(label, page)})

    movies = parse_films(FILM_PAGE)

    errors = validate(series, movies)
    if errors:
        print("\nValidation failed -- data.json was NOT written:")
        for error in errors:
            print("  - %s" % error)
        sys.exit(1)

    stamp = datetime.now().strftime("%B %d, %Y")
    payload = {
        "updated": stamp,
        "series": series,
        "movies": movies,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    total = sum(len(show["episodes"]) for show in series)
    films = sum(len(era["films"]) for era in movies)
    print("\nWrote data.json: %d series / %d episodes, %d film eras / %d films"
          % (len(series), total, len(movies), films))

    update_readme(stamp)


if __name__ == "__main__":
    main()
