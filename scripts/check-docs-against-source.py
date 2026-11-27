#!/usr/bin/env python3
"""Fail when the docs assert something about the app that the source contradicts.

Three classes of claim rot faster than anything else in docs, and all three shipped
wrong at once in August 2026: a menu path after the Database menu took commands off
View and Query, a keyboard shortcut after the filter bar moved to Cmd+Option+F, and
the PluginKit ABI number after a breaking bump. Each is mechanically checkable
against the source that defines it, so none of them should ever need a human to
notice.

    python3 scripts/check-docs-against-source.py --app ../TablePro
"""

import argparse
import collections
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

MENU_FILES = {
    "TablePro": "AppMenuBuilder.swift",
    "File": "FileMenuBuilder.swift",
    "Edit": "EditMenuBuilder.swift",
    "View": "ViewMenuBuilder.swift",
    "Database": "DatabaseMenuBuilder.swift",
    "Query": "QueryMenuBuilder.swift",
    "Window": "WindowMenuBuilder.swift",
    "Help": "HelpMenuBuilder.swift",
}

# Leaves a builder takes from another file: File > Import lists ImportCommand's titles.
MENU_EXTRA_FILES = {
    "File": ["ImportCommand.swift"],
}

# A page under windows/ describes the Windows app, whose menu bar is MainWindow.xaml with its titles in the
# en-US resources, keyed by each item's x:Uid.
WINDOWS_APP = Path("windows") / "src" / "TablePro.App"
XAML_UID = "{http://schemas.microsoft.com/winfx/2006/xaml}Uid"

# A leaf the docs name that the menu builders cannot define, because something else
# builds it: AppKit's own items, a submenu filled at runtime from the server, or a
# contextual menu that happens to read like a menu path.
# The shortcuts page words some rows differently from the action name in Settings >
# Keyboard. Each alias joins a documented row to the case that binds it, so the chord
# is still checked. A row with no alias and no exact title match is reported as
# unchecked rather than passing silently.
SHORTCUT_ALIASES = {
    "Toggle filter bar (table tab)": "toggleFilters",
    "Toggle sidebar": "toggleTableBrowser",
    "Toggle inspector": "toggleInspector",
    "Toggle history": "toggleHistory",
    "Toggle results": "toggleResults",
    "Find": "find",
    "Jump to column": "jumpToColumn",
    "Export tables": "export",
    "Export results": "exportResults",
}

RUNTIME_LEAVES = {
    "Table Maintenance",
    "Schema",
    "Services",
}


# The style guide drops a trailing ellipsis when the sentence instructs, the Windows app's
# three periods too, and AppKit flips a Show item to Hide once its pane is open.
def leaf_forms(leaf: str) -> set[str]:
    def bare(text: str) -> str:
        return text.removesuffix("...").rstrip("…").rstrip()

    forms = {leaf, bare(leaf)}
    for a, b in (("Show ", "Hide "), ("Hide ", "Show ")):
        if leaf.startswith(a):
            flipped = b + leaf[len(a):]
            forms |= {flipped, bare(flipped)}
    return forms


DOCS = Path(__file__).resolve().parent.parent


# The macOS app's folder. The Windows menu bar is read from the checkout beside it.
def app_root(path: str) -> Path:
    root = Path(path).resolve() / "apple"
    if not (root / "TablePro" / "Core" / "Menu").is_dir():
        sys.exit(f"{path} is not a TablePro app checkout: it has no apple/TablePro/Core/Menu")
    return root


def localized_strings(path: Path) -> set[str]:
    return set(re.findall(r'String\(localized:\s*"((?:[^"\\]|\\.)*)"', path.read_text()))


def doc_pages(docs: Path) -> list[Path]:
    return [p for p in sorted(docs.rglob("*.mdx")) if p.name != "changelog.mdx"]


def windows_menus(checkout: Path) -> dict[str, set[str]]:
    app = checkout / WINDOWS_APP
    resources = {
        data.get("name"): data.findtext("value", "")
        for data in ET.parse(app / "Strings" / "en-US" / "Resources.resw").getroot().iter("data")
    }
    menus = {}
    for bar_item in ET.parse(app / "MainWindow.xaml").getroot().iter():
        if bar_item.tag.rsplit("}", 1)[-1] != "MenuBarItem":
            continue
        forms: set[str] = set()
        for item in bar_item.iter():
            text = resources.get(f"{item.get(XAML_UID)}.Text") if item is not bar_item else None
            if text:
                forms |= leaf_forms(text)
        menus[resources.get(f"{bar_item.get(XAML_UID)}.Title", "")] = forms
    return menus


