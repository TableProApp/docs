# TablePro Docs

The Mintlify source of [docs.tablepro.app](https://docs.tablepro.app). The app is [TableProApp/TablePro](https://github.com/TableProApp/TablePro); the checks here read its source, and expect a checkout at `../TablePro`.

Claude Code loads this file through `CLAUDE.md`; Codex loads it directly.

## Repository map

- `docs.json`: navigation, redirects, theme, analytics. A page in no navigation group fails `scripts/check-links.py`.
- `*.mdx` and the topic directories: the pages. `changelog.mdx` is the release history.
- `snippets/`: a fact two pages share lives here once. See `STYLE.md` 9.
- `images/`: screenshots, each a light and dark pair.
- `consent.js`: Mintlify loads every `.js` file in the repository on every page. Add no other.
- `scripts/`: the three checks CI runs, `make-placeholder.py` for a shot not taken yet, `proper-nouns.txt` for the heading-case check.
- `STYLE.md`: the spec for every page.

## Commands

```bash
npm ci
npm run dev                                                    # preview at localhost:3000
npm run validate && npm run broken-links && npm run a11y
python3 scripts/check-docs-against-source.py --app ../TablePro # menu paths, shortcuts, engine counts, changelog parity
bash scripts/check-writing-style.sh ../TablePro                # house style; banned words come from the app
python3 scripts/check-links.py --app ../TablePro               # links, navigation, and the app's links into this site
```

Run the three scripts against an app checkout at the `main` the change describes. CI checks out the app's `main`.

## Writing a page

- **Read `STYLE.md` before writing.**
- **Write against the app's `main`, or re-check every claim against its source right before committing.** Capability tables, supported-engine lists and default values go stale when a later app commit changes the code.
- **What the scripts cannot catch:** a first sentence that repeats the frontmatter `description`; `alt` text identical to the `<Frame>` caption; design rationale aimed at the reader; the product as the subject of a sentence instead of the reader's task; "you can"; a bold label used as a heading; prose that repeats the table above it; a callout the page is wrong without.
- **A page that shows UI carries a light and dark screenshot pair** (`images/<name>.png` and `<name>-dark.png`) in a `<Frame>`.
- **No competitor is named in the docs.**
- **Renaming or removing a page adds a redirect in `docs.json`.** The app links here from the Help menu, the plugin registry and the release notes; `check-links.py --app` fails on any of those that stops resolving.

## Working with the app repository

- **A change that documents an app change** opens as a draft pull request whose description names the app pull request (`TableProApp/TablePro#1234`). CI checks against the app's `main`, so it goes green once the app pull request merges; mark it ready then.
- **The daily run** catches an app change that broke a claim here. Fix the page, not the check.
- **Releases.** For each stable release, the app's `release` skill opens a `docs(changelog): vX.Y.Z` pull request whose `<Update>` block in `changelog.mdx` is written by the app's `apple/scripts/release/notes.py docs`, and merges it once the release is published. Every version in the app's `apple/CHANGELOG.md` must be on that page.

## Writing style

Short sentences, plain words, specific numbers and names. No em dashes, no filler. The app's `scripts/banned-words.txt` is the list.

## Commits and pull requests

Squash merges use the pull request title as the commit subject. Conventional Commits, at most 72 characters: `docs(<area>): <description>` for pages, `ci:` or `chore:` for tooling. Areas are the top-level directories (`features`, `databases`, `connections`, `developers`, `integrations`, `customization`, `development`, `ios`, `security`) and `changelog`.
