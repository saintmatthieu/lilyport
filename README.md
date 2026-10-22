# lilyport

Export LilyPond scores to MusicXML (and, later, other formats), checked
against LilyPond's own MIDI.

LilyPond has no MusicXML export, and converters that parse `.ly` text
(python-ly) can't follow what LilyPond evaluates: variables, music functions,
Scheme, `\relative`, repeats, several voices on a staff. lilyport lets LilyPond
do the evaluating: a listener loaded into LilyPond writes the music as events,
and Python assembles them into the output format.

**Status: early.** `lilyport dump` writes the event stream; the MusicXML
writer is next. See [docs/design.md](docs/design.md) for the design, the plan
and what has been found so far.

## Use

```sh
tools/fetch-lilypond.sh          # an official LilyPond release into .tools/
python3 -m lilyport dump piece.ly -o piece.events.jsonl
```

lilyport runs the LilyPond in `.tools/`, else `$LILYPOND`, else `lilypond` on
the PATH. Sources written for old LilyPond versions need `convert-ly` first.

## Tests

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

## Licence

GPL-3.0-or-later (the listener runs inside LilyPond, which is GPL-3).
Converted scores keep the licence of their source edition.
