# TablePro Docs

Source of [docs.tablepro.app](https://docs.tablepro.app), built with [Mintlify](https://mintlify.com). The app lives in [TableProApp/TablePro](https://github.com/TableProApp/TablePro).

## Local preview

```bash
npm ci
npm run dev
```

Preview at `http://localhost:3000`.

## Checks

CI runs these on every pull request and every push to `main`. The scripts read the app source, so they take a checkout of it:

```bash
npm run validate
npm run broken-links
npm run a11y
bash scripts/check-writing-style.sh ../TablePro
python3 scripts/check-links.py --app ../TablePro
```

`python3 scripts/check-docs-against-source.py --app ../TablePro` runs nightly against the app's `main` instead, and reports a failure as an issue here.

## Contributing

Read [STYLE.md](STYLE.md) before writing a page. A page that documents an app change is checked against the app's `main`, so open it alongside the app pull request and merge it after that one merges.

Report problems with the docs in [TablePro issues](https://github.com/TableProApp/TablePro/issues).

## Deployment

Mintlify deploys `main` through its GitHub app.

## History

This repository was split out of `docs/` in TableProApp/TablePro in October 2026 with its history kept. In commits from before the split, `#1234` refers to a pull request or issue in TableProApp/TablePro.

## License

The pages are covered by the [AGPLv3 license](LICENSE), like TablePro itself. The TablePro name and logo, including `logo/` and `favicon.png`, are trademarks of Ngo Quoc Dat and are not licensed under it. Screenshots of other products belong to their owners.
