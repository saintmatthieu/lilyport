# lilyport — design

Getting music out of LilyPond: one LilyPond front end, one format-neutral
event model, a writer per format — **MusicXML first**. Started from the
handover of 2026-10-21 (Orchestrion session); kept up to date as the project
goes. See *Status* at the end for what exists.

**Name: `lilyport`** — *export* from LilyPond, *porting* music to other formats.
Chosen over format-specific names (`ly2mxl`, `lilyxml`, ...) because the tool
is one LilyPond front end with a writer per format.

## Why

Orchestrion (`~/github/saintmatthieu/Orchestrion`) ships example scores in `scores/`
and needs more, with clean licences. On 2026-10-21 two bundled scores turned out to be
musescore.com uploads marked **"All rights reserved"** (Chopin Nocturne Op. 9 No. 2,
from musescore.com/score/2293506; Beethoven Moonlight Sonata 1st mvt, from
musescore.com/classicman/scores/55352). The compositions are public domain, the
transcriptions are not. They are to be removed from Orchestrion and replaced by
freely licensed editions.

The Mutopia Project has ~2,000 public-domain / CC-licensed editions as LilyPond
sources (with PDFs and MIDI), but no MusicXML. A converter would make that corpus,
and any LilyPond source, usable — a good return on investment beyond these two pieces.

## State of the art (checked 2026-10-21)

