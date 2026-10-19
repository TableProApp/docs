#!/usr/bin/env bash
#
# The house style rules that a grep can settle, plus the UI vocabulary the app
# itself defines. Every rule here passes on the corpus today, so a failure is a
# regression rather than a backlog item.
#
# The banned filler comes from the app checkout's scripts/banned-words.txt, the
# list the app's own writing checks read, so both repos ban the same words. It
# matches case-insensitively at the start of a word.
#
#   scripts/check-writing-style.sh ../TablePro
#
# changelog.mdx is excluded throughout. It is 116 releases of shipped history and
# what 0.41.0's notes called a button cannot be rewritten now.

set -uo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $0 <path to a TablePro app checkout>" >&2
    exit 2
fi
BANNED_WORDS="$(cd "$1" && pwd)/scripts/banned-words.txt" || exit 2
cd "$(dirname "$0")/.." || exit 1

fail=0

report() {
    local name="$1" hits="$2"
    if [ -n "$hits" ]; then
        echo "FAIL  $name"
        echo "$hits" | sed 's/^/        /'
        fail=1
    else
        echo "  ok  $name"
    fi
}

check() {
    report "$1" "$(grep -rnE "$2" --include='*.mdx' --exclude=changelog.mdx . || true)"
}

check_ignoring_case() {
    report "$1" "$(grep -rniE "$2" --include='*.mdx' --exclude=changelog.mdx . || true)"
}

banned_filler_pattern() {
    local term alternatives=""
    while IFS= read -r term || [ -n "$term" ]; do
        case "$term" in
            [[:alnum:]]*) ;;
            *) continue ;;
        esac
        term="$(printf '%s' "$term" | sed -e 's/[[:space:]]*$//' -e 's/[][\.*^$+?(){}|/]/\\&/g')"
        alternatives="${alternatives:+$alternatives|}$term"
    done < "$BANNED_WORDS"
    printf '(^|[^[:alnum:]_-])(%s)' "$alternatives"
}

if [ ! -f "$BANNED_WORDS" ]; then
    echo "FAIL  banned filler: $BANNED_WORDS is missing"
    exit 1
fi

check "em dash" '—'
check_ignoring_case "banned filler" "$(banned_filler_pattern)"
check "hedge" '\b(simply|in order to|please note|and\/or)\b'
check "allows, enables, lets you" 'allows you to|enables you to|lets you|helps you'
check "British spelling" 'colour|behaviour|honour|recognis'
check "split menu path" '\*\*[^*]+\*\* > \*\*'
check "bold keyboard shortcut" '\*\*(Cmd|Ctrl|Option|Shift)\+'
check "modifier glyph" '[⌘⌥⇧⌃]'
check "greyed out" 'greyed out|grayed out'
check "welcome screen" '[a-z] welcome screen'
check "H4 heading" '^#### '
check "New Connection button" '\*\*New Connection\*\*'
check "filter panel" 'filter panel'

if [ "$fail" -ne 0 ]; then
    echo
    echo "The docs break the house style. See scripts/check-writing-style.sh."
    exit 1
fi

echo
echo "The docs match the house style."