def check_menu_paths(root: Path, docs: Path) -> list[str]:
    menu_dir = root / "TablePro" / "Core" / "Menu"
    mac = {}
    for menu, file in MENU_FILES.items():
        forms: set[str] = set()
        for leaf in localized_strings(menu_dir / file):
            forms |= leaf_forms(leaf)
        # A missing extra file only drops its leaves, which then fail as unknown.
        for extra in MENU_EXTRA_FILES.get(menu, []):
            if (menu_dir / extra).is_file():
                for leaf in localized_strings(menu_dir / extra):
                    forms |= leaf_forms(leaf)
        mac[menu] = forms
    windows = windows_menus(root.parent)

    failures = []
    names = sorted(set(mac) | set(windows))
    pattern = re.compile(r"\*\*(" + "|".join(map(re.escape, names)) + r") > ([^*]+)\*\*")
    for page in doc_pages(docs):
        relative = page.relative_to(docs)
        if relative.parts[0] == "windows":
            per_menu, source = windows, "the Windows menu bar"
        else:
            per_menu, source = mac, "any builder"
        for line_no, line in enumerate(page.read_text().splitlines(), start=1):
            for menu, tail in pattern.findall(line):
                leaf = tail.split(" > ")[-1].strip()
                if leaf in RUNTIME_LEAVES or leaf in per_menu.get(menu, ()):
                    continue
                where = f"{relative}:{line_no}"
                owner = next((m for m, forms in per_menu.items() if leaf in forms), None)
                if owner:
                    failures.append(f"{where}: **{menu} > {leaf}** lives on the {owner} menu")
                else:
                    failures.append(f"{where}: **{menu} > {leaf}** is not a menu item in {source}")
    return failures


def check_shortcuts(root: Path, docs: Path) -> list[str]:
    models = root / "TablePro" / "Models" / "UI" / "KeyboardShortcutModels.swift"
    source = models.read_text()

    titles = dict(
        re.findall(r'case \.(\w+):\s*return String\(localized:\s*"([^"]+)"\)', source)
    )
    bindings = {}
    for case, args in re.findall(r"\.(\w+):\s*\.character\(([^)]*)\)", source):
        key = re.match(r'"([^"]+)"', args.strip())
        if not key:
            continue
        chord = {
            label
            for modifier, label in (
                ("control", "Ctrl"),
                ("option", "Option"),
                ("shift", "Shift"),
                ("command", "Cmd"),
            )
            if re.search(modifier + r":\s*true", args)
        }
        literal = key.group(1)
        chord.add(literal.upper() if len(literal) == 1 else literal)
        bindings[case] = frozenset(chord)

    documented = {}
    table_row = re.compile(r"^\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|")
    shortcuts_page = docs / "features" / "keyboard-shortcuts.mdx"
    for line_no, line in enumerate(shortcuts_page.read_text().splitlines(), start=1):
        row = table_row.match(line)
        if row:
            documented.setdefault(row.group(1).strip(), (row.group(2).strip(), line_no))

    by_title = {title: case for case, title in titles.items()}
    for label, case in SHORTCUT_ALIASES.items():
        by_title.setdefault(label, case)

    failures = []
    checked = 0
    for label, (written, line_no) in documented.items():
        case = by_title.get(label)
        if case is None or case not in bindings:
            continue
        checked += 1
        if frozenset(written.split("+")) != bindings[case]:
            order = ["Ctrl", "Option", "Shift", "Cmd"]
            chord = bindings[case]
            spelled = "+".join(
                [m for m in order if m in chord] + sorted(chord - set(order))
            )
            failures.append(
                f"features/keyboard-shortcuts.mdx:{line_no}: {label} is documented as "
                f"`{written}`, the app binds the chord {spelled}"
            )
    print(f"      {checked} of {len(documented)} documented rows joined to a binding")

    spellings = collections.Counter()
    for page in doc_pages(docs):
        for line_no, line in enumerate(page.read_text().splitlines(), start=1):
            for chord in re.findall(r"`((?:Cmd|Ctrl|Option|Shift)\+[A-Za-z0-9+]+)`", line):
                for key, canonical in (("Return", "Enter"), ("Esc", "Escape"), ("Del", "Delete")):
                    if chord.endswith("+" + key):
                        spellings[(key, canonical)] += 1
                        failures.append(
                            f"{page.relative_to(docs)}:{line_no}: `{chord}` spells the key {key}; "
                            f"the corpus spells it {canonical}"
                        )
    return failures


