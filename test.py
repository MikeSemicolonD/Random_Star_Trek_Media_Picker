"""Ground-truth tests for the Star Trek Media Picker data pipeline.

If every check here passes, data.json is trustworthy and the picker will
behave correctly. The tests fall into two groups:

  1. Structural invariants -- format, season contiguity, no duplicates, and
     no leftover scraping artifacts (wikilinks, refs, HTML entities, etc.).
  2. Ground truth -- a curated table of season and per-season episode counts.
     Season counts are absolute facts; episode counts are Wikipedia
     episode-table *row* counts (a two-part episode occupies one row), which
     is the parser's defined behaviour.

The ground truth is a BASELINE, not an exact snapshot:

  * fewer episodes/seasons/shows/films than the baseline  -> FAILURE
    (a real regression -- data loss or a broken parser).
  * exactly the baseline                                  -> pass.
  * MORE than the baseline (a new episode, season, show or film)
                                                          -> pass, plus a
    NOTICE naming the new item and advising a ground_truth.json update.

Notices never fail the test -- the run is still positive (exit code 0).
Because the baseline is only a floor, a series still in production needs no
special handling: its current counts are the floor, and new episodes simply
raise notices like any other change.

The baseline lives in ground_truth.json beside this script, laid out like
data.json -- a "series" list and a "movies" list. Edit that file to keep the
baseline current; test.py holds only the checking logic.

Usage:
  python test.py            check the committed data.json
  python test.py --fresh    re-run Updater.py first, then check
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
GROUND_TRUTH_FILE = os.path.join(HERE, "ground_truth.json")

# The curated baseline is data, not code -- it lives in ground_truth.json so
# it can be updated without touching the checking logic below.
try:
    with open(GROUND_TRUTH_FILE, encoding="utf-8") as _gt_handle:
        _gt = json.load(_gt_handle)
except (OSError, ValueError) as _gt_error:
    sys.exit("Cannot read ground_truth.json: %s" % _gt_error)

try:
    # ground_truth.json mirrors data.json: a "series" list and a "movies"
    # list. Build the internal lookups the checks below rely on.
    # show name -> {season number: episode count}  (JSON keys are strings).
    GROUND_TRUTH = {
        entry["label"]: {int(season): count
                         for season, count in entry["seasons"].items()}
        for entry in _gt["series"]
    }
    # film era -> baseline film count.
    FILM_GROUND_TRUTH = {era["label"]: era["count"] for era in _gt["movies"]}
except (KeyError, AttributeError, TypeError, ValueError) as _gt_error:
    sys.exit("ground_truth.json has the wrong structure: %s" % _gt_error)

# Substrings that must never appear in a cleaned episode/film title.
ARTIFACTS = ["[[", "]]", "{{", "}}", "<ref", "&nbsp;", "&amp;", "&#",
             "\xa0", "\u200b", "  "]

EPISODE_RE = re.compile(r"^S(\d+)E(\d+) (.+)$")
FILM_RE = re.compile(r"^.+ \(\d{4}\)$")


class Results:
    """Collects pass/fail outcomes plus non-fatal 'new content' notices."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.notices = []

    def check(self, ok, label, detail=""):
        if ok:
            self.passed += 1
            print("  [PASS] %s" % label)
        else:
            self.failed += 1
            print("  [FAIL] %s%s" % (label, ("  -- " + detail) if detail else ""))
        return ok

    def record(self, ok):
        """Tally an outcome whose report line is printed by the caller."""
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def notice(self, message):
        """Flag new content -- informational, never fails the run."""
        self.notices.append(message)


def group_seasons(episodes):
    """Return {season number: sorted list of in-season episode numbers}."""
    seasons = {}
    for episode in episodes:
        match = EPISODE_RE.match(episode)
        if match:
            seasons.setdefault(int(match.group(1)), []).append(
                int(match.group(2)))
    for numbers in seasons.values():
        numbers.sort()
    return seasons