- **LilyPond itself** has no MusicXML export. Its `musicxml2ly` goes the other way.
- **python-ly** (`ly musicxml piece.ly`, the Frescobaldi library) is the only direct
  converter. Its MusicXML export is still labelled experimental and has barely moved:
  steady work 2014–2016, a batch of fixes in 0.9.6 (2020), then two bug fixes in
  0.9.10 (2026-04-04: lost measure boundaries with chords, #183; empty-list crash, #184).
  Licence GPL-3.0-or-later since 0.9.10.
  - **Structural ceiling:** it parses `.ly` *text* into its own tree (`ly.music`)
    without running LilyPond, so every LilyPond semantic — variables, music functions,
    Scheme, `\include`d stylesheets, `\relative` subtleties, `\repeat`, multi-voice
    staves — has to be re-implemented, and is only approximated. Mutopia files are full
    of these. Patching python-ly is not the recommended path.
- **openLilyLib's `lilypond-export`** (https://github.com/openlilylib/lilypond-export,
  Jan-Peter Voigt, GPL-3.0) is **prior art for the architecture proposed below**: Scheme
  (`api.scm`, `lily.scm`, `MusicXML.scm`, `Humdrum.scm`) that exports MusicXML 3.0 and
  Humdrum from the music LilyPond has evaluated, without typesetting
  (`\layout { \FileExport #opts }`, `opts.exporter = #exportMusicXML`). Its README calls it
  "pre-alpha", "far from production-ready", handling "very simple scores". Last commit
  2023-10-17; 5 open issues (incl. #29 failing on LilyPond 2.24.0, #14 grace notes at
  moment 0 landing in the previous bar, #28 stem-direction Scheme error) and 5 open PRs.
  Depends on openLilyLib's `oll-core`.
  - **Read its `MusicXML.scm` / `api.scm` first** — how it walks the evaluated music
    and what broke on 2.24 will save time. Same licence, so code can be borrowed with
    credit. What `lilyport` adds: Python assembly of the output, the MIDI round-trip
    check, the Mutopia corpus run, current LilyPond versions, no `oll-core` dependency.
- **`ly2mxl`** was mentioned as existing; it is not on PyPI and the GitHub topic has no
  public repositories (2026-10-21) — find out what it is before starting.
- `lasconic/lilypond_export` is unrelated (a MuseScore 1.2 plugin going MusicXML → LilyPond).
- `uliska/ly2xml` is a stub pointing at python-ly.

Sources: https://github.com/frescobaldi/python-ly/blob/master/CHANGELOG.md ,
https://python-ly.readthedocs.io/en/latest/_modules/ly/musicxml.html ,
https://github.com/uliska/ly2xml , https://github.com/lasconic/lilypond_export

## Architecture

**Let LilyPond do the parsing; export what it has evaluated.**

1. **Scheme side (inside LilyPond).** After LilyPond has evaluated the input, every
   variable, function, `\relative`, transposition etc. is resolved, and the translation
   step sends a stream of *music events* per context (Staff / Voice): notes with spelled
   pitch and duration, rests, ties, grace notes, tuplets, articulations and ornaments,
   dynamics, hairpins, slurs, sustain pedal, tempo, key/time/clef changes, bar checks.
   LilyPond's own MIDI output is built from this same layer, which is the evidence it
   holds everything a performance needs.
   - Implement as a listener/engraver (Scheme) loaded with `-dinclude-settings` /
     `--include` or a `-e` expression, writing one record per event (JSON lines or
     TSV) with: context path (score/staff/voice ids), moment (bar number + position in
     bar, from `currentBarNumber` / `measurePosition`), grace offset, event class and
     properties.
   - LilyPond ships `ly/event-listener.ly` (for Vivi, the Virtual Violinist):
     tab-separated MIDI pitches per staff. Ours (`lilyport/frontend/events.ly`)
     follows its approach with spelled pitches, contexts, bar positions, JSON lines.
   - `-dno-print-pages` runs the whole translation (engravers included) and
     writes no PDF. (`-dbackend=null` is no option.) The listener is loaded with
     `-dinclude-settings`, so it needs a `\layout` in the score — a score
     with only `\midi` produces no events (to handle: add a `\layout`).
2. **Python side, in two layers.**
   - **Event model** (format-neutral): read the dump and build parts → staves →
     voices → measures, with notes, ties, tuplets, grace groups, markings, repeat
     structure and metadata. This is the project's core and its stable interface;
     keep it free of any one format's vocabulary.
   - **Writers**, one per format, each reading only the event model. The first is
     **MusicXML 4.0 `score-partwise`**, compressed as `.mxl` (`zipfile` +
     `META-INF/container.xml`) or plain `.musicxml`.
   Standard library only (`xml.etree`, `zipfile`, `json`). Fallback if
   measure/voice/tuplet assembly gets hairy: `music21` (BSD), but it is a heavy
   dependency — avoid unless needed.

### Known hard parts

- **Repeats and voltas must stay repeats** (Orchestrion needs the structure, not an
  unfolded pass). The event stream plays a `\repeat volta` once; repeat bar lines and
  volta brackets surface as context property changes (`repeatCommands`) — listen for
  those, or read the `RepeatedMusic` expression before iteration. `\repeat unfold`
  should come out unfolded.
- **Grace notes** have zero main duration and a grace offset; MusicXML wants
  `<grace/>` notes before the main note, slash for acciaccaturas.
- **Tuplets** (incl. odd groupings in Chopin-style runs) → `<time-modification>` +
  `<tuplet>` start/stop.
- **Multiple voices on one staff** and **cross-staff notes** (`\change Staff`) →
  MusicXML `<voice>` numbers and `<staff>` per note, `<backup>`/`<forward>`.
- **Ties across bar lines** come from LilyPond already split per notated note, which
  helps; check that `~` across `\bar` survives.
- **Beaming** is computed at engraving time; MuseScore re-beams on import anyway, so
  emitting no `<beam>` is acceptable at first.
- **Partial first measure** (`\partial`) → MusicXML implicit measure / measure number 0.
- **Chord names, lyrics, figured bass**: out of scope at first (Orchestrion ignores them).

## Formats

The front end (LilyPond + Scheme listener) and the event model are shared; each format
is a writer. Order of work:

| Format | Extension | What / why | When |
|---|---|---|---|
| **MusicXML 4.0** | `.mxl`, `.musicxml` | The interchange standard every notation program imports; Orchestrion's input | First |
| **Event dump (JSON)** | `.json` | The documented event model itself — useful for analysis / ML, and what the writers read anyway | Comes free with the core; document it |
| **MNX** | `.mnx` (JSON) | MusicXML's designated successor (W3C Music Notation CG), cleaner semantics; 1.0 being finalised. MuseScore has an MNX importer (in Orchestrion's `MuseScore.cmake` list, switched off) | Next — future-proofing |
| **MEI** | `.mei` | Music Encoding Initiative, the scholarly standard; Verovio's native format; MuseScore 4 imports it | Later |
| **Humdrum `**kern`** | `.krn` | Computational musicology (music21, KernScores); `lilypond-export` already writes it | Later |
| **ABC** | `.abc` | Text format of folk / traditional music; simple to write | Later, if asked for |

Design rule: anything a writer needs that the event model lacks goes into the model
(and the Scheme dump if needed), not into a writer-specific side channel. The
verification below is per format; MusicXML's is specified in detail, the others reuse
the MIDI diff (Verovio reads MEI natively, and MusicXML/MNX via conversion).

## What Orchestrion needs from a score (priority order)