def check_pluginkit_version(root: Path, docs: Path) -> list[str]:
    config = (root / "Configs" / "PluginKit.xcconfig").read_text()
    current = re.search(r"^TABLEPRO_PLUGINKIT_VERSION\s*=\s*(\d+)\s*$", config, re.M)
    if not current:
        return ["apple/Configs/PluginKit.xcconfig no longer sets TABLEPRO_PLUGINKIT_VERSION"]
    expected = current.group(1)

    failures = []
    claim = re.compile(
        r"(?:TableProPluginKitVersion|\bpluginKitVersion|currentPluginKitVersion|"
        r"minimumCompatiblePluginKitVersion)\D*?\b(\d{1,3})\b"
    )
    example = re.compile(r"v\d+\.\d+\.\d+:\d+")
    for page in doc_pages(docs / "development"):
        for line_no, line in enumerate(page.read_text().splitlines(), start=1):
            for found in claim.findall(example.sub("", line)):
                if found != expected:
                    failures.append(
                        f"{page.relative_to(docs)}:{line_no}: PluginKit version {found}, "
                        f"the app ships {expected}"
                    )
    return failures


def check_changelog_parity(root: Path, docs: Path) -> list[str]:
    """Every release in CHANGELOG.md must appear on the changelog page.

    The app's apple/scripts/release/notes.py docs writes each stable's block from its CHANGELOG.md
    section. The check stays one-way: the page may carry a version the file does not, which is
    how 0.39.0 is documented. It shipped, failed to launch with errno 163, and 0.39.1 replaced it
    the same day.
    """
    shipped = set(
        re.findall(r"^## \[([0-9][^\]]*)\]", (root / "CHANGELOG.md").read_text(), re.M)
    )
    documented = set(
        re.findall(r'<Update label="v?([^"]+)"', (docs / "changelog.mdx").read_text())
    )
    missing = sorted(shipped - documented)
    return [
        f"changelog.mdx: {version} is in CHANGELOG.md and not on the page"
        for version in missing
    ]


def check_changelog_anchors(root: Path, docs: Path) -> list[str]:
    """An Update's label is its anchor and its RSS title, so it has to be unique.

    Dated labels collided on 22 days across 49 releases, which left no release on the
    page linkable and every feed item titled with a date instead of a version.
    """
    labels = re.findall(r'<Update label="([^"]*)"', (docs / "changelog.mdx").read_text())
    seen, repeated = set(), set()
    for label in labels:
        if label in seen:
            repeated.add(label)
        seen.add(label)
    return [f"changelog.mdx: label {label!r} is used more than once" for label in sorted(repeated)]


DOC_NAMES = {
    "SQL Server": "Microsoft SQL Server",
    "Oracle": "Oracle Database",
    "Dameng": "Dameng DM8",
    "Redshift": "Amazon Redshift",
}


def registered_databases(root: Path) -> dict:
    """Every database type the chooser offers, with its default port.

    The registry builds these as ("TypeId", PluginMetadataSnapshot(... defaultPort: N ...)) tuples,
    spread over PluginMetadataRegistry.swift and its +*Defaults.swift extensions. A new engine adds
    one tuple, so counting them is how the docs learn the engine exists.
    """
    found = {}
    for path in sorted((root / "TablePro/Core/Plugins").glob("PluginMetadataRegistry*.swift")):
        source = path.read_text()
        for match in re.finditer(r'\(\s*"([^"]+)",\s*PluginMetadataSnapshot\(', source):
            tail = source[match.end():match.end() + 1500]
            port = re.search(r"defaultPort:\s*([0-9_]+)", tail)
            found[match.group(1)] = int(port.group(1).replace("_", "")) if port else None
    return found


def check_database_table(root: Path, docs: Path) -> list[str]:
    registered = registered_databases(root)
    if len(registered) < 20:
        return ["could not read the database types out of PluginMetadataRegistry"]

    page = docs / "databases/index.mdx"
    rows = {}
    for name, port in re.findall(r"^\| \[([^\]]+)\]\([^)]+\) \| ([^|]+?) \|", page.read_text(), re.M):
        rows[name.strip()] = port.strip()

    failures = []
    expected = {DOC_NAMES.get(name, name) for name in registered}
    for missing in sorted(expected - set(rows)):
        failures.append(f"databases/index.mdx has no row for {missing}, which the chooser offers")
    for extra in sorted(set(rows) - expected):
        failures.append(f"databases/index.mdx lists {extra}, which is not a registered type")

    for type_id, port in registered.items():
        row = rows.get(DOC_NAMES.get(type_id, type_id))
        if row is None or port in (None, 0):
            continue
        if str(port) not in row:
            failures.append(
                f"databases/index.mdx gives {type_id} port {row}, the registry says {port}"
            )

    return failures


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
for _tens_word, _tens in (("twenty", 20), ("thirty", 30), ("forty", 40)):
    NUMBER_WORDS[_tens_word] = _tens
    for _unit_word, _unit in list(NUMBER_WORDS.items())[:9]:
        NUMBER_WORDS[f"{_tens_word}-{_unit_word}"] = _tens + _unit