def load_data():
    with open(DATA_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def test_structure(data, results):
    print("\n[structure]")
    results.check(
        all(key in data for key in ("updated", "series", "movies")),
        "data.json has 'updated', 'series' and 'movies'")

    bad_format = []
    bad_artifacts = []
    for show in data["series"]:
        for episode in show["episodes"]:
            match = EPISODE_RE.match(episode)
            if not match or not match.group(3).strip():
                bad_format.append("%s: %r" % (show["label"], episode))
            for artifact in ARTIFACTS:
                if artifact in episode:
                    bad_artifacts.append(
                        "%s: %r (%r)" % (show["label"], episode, artifact))
    results.check(not bad_format, "every episode matches 'S#E## Title'",
                  "; ".join(bad_format[:3]))
    results.check(not bad_artifacts, "no scraping artifacts in titles",
                  "; ".join(bad_artifacts[:3]))

    gap_problems = []
    dup_problems = []
    for show in data["series"]:
        seasons = group_seasons(show["episodes"])
        for season_no, numbers in sorted(seasons.items()):
            if numbers != list(range(1, len(numbers) + 1)):
                gap_problems.append(
                    "%s S%d: %s" % (show["label"], season_no, numbers))
        if len(show["episodes"]) != len(set(show["episodes"])):
            dup_problems.append(show["label"])
    results.check(not gap_problems,
                  "episode numbers are contiguous 1..N within each season",
                  "; ".join(gap_problems[:3]))
    results.check(not dup_problems, "no duplicate episodes within a show",
                  ", ".join(dup_problems))


def test_ground_truth(data, results):
    print("\n[ground truth: seasons / episodes]")
    by_name = {show["label"]: show["episodes"] for show in data["series"]}

    # A missing series is a regression; a brand-new series is a notice.
    missing = sorted(set(GROUND_TRUTH) - set(by_name))
    new_shows = sorted(set(by_name) - set(GROUND_TRUTH))
    results.check(not missing,
                  "all ground-truth series are present in data.json",
                  "missing: " + ", ".join(missing))
    for name in new_shows:
        results.notice("new show %r (%d episodes) -- add it to "
                        "ground_truth.json" % (name, len(by_name[name])))

    header = "  %-32s %-9s %-12s %s" % ("show", "seasons", "episodes", "result")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for name in list(GROUND_TRUTH) + new_shows:
        episodes = by_name.get(name)
        if episodes is None:
            continue  # missing series -- already failed above
        seasons = group_seasons(episodes)
        expected = GROUND_TRUTH.get(name, {})

        problems = []   # regressions -> failure
        new_items = []  # extra content -> notice

        for season_no, want in sorted(expected.items()):
            got = len(seasons.get(season_no, []))
            if season_no not in seasons:
                problems.append("S%d missing" % season_no)
            elif got < want:
                problems.append("S%d %d<%d" % (season_no, got, want))
            elif got > want:
                new_items.append("S%d has %d episodes (baseline %d)"
                                  % (season_no, got, want))
        for season_no in sorted(set(seasons) - set(expected)):
            new_items.append("new season S%d (%d episodes)"
                              % (season_no, len(seasons[season_no])))

        for item in new_items:
            results.notice("%s: %s -- update ground_truth.json"
                            % (name, item))

        seasons_cell = "%d/%d" % (len(seasons), len(expected))
        episodes_cell = "%d/%d" % (len(episodes), sum(expected.values()))
        if problems:
            result = "FAIL: " + "; ".join(problems)
        elif new_items:
            result = "ok (+%d new)" % len(new_items)
        else:
            result = "ok"
        results.record(not problems)
        print("  %-32s %-9s %-12s %s"
              % (name, seasons_cell, episodes_cell, result))


def test_films(data, results):
    print("\n[films]")
    eras = {era["label"]: era["films"] for era in data["movies"]}

    bad_format = [
        "%s: %r" % (label, film)
        for label, films in eras.items()
        for film in films
        if not FILM_RE.match(film)
    ]
    results.check(not bad_format, "every film matches 'Title (YYYY)'",
                  "; ".join(bad_format[:3]))

    for label, want in FILM_GROUND_TRUTH.items():
        films = eras.get(label)
        if films is None:
            results.check(False, "film era present: %s" % label,
                          "era missing from data.json")
            continue
        got = len(films)
        results.check(got >= want, "%s: %d film(s)" % (label, got),
                      "baseline %d -- films missing" % want)
        if got > want:
            results.notice(
                "%s: %d films (baseline %d) -- new film; update "
                "ground_truth.json" % (label, got, want))

    for label in sorted(set(eras) - set(FILM_GROUND_TRUTH)):
        results.notice("new film era %r (%d films) -- add it to "
                        "ground_truth.json" % (label, len(eras[label])))


def main():
    if "--fresh" in sys.argv:
        print("Re-running Updater.py to refresh data.json...\n")
        completed = subprocess.run([sys.executable, "Updater.py"], cwd=HERE)
        if completed.returncode != 0:
            print("\nUpdater.py failed -- cannot test.")
            sys.exit(1)
        print()

    if not os.path.exists(DATA_FILE):
        print("data.json not found -- run Updater.py (or test.py --fresh).")
        sys.exit(1)

    data = load_data()
    print("Testing data.json (updated: %s)" % data.get("updated", "?"))

    results = Results()
    test_structure(data, results)
    test_ground_truth(data, results)
    test_films(data, results)

    if results.notices:
        print("\n[notices] potential new Star Trek content -- NOT failures:")
        for note in results.notices:
            print("  * %s" % note)
        print("  Tests still pass. Update ground_truth.json once you have "
              "confirmed the new content.")

    total = results.passed + results.failed
    print("\n" + "=" * 60)
    if results.failed:
        print("RESULT: %d/%d checks passed -- data.json has PROBLEMS."
              % (results.passed, total))
        sys.exit(1)
    suffix = ""
    if results.notices:
        suffix = " (%d notice%s)" % (
            len(results.notices), "" if len(results.notices) == 1 else "s")
    print("RESULT: %d/%d checks passed%s -- data.json is valid."
          % (results.passed, total, suffix))


if __name__ == "__main__":
    main()
