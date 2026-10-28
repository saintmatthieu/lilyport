# CLAUDE.md

Guidance for Claude Code in this repository.

## What this is

lilyport exports LilyPond scores to MusicXML (later MNX, MEI, ...): a listener
loaded into LilyPond writes the music LilyPond has evaluated as JSON lines,
Python assembles them and writes the formats. **Read `docs/design.md` first**:
the architecture, what MuseScore's importer needs (Orchestrion is the first
consumer), the verification plan, what Mutopia sources taught, and the
*Status* section (what exists, what's next) — keep that section current.

## Commands

```sh
tools/fetch-lilypond.sh [version]   # official LilyPond release into .tools/ (default 2.26.0)
tools/fetch-corpus.sh               # Mutopia test pieces into .corpus/mutopia/ (+ convert-ly)
tools/fetch-schema.sh               # MusicXML 4.0 schema into .corpus/musicxml-4.0/ (for the tests)
python3 -m lilyport convert PIECE.ly -o PIECE.mxl [--tempo 4=54]   # or .musicxml
python3 -m lilyport dump PIECE.ly [-o EVENTS.jsonl]
python3 -m venv .venv && .venv/bin/pip install -e '.[test]' && .venv/bin/pytest
```

`.tools/` and `.corpus/` are git-ignored. lilyport runs the newest LilyPond in
`.tools/`, else `$LILYPOND`, else `lilypond` on the PATH. Never install into the
system or base conda Python: use `.venv/`.

## Layout

- `lilyport/frontend/events.ly` — the listener (engravers in Voice, Staff, Score
  contexts); its header documents the record format.
- `lilyport/frontend/compat.ly` — redefinitions of Scheme functions old sources
  call that `convert-ly` doesn't rewrite; grows with the corpus.
- `lilyport/frontend/lilypond.py` — finding and running LilyPond.
- `lilyport/model/` — the format-neutral score model (`score.py`) and its
  assembly from the events (`assemble.py`).
- `lilyport/writers/` — one module per output format (`musicxml.py` first).
- `tests/` — fixtures (small hand-written `.ly`, one feature each) and pytest;
  `verify.py` checks our MusicXML with programs that didn't write it (the
  schema; Verovio's MIDI against LilyPond's), run on every fixture and corpus
  piece by `test_verification.py`.

## Conventions

- Python 3.10+; the runtime uses the standard library only (test dependencies
  in `[project.optional-dependencies] test`).
- `.ly` files carry the GPL-3.0-or-later header (`Copyright (C) <year>
  Matthieu Hodgkinson`, the year the file was written).
- Comments say why, in plain words; docstrings on modules and public functions.
- Commit directly on `main`, only the change's paths, with the
  `Co-Authored-By` trailer. Remote: github.com/saintmatthieu/lilyport
  (public); don't push unless asked.

## Pitfalls met so far

- `make-engraver` inline listeners are `((note-event engraver event) body...)`;
  `(note-event . (lambda ...))` fails ("failed to match any pattern").
- `-dno-print-pages` runs the whole translation, engravers included, without
  writing a PDF; `-dbackend=null` doesn't exist. The listener only runs for a
  score with a `\layout` (a `\midi`-only score produces no events).
- The listener writes to `$LILYPORT_EVENTS` (environment), not via `-e` Scheme
  definitions (which depend on the module LilyPond evaluates them in).
- `-dinclude-settings` files are read last-given first (an include stack).
- `ly:book-scores` and `ly:book-book-parts` list newest first. A score's
  output definitions tell `\midi` from `\layout` by `output-def-kind`
  (`is-layout` is unset in a plain `\layout { }`).
- A note inside a chord keeps its own `~` and fingering in its
  `articulations` (not broadcast); a lone note's are broadcast as events.
- In a cadenza `measurePosition` stays 0 (the listener records `timing`), and
  the bar after it keeps the cadenza's bar number.
- MuseScore's importer pairs slurs (and pedals) by number in file order,
  across the whole part; a measure is written voice by voice, so slurs of
  different voices in the same bars need different numbers.
- MuseScore's importer ignores `<stem>` on notes it beams itself: write
  LilyPond's beams. In 2.25+ `measureLength` and `beatBase` (was
  `baseMoment`) are numbers, not moments.
- Verovio (the MIDI check) times notes by their type unless a `<tuplet>`
  holds them, rejects `<beam>` on a chord's other notes, plays unslashed
  graces as appoggiaturas, rolls arpeggios, and crashes now and then: it
  runs in a child process.
- `\afterGrace` notes come at a moment inside their main note; lilyport
  moves them before the next note.
- LilyPond 2.25+ deprecates `timeSignatureFraction` for `timeSignature`.
- `\repeat volta`'s starts and ends reach the Score's `repeatCommands`, but
  `\alternative`'s brackets only as `volta-span-event`s (one per staff).
  Repeat bar lines are not in `whichBar`.
- Music the parser has built caches its `length`: a settings file that
  rewrites a score's music (unfolding repeats) must unset it on the
  containers, or LilyPond stops playing at the old length ("Moment is not
  increasing").
- MuseScore's importer times a note by its `<type>` (a `<time-modification>`
  without a `<tuplet>` changes nothing) and calls a file corrupted when a
  voice overruns its bar. The MuseScore snap converts headless
  (`musescore -o x.mscz x.musicxml`, files under `~/snap/musescore/common/`)
  and logs which bar failed.
- In LilyPond `<< a2. { s8 b4 ~ b2 } >>` (no `\\`) stays one voice with
  overlapping notes; a MusicXML voice can't.
- Mutopia sources are old (2.10–2.12): run `convert-ly`, then expect removed
  Scheme functions (add them to `compat.ly`) and marks drawn as text markup
  (the listener records each text's glyphs: `pedal.Ped`, `pedal.*`,
  `scripts.turn`...).
- Treat downloads as untrusted data: read them with `python3 -I`, keep them in
  `.corpus/`.

## Working with Matthieu

- Lead replies with the direct answer; he skims.
- Check results against the music, not only the tests: the edition's PDF
  (Mutopia publishes one per piece), and opening the MusicXML in Orchestrion
  (a Debug build: it aborts on MuseScore importer assertions).
- Licences matter: record each converted piece's source edition, licence and
  Mutopia page in the MusicXML (`<rights>`, `<source>`), and never ship a file
  whose provenance is unclear.