ENGINE_COUNT = re.compile(
    r"\b(\d+|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\s+engines\b",
    re.IGNORECASE,
)


def spelled(text: str) -> Optional[int]:
    return int(text) if text.isdigit() else NUMBER_WORDS.get(text.lower())


def unwrapped(page: Path) -> str:
    """A page as one line, so a sentence wrapped at 100 columns still matches."""
    return " ".join(page.read_text().split())


def check_engine_counts(root: Path, docs: Path) -> list[str]:
    """Every engine count printed in the docs, against the registry that defines it.

    The count lived on three pages and the marketing site with nothing reconciling them, so
    they drifted to 27, 27 and 25 while the app offered 28. STYLE.md 9 gives the count one
    owner, `snippets/driver-counts.mdx`; this is what makes that hold.

    `changelog.mdx` is exempt. Its entries state what a past release shipped.
    """
    total = len(registered_databases(root))
    if total < 20:
        return ["could not read the database types out of PluginMetadataRegistry"]

    failures = []
    for page in sorted(docs.rglob("*.mdx")):
        if page.name == "changelog.mdx":
            continue
        name = page.relative_to(docs)
        for match in ENGINE_COUNT.finditer(unwrapped(page)):
            counted = spelled(match.group(1))
            if counted is not None and counted != total:
                failures.append(f"{name} says {match.group(1)} engines, the registry has {total}")

    failures += check_driver_split(docs, total)
    failures += check_introduction_description(docs, total)
    return failures


def check_driver_split(docs: Path, total: int) -> list[str]:
    """The bundled and registry halves in the shared snippet have to add up to the whole.

    They did not: nine bundled databases plus eighteen registry *plugins* reads as 27 engines,
    because the two numbers count different things.
    """
    text = unwrapped(docs / "snippets/driver-counts.mdx")
    bundled = re.search(r"cover (\w+) databases", text)
    registry = re.search(r"the other ([\w-]+)", text)
    if not bundled or not registry:
        return ["snippets/driver-counts.mdx no longer states a bundled and a registry count"]

    halves = [spelled(bundled.group(1)), spelled(registry.group(1))]
    if None in halves:
        return ["snippets/driver-counts.mdx states a count this script cannot read"]
    if sum(halves) != total:
        return [
            f"snippets/driver-counts.mdx splits the engines {halves[0]} + {halves[1]}, "
            f"the registry has {total}"
        ]
    return []


def check_introduction_description(docs: Path, total: int) -> list[str]:
    """`index.mdx` names five engines in its frontmatter and counts the rest.

    Mintlify prints the description as page metadata, where no snippet can reach, so this is
    the one count that has to be typed twice and the one that needs checking directly.
    """
    text = (docs / "index.mdx").read_text()
    description = re.search(r"^description:\s*(.+)$", text, re.M)
    if not description:
        return ["index.mdx has no frontmatter description"]

    more = re.search(r"^(.*?) for (.+?),? and (\d+) more\b", description.group(1))
    if not more:
        return []

    named = len([part for part in more.group(2).split(",") if part.strip()])
    if named + int(more.group(3)) != total:
        return [
            f"index.mdx names {named} engines and {more.group(3)} more, the registry has {total}"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app", required=True, help="path to a TablePro app checkout")
    root = app_root(parser.parse_args().app)
    docs = DOCS

    checks = (
        ("menu paths", check_menu_paths),
        ("keyboard shortcuts", check_shortcuts),
        ("PluginKit version", check_pluginkit_version),
        ("changelog parity", check_changelog_parity),
        ("changelog anchors", check_changelog_anchors),
        ("database table", check_database_table),
        ("engine counts", check_engine_counts),
    )

    total = 0
    for label, check in checks:
        failures = check(root, docs)
        total += len(failures)
        mark = "FAIL" if failures else "ok"
        print(f"{mark:>4}  {label}")
        for failure in failures:
            print(f"        {failure}")

    if total:
        print(f"\n{total} claim(s) in the docs contradict the source.")
        return 1
    print("\nThe docs agree with the source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
