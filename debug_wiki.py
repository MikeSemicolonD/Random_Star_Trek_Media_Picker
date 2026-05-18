"""
Diagnostic script - dumps the ACTUAL structure of the Wikipedia pages
so we can see how films and episodes are laid out.

Run:  python debug_wiki.py
Then paste the full output back.
"""
import wikipedia
from bs4 import BeautifulSoup


def dump_page(title):
    print("\n" + "=" * 70)
    print(f"PAGE: {title}")
    print("=" * 70)
    try:
        page = wikipedia.page(title, auto_suggest=False)
    except Exception as e:
        print(f"  Could not load page: {e}")
        return

    html = page.html()
    print(f"  HTML length: {len(html)} chars")
    print(f"  HTML is single-line blob: {html.count(chr(10)) < 5}")

    soup = BeautifulSoup(html, 'html.parser')

    # Show all tables and their classes
    tables = soup.find_all('table')
    print(f"\n  TABLES: {len(tables)} total")
    for i, t in enumerate(tables[:8]):
        classes = t.get('class', [])
        rows = t.find_all('tr')
        has_summary = len(t.select('td.summary'))
        print(f"    [{i}] class={classes} rows={len(rows)} td.summary cells={has_summary}")
        # Show first data row
        if len(rows) > 1:
            sample = rows[1].get_text(separator=' | ', strip=True)
            print(f"        row1: {sample[:120]}")

    # Show heading structure
    print(f"\n  HEADINGS (h2/h3):")
    for h in soup.find_all(['h2', 'h3'])[:25]:
        parent = h.parent
        parent_class = parent.get('class', []) if parent else []
        text = h.get_text(separator=' ', strip=True)
        print(f"    <{h.name}> parent=<{parent.name if parent else None} class={parent_class}>  text={text!r}")

    # For film page: what follows each film-era heading?
    print(f"\n  WHAT FOLLOWS EACH HEADING (next 3 elements in doc order):")
    for h in soup.find_all(['h2', 'h3'])[:20]:
        text = h.get_text(separator=' ', strip=True)
        if 'film' not in text.lower():
            continue
        print(f"    Heading: {text!r}")
        # Walk document order from the heading's wrapper
        start = h.parent if (h.parent and 'mw-heading' in h.parent.get('class', [])) else h
        count = 0
        for el in start.next_elements:
            if getattr(el, 'name', None) in ('p', 'ul', 'ol', 'table', 'div'):
                snippet = el.get_text(separator=' ', strip=True)[:90]
                print(f"        -> <{el.name} class={el.get('class', [])}> {snippet!r}")
                count += 1
                if count >= 3:
                    break


# Films
dump_page("List of Star Trek films")

# One episode list (to confirm episode table structure)
dump_page("List of Star Trek: The Original Series episodes")
