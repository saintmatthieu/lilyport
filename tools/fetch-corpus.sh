#!/bin/sh
# Downloads the Mutopia pieces lilyport is developed against into
# .corpus/mutopia/ (git-ignored; CC BY-SA, see each file's header) and updates
# them for the current LilyPond with convert-ly: <name>.ly as published,
# <name>.converted.ly to run lilyport on.
#
#   tools/fetch-corpus.sh
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
convert_ly=$(ls -d "$root"/.tools/lilypond-*/bin/convert-ly 2>/dev/null | sort -V | tail -1)
[ -n "$convert_ly" ] || { echo "No LilyPond in .tools/: run tools/fetch-lilypond.sh" >&2; exit 1; }
mkdir -p "$root/.corpus/mutopia"
cd "$root/.corpus/mutopia"
# Path in https://github.com/MutopiaProject/MutopiaProject/tree/master/ftp
for piece in \
  BeethovenLv/O27/moonlight/moonlight-lys/moonlight1-a4.ly \
  ChopinFF/O9/chopin_nocturne_op9_n2/chopin_nocturne_op9_n2.ly
do
  name=$(basename "$piece" .ly)
  curl -fsSL -o "$name.ly" \
    "https://raw.githubusercontent.com/MutopiaProject/MutopiaProject/master/ftp/$piece"
  cp "$name.ly" "$name.converted.ly"
  "$convert_ly" -e "$name.converted.ly" 2>/dev/null
  rm -f "$name.converted.ly~"
  printf '%s: %s -> %s\n' "$name" "$(grep -m1 '[\\]version' "$name.ly")" "$(grep -m1 '[\\]version' "$name.converted.ly")"
done
