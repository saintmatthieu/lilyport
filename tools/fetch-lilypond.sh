#!/bin/sh
# Downloads an official LilyPond binary release into .tools/lilypond-<version>/
# (not installed system-wide). lilyport finds it there, or takes the one given
# by LILYPOND or on the PATH.
#
#   tools/fetch-lilypond.sh [version]     # default: the stable release below
set -eu
version=${1:-2.26.0}
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) platform=linux-x86_64; ext=tar.gz ;;
  Darwin-*) platform=darwin-x86_64; ext=tar.gz ;; # runs under Rosetta on Apple silicon
  *) echo "No LilyPond binary release for $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
root=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/.tools"
cd "$root/.tools"
if [ -x "lilypond-$version/bin/lilypond" ]; then
  echo "lilypond-$version already there"; exit 0
fi
archive="lilypond-$version-$platform.$ext"
curl -fL -o "$archive" \
  "https://gitlab.com/api/v4/projects/lilypond%2Flilypond/packages/generic/lilypond/$version/$archive"
tar -xzf "$archive"
rm "$archive"
"lilypond-$version/bin/lilypond" --version | head -1
