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
- `lilyport/model/` — the format-neutral event model (to write).
- `lilyport/writers/` — one module per output format (MusicXML first, to write).
- `tests/` — fixtures (small hand-written `.ly`, one feature each) and pytest.

## Conventions

- Python 3.10+; the runtime uses the standard library only (test dependencies
  in `[project.optional-dependencies] test`).
- `.ly` files carry the GPL-3.0-or-later header (`Copyright (C) <year>
  Matthieu Hodgkinson`, the year the file was written).
- Comments say why, in plain words; docstrings on modules and public functions.
- Commit directly on `main`, only the change's paths, with the
  `Co-Authored-By` trailer. No remote yet: don't push unless asked.

## Pitfalls met so far

- `make-engraver` inline listeners are `((note-event engraver event) body...)`;
  `(note-event . (lambda ...))` fails ("failed to match any pattern").
- `-dno-print-pages` runs the whole translation, engravers included, without
  writing a PDF; `-dbackend=null` doesn't exist. The listener only runs for a
  score with a `\layout` (a `\midi`-only score produces no events).
- The listener writes to `$LILYPORT_EVENTS` (environment), not via `-e` Scheme
  definitions (which depend on the module LilyPond evaluates them in).
- LilyPond 2.25+ deprecates `timeSignatureFraction` for `timeSignature`.
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