Orchestrion imports MusicXML through MuseScore (its fork is in
`~/github/saintmatthieu/MuseScore`), and plays the score note by note from a gesture
controller. What matters, roughly by importance:

1. Notes, rests, durations, voices, staves (piano: two staves, one part), ties.
2. Key, time, clef changes; pickup bars; repeats/voltas kept as structure.
3. Grace notes, tuplets.
4. Ornaments: trill, mordent, inverted mordent, turn (Orchestrion plays them — see
   Orchestrion's `testscores/ornaments-*.musicxml`); arpeggios; tremolos.
5. Dynamics, hairpins (`cresc.` text too), sustain pedal, slurs, tempo marks, fingering.
6. Metadata — **important for Orchestrion's score shelf**, which names cards by them:
   - `<work><work-title>` = the work's title as it should be displayed;
   - `<identification><creator type="composer">` = the composer's full name
     (search relies on it: "beethoven" must find the Moonlight);
   - `<identification><rights>` = the licence (e.g. "Public Domain", "CC BY-SA 4.0 —
     <editor>");
   - `<identification><source>` = the Mutopia page URL of the edition.
   Map these from the `.ly` `\header` (`title`, `composer`, `copyright`/`license`,
   `mutopia*` fields).

## Writing MusicXML that MuseScore imports right

Orchestrion reads MusicXML through MuseScore's importer (its fork,
`~/github/saintmatthieu/Orchestrion/MuseScore`,
`src/importexport/musicxml/internal/import/importmusicxmlpass2.cpp`). Learnt
the hard way on 2026-10-21, curating PDMX scores (user uploads from
musescore.com) — the writer must:

- **Write no invisible notes.** The importer brings `print-object="no"` notes
  back as real notes: Orchestrion then makes the player play them. (PDMX
  transcribers wrote turns and trills out invisibly for MuseScore's playback
  on top of the ornament mark: they had to be played twice.) Same for tempo:
  write the tempo markings the score shows, not playback rubato.
- **Write each staff's pedal marks in time order.** The importer pairs pedal
  starts and stops in *file* order and ignores their `number`; a start that
  comes (in the file) before the previous pedal's stop is dropped, and the
  stops then close the wrong pedals. Write a staff's pedals from one voice's
  pass through the measure, or with `<offset>`, in time order (a release
  before a press at the same instant).
- **Ornaments as marks, notes as notes.** A turn/trill/mordent is an
  `<ornaments>` mark on its note; Orchestrion plays it. Write grace notes as
  `<grace/>` notes before their main note.
- **Mind text inference.** Orchestrion turns on the importer's "infer text
  type": `<words>` like "cresc."/"dim." become crescendo/diminuendo lines
  running to the next dynamic (within 24 quarters, on the same staff), "p"/"f"
  in words become dynamics, tempo words become tempo marks. A "cresc." with
  `<dashes>` in the same `<direction>` becomes one dashed line with the dashes'
  extent (fork fix, 2026-10-21). So a LilyPond `\cresc` text span should be
  written as words + dashes; a hairpin as a `<wedge>`.
- **Expect Debug builds to abort** on the importer's failed assertions
  (`IF_ASSERT_FAILED` calls `assert()`); Release builds only log them, and
  import the score wrong. Orchestrion's score shelf loads every score it lists
  to draw its card, so one bad file crashes the shelf. The final check of a
  file for Orchestrion is opening it in a Debug build and grepping the log for
  `ASSERT FAILED` (the Orchestrion repo's memory notes how to do it headless:
  one launch per file, startup score set in the ini — quoted if the path has a
  comma).

### Checking the Nocturne

Two places to check against the source edition (Schirmer 1881, see Mutopia's
PDF of #1590) once it converts:

- Bar 13 (counting the pickup as bar 1; bar 12 numbered from 0) and its
  repeat at bar 21: the third left-hand chord. The two musescore.com
  transcriptions Orchestrion had disagree — C4–E♭4–F4 against C4–E♭4–G4.
- The turns (bars 3 and 27, 1-based): a mark on the note, not written out too.

## Verification (the main value of the project)

The check needs a reader of our MusicXML that **we didn't write**: if our own code read
it back, a misunderstanding of MusicXML would sit in both writer and reader and cancel
out.

- **MIDI diff (pitches and rhythms).** LilyPond renders MIDI from the same source
  (`\midi {}`) — that is LilyPond's own interpretation, independent of our code
  (repeats, tuplets, grace timing). Render our MusicXML to MIDI with **Verovio**
  (`pip install verovio`; `toolkit.loadFile(...)`, `toolkit.renderToMIDI()`; headless,
  fast) and compare note by note (pitch, onset, duration, per staff/channel) with
  `mido`. Normalise tempo and velocities; compare onsets in beats. Repeats: compare
  against LilyPond's MIDI with `\unfoldRepeats`.
  - **Ornaments:** plain LilyPond MIDI plays a trill as its written note (unless
    `articulate.ly` is used), and so does Verovio, so the diff compares written notes.
    Ornament markings are checked by the structured comparison below.
- **Structured diff (spelling, voices, staves, markings).** MIDI loses pitch spelling
  (C♯ vs D♭), voice and staff assignment, ornaments and articulations. Parse our
  MusicXML with **music21** (`music21.converter.parse`) and compare it with LilyPond's
  event dump (which has spelling, voices and markings).
- **Schema validation** of every output against the official MusicXML 4.0 XSD with
  `lxml`, so that we don't rely on any reader's leniency.
- **Optional consumer check: MuseScore 4** — the importer Orchestrion actually uses.
  Heavy (Qt application, AppImage in CI), so not a hard dependency: run it nightly or
  behind a flag (`mscore -o out.mid in.mxl`, headless with
  `QT_QPA_PLATFORM=offscreen`). MuseScore realises ornaments in playback, so compare
  its MIDI with that in mind.
- **Corpus run:** a pinned checkout of the Mutopia repository
  (https://github.com/MutopiaProject/MutopiaProject), fetched in CI, not vendored. Old
  sources first go through `convert-ly` (bundled with LilyPond). Report per piece:
  converted / schema-valid / MIDI-identical / structurally identical / which features
  failed — the failure histogram drives what to fix next.

## What Mutopia sources need (found on the first two pieces)

- **`convert-ly` is not enough.** Old sources (2.10, 2.12) call Scheme
  functions removed since, which it doesn't rewrite: `set-octavation`
  (now `\ottava`), `override-auto-beam-setting`. `frontend/compat.ly`
  redefines them in today's terms; add to it as the corpus requires.
- **Marks drawn as text.** The Nocturne (#1590) draws its pedal marks as
  `\markup` glyphs (`pedal.Ped`, `pedal.*`: 73 and 72 of them), a turn and a
  trill as glyph text (`scripts.turn`, `scripts.trill`), and fingerings as
  plain numbers. The listener records each text's glyphs; the assembler must
  read them back as sustain on/off and ornaments.
- **Voice contexts come and go.** `<< { } \\ { } >>` creates voice contexts for
  its span and the music continues in another; the assembler maps LilyPond's
  voice contexts to MusicXML voice numbers per staff, reusing numbers.
- **Grace notes** carry a negative grace time (e.g. `[1,1,-1,16]`) at the main
  note's moment; a tuplet's end is reported at the next time step, which can
  be a grace time.

## Dependencies

- **Runtime:** LilyPond **2.24+** (the binary releases bundle Guile — 3.0 since
  2.26). Stable is 2.26 (2026-04), development 2.27; the listener reads
  `timeSignature` on 2.25+ (`timeSignatureFraction` before). Test on 2.26 and
  the development series, and 2.24 while it's common. Python **3.10+**,
  standard library only. `tools/fetch-lilypond.sh [version]` puts an official
  release in `.tools/` (git-ignored), where lilyport finds it.
- **Dev/CI (required):** `verovio` (LGPL) + `mido` (MIT) for the MIDI diff;
  `music21` (BSD) for the structured diff; `lxml` + the MusicXML 4.0 XSD; `pytest`.
  All pip-installable. On GitHub Actions use the official LilyPond binary tarball, not
  distro packages (often outdated).
- **Dev/CI (optional):** MuseScore 4 (AppImage) for the consumer check.

## Layout

```
lilyport/
  pyproject.toml            # package + console script `lilyport`
  lilyport/
    __main__.py / cli.py    # lilyport piece.ly -o piece.mxl  (format from the extension,
                            #  or --to musicxml|json|mnx|...)
    frontend/
      events.ly             # the Scheme listener, loaded into LilyPond
      compat.ly             # definitions old sources rely on
      lilypond.py           # locate + run LilyPond (and convert-ly), read the dump
    model/
      assemble.py           # dump → parts/staves/voices/measures
      score.py              # the format-neutral event model (dataclasses)
      dump.py               # JSON (de)serialisation of the model — the `.json` "format"
    writers/
      musicxml.py           # first writer (+ .mxl packing)
      # mnx.py, mei.py, kern.py, abc.py later
  tests/
    fixtures/*.ly           # small hand-written cases, one feature each
    test_musicxml.py        # schema-valid + MIDI-identical + structurally identical
  tools/
    corpus.py               # Mutopia run + report
  LICENSE                   # GPL-3.0-or-later (runs inside GPL-3 LilyPond)
```

## Milestones

1. **Spike:** confirm the event-listener approach on a two-bar piano fixture
   (two staves, a chord, a tie, a rest); dump events; verify which LilyPond option
   suppresses page output.
2. **Moonlight Sonata, 1st mvt** (Mutopia #276, `moonlight1-a4.ly`, CC BY-SA
   2.5; regular triplets, two staves) end to end: schema-valid, MIDI-identical (Verovio),
   structurally identical (music21), and imports cleanly in MuseScore (checked once by
   hand, since Orchestrion is the first consumer). **Check its Mutopia licence before shipping it in Orchestrion.**
3. Fixtures for each "hard part" above; then the Nocturne Op. 9 No. 2
   (Mutopia #1590, `chopin_nocturne_op9_n2.ly`, CC BY-SA 3.0, after
   G. Schirmer 1881: ornaments, grace-note runs, tuplets, pedals drawn as text).
4. Corpus run over Mutopia's piano pieces; fix by failure frequency.
5. Packaging (`pip install lilyport`), CI on 2.24 + dev series.
6. Second writer: MNX (or the documented JSON dump first, if someone needs it).

## Delivering scores to Orchestrion

- Orchestrion commits the generated `.mxl` files themselves; no build dependency on
  this tool (at most a script in Orchestrion's `tools/` calling it).
- File name = the work's display name (e.g. `Moonlight Sonata, 1st movement.mxl`);
  the File menu lists file names and the shelf sorts by them (numbers by value).
- Each shipped score that needs credit gets an entry in Orchestrion's
  `scores/attributions.json`, keyed by file name:
  `{"author": "...", "license": "...", "url": "<Mutopia page>"}` — shown as a toast
  when the score is opened. CC-BY(-SA) editions require it; the converted file keeps
  the edition's licence (a derivative).
- Precedent for hand-transcribed public-domain scores: Orchestrion's
  `tools/gen_easy_scores.py` (+ `tools/scorenotation.py`, `tools/kv265.py`) generates
  Mozart's K. 265 note for note from the Breitkopf & Härtel edition. Fallback for any
  piece the converter can't handle yet.

## Status

- **Done:** the listener (`lilyport dump PIECE.ly` writes the event stream),
  `compat.ly`; both Mutopia pieces (`tools/fetch-corpus.sh` puts them in
  `.corpus/mutopia/`, git-ignored, as published and after `convert-ly`) dump
  completely on LilyPond 2.26.0. Each score's merged `\header` is a `header`
  record (Moonlight's licence is in `mutopiacopyright`, the Nocturne's in
  `copyright`; the Mutopia id ends `footer`, e.g. `Mutopia-2007/02/11-276`).
- **Done:** the score model and the MusicXML writer (`lilyport convert
  PIECE.ly -o PIECE.mxl`): parts from PianoStaff grouping, voices numbered
  per home staff (cross-staff notes keep their voice; stems-up voices take
  the lower numbers), stem directions the source sets, chords, ties (per note
  in chords), tuplets, grace notes, pickups, cadenzas, multi-measure rests,
  key/time/clef changes, slurs, articulations and ornaments, fingerings
  (Moonlight's text "4 - 5" as a substitution), dynamics, hairpins, pedals,
  text, tempo, final bar lines; metadata into `<work>`, `<identification>`
  (rights = licence — maintainer, source = Mutopia page URL). On both pieces
  music21's reading of the output matches LilyPond's dump note for note
  (onset, spelled pitch, length, staff).
- **Next:** the verification harness (XSD, Verovio MIDI against LilyPond's
  MIDI, music21 structured diff) as tests; open Moonlight in Orchestrion's
  Debug build; then milestone 3 (the Nocturne's text-drawn pedals and
  ornaments, `\cresc` as words + dashes).
- **Open:** repeat structure (`repeatCommands` is recorded, not written);
  beams and accidentals are left to the importer; scores without `\layout`;
  lyrics and chord names (out of scope for now). Moonlight's source says
  `\key e \major` (written as such: C♯ minor isn't declared).
