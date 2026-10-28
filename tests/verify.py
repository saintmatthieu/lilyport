"""Checks lilyport's MusicXML with programs that didn't write it.

- schema_errors(): the MusicXML 4.0 schema (tools/fetch-schema.sh), so that
  no reader's leniency hides a mistake.
- midi_differences(): LilyPond's own MIDI of the source against Verovio's
  MIDI of our MusicXML, note by note (onset, pitch, length, in quarter
  notes). Not staff by staff: the two file a voice's cross-staff notes under
  different tracks (staves are checked by reading the MusicXML instead).
  Where the two programs play the notation differently, the comparison is
  looser:
  - grace notes (LilyPond plays them before the beat, Verovio as
    appoggiaturas, on it): the pitches sounding around their main note; and
    without their octave if an \\ottava starts at the main note (Verovio
    shifts the graces before it too);
  - a rolled chord (\\arpeggio; Verovio rolls it, LilyPond doesn't): its
    notes may start up to ARPEGGIO_SPREAD late;
  - a unison of two voices (one MIDI note), a note with an articulation
    (LilyPond plays a staccato half its length), and a scaled note (c'4*1/2
    s8 is written as drawn, lasting until the voice's next note): onsets
    only;
  - a note tied from the end of the repeated music (\repeatTie): Verovio
    ignores a tie with no start, and strikes it again.
"""
import base64
import io
import subprocess
import sys
from bisect import bisect_left
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / ".corpus" / "musicxml-4.0" / "musicxml.xsd"
ADD_MIDI = Path(__file__).with_name("support") / "add-midi.ly"
UNFOLD_REPEATS = Path(__file__).with_name("support") / "unfold-repeats.ly"
# Verovio writes 120 ticks a quarter, and ends each note a tick early.
ONSET_TOLERANCE = 0.0125
LENGTH_TOLERANCE = 0.02
ARPEGGIO_SPREAD = 0.5


def schema_errors(xml_text):
    """The schema's complaints about a MusicXML document (empty if valid)."""
    from lxml import etree
    schema = etree.XMLSchema(etree.parse(str(SCHEMA)))
    if schema.validate(etree.fromstring(xml_text.encode("utf-8"))):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def midi_notes(data):
    """(onset, length, pitch) of every note of a MIDI file, all tracks
    together, times in quarter notes. A note struck again while it sounds (two
    voices on one pitch) ends there, its length unknown (None)."""
    import mido
    midi = mido.MidiFile(file=io.BytesIO(data))
    notes = []
    for track in midi.tracks:
        found = []
        now, sounding = 0, {}
        for message in track:
            now += message.time
            key = (message.channel, message.note) if message.type.startswith("note") else None
            if message.type == "note_on" and message.velocity > 0:
                if key in sounding:
                    found.append((sounding[key] / midi.ticks_per_beat, None, message.note))
                sounding[key] = now
            elif key is not None:
                start = sounding.pop(key, None)
                if start is not None:
                    found.append((start / midi.ticks_per_beat,
                                  (now - start) / midi.ticks_per_beat, message.note))
        notes += found
    return notes


def verovio_midi(xml_text, repeats=True):
    """Verovio's MIDI of a MusicXML document, its repeats played (or played
    once). Verovio runs in a child process: it crashes now and then after
    many documents in one."""
    script = ("import base64, sys, verovio\n"
              "toolkit = verovio.toolkit()\n"
              f"toolkit.setOptions({{'expandNever': {not repeats}}})\n"
              "if not toolkit.loadData(sys.stdin.read()):\n"
              "    sys.exit('Verovio could not read the MusicXML')\n"
              "sys.stdout.write(toolkit.renderToMIDI())\n")
    result = subprocess.run([sys.executable, "-c", script], input=xml_text, text=True,
                            capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Verovio failed ({result.returncode}): {result.stderr[-500:]}")
    return base64.b64decode(result.stdout)


def _quarters(time):
    return float(Fraction(time[0], time[1]) * 4)


def _grace_windows(events):
    """The spans [first grace, end of main note) of each grace group, from
    LilyPond's events, and whether an \\ottava starts at the main note. An
    \\afterGrace group has no main note at its moment (it sits inside the
    note it follows): its span runs to the end of the voice's next note,
    before which lilyport writes it."""
    graces = defaultdict(Fraction)  # (voice, main time) -> grace length
    mains = defaultdict(dict)  # voice -> main time -> longest main note
    ottavas = {_quarters(e["t"]) for e in events if e["kind"] == "ottava"}
    for e in events:
        if e["kind"] != "note":
            continue
        d = e["duration"]
        length = float(Fraction(2) ** -d["log"] * (2 - Fraction(1, 2 ** d["dots"]))
                       * Fraction(*d["factor"]) * 4)
        main = _quarters(e["t"])
        if e["t"][2]:
            graces[(e["voice"], main)] += Fraction(length)
        else:
            mains[e["voice"]][main] = max(mains[e["voice"]].get(main, 0), length)
    windows = []
    for (voice, main), steal in graces.items():
        if main in mains[voice]:
            end = main + mains[voice][main]
        else:
            following = [t for t in mains[voice] if t > main]
            end = min(following) + mains[voice][min(following)] if following else main
        windows.append((main - float(steal) - ONSET_TOLERANCE, end, main in ottavas))
    return windows


def lilypond_midi_files(directory, stem):
    """LilyPond's MIDI files for a .ly file with one book, in its scores'
    order (one per score with a \\midi: <stem>.midi, <stem>-1.midi, ...).
    Several books name theirs otherwise (<stem>-1-1.midi): not supported."""
    found = {}
    for path in Path(directory).glob(f"{stem}*.mid*"):
        suffix = path.stem[len(stem):]
        if suffix == "" or (suffix[0] == "-" and suffix[1:].isdigit()):
            found[int(suffix[1:] or 0)] = path
        else:
            raise ValueError(f"several books' MIDI files: {path.name}")
    return [found[n] for n in sorted(found)]


def _pitch(e):
    p = e["pitch"]
    return 60 + 12 * p["octave"] + [0, 2, 4, 5, 7, 9, 11][p["step"]] + round(p["alter"] * 2)


def _onsets(events, kind):
    """Sorted onsets of the events of a kind."""
    return sorted(_quarters(e["t"]) for e in events if e["kind"] == kind)


def _near(onsets, time, before=ONSET_TOLERANCE, after=ONSET_TOLERANCE):
    """The first of the sorted onsets within [time - after, time + before]."""
    i = bisect_left(onsets, time - after)
    return onsets[i] if i < len(onsets) and onsets[i] <= time + before else None


def _unisons(events):
    """Per pitch, the sorted onsets two voices strike it at once."""
    voices = defaultdict(set)
    for e in events:
        if e["kind"] == "note" and "pitch" in e and not e["t"][2]:
            voices[(_quarters(e["t"]), _pitch(e))].add(e["voice"])
    unisons = defaultdict(list)
    for (onset, pitch), struck in sorted(voices.items()):
        if len(struck) > 1:
            unisons[pitch].append(onset)
    return unisons


def _repeat_tied(events):
    """Per pitch, the sorted onsets of notes tied with \\repeatTie."""
    chords = {(e["voice"], tuple(e["t"])) for e in events if e["kind"] == "repeat-tie"}
    tied = defaultdict(list)
    for e in events:
        if e["kind"] == "note" and "pitch" in e and \
                (e.get("repeat_tie") or (e["voice"], tuple(e["t"])) in chords):
            tied[_pitch(e)].append(_quarters(e["t"]))
    return {pitch: sorted(onsets) for pitch, onsets in tied.items()}


def midi_differences(lilypond_midi, musicxml_text, events, repeats=True):
    """What differs between LilyPond's MIDI and Verovio's MIDI of our
    MusicXML: a list of readable lines (empty if they agree). events: those
    of LilyPond's run that wrote the MIDI; repeats: whether Verovio plays
    them (LilyPond's MIDI then has them unfolded)."""
    ours = midi_notes(verovio_midi(musicxml_text, repeats))
    theirs = midi_notes(lilypond_midi)
    windows = _grace_windows(events)
    unisons = _unisons(events)
    articulated = _onsets(events, "articulation")
    scaled = sorted(_quarters(e["t"]) for e in events if e["kind"] == "note"
                    and e["duration"]["factor"] != [1, 1])
    arpeggios = _onsets(events, "arpeggio")
    repeat_tied = _repeat_tied(events)

    def in_window(time):
        return any(start <= time < end for start, end, _ in windows)

    differences = []
    # Around grace notes: the same pitches, in whatever rhythm.
    for start, end, ottava in sorted(windows):
        def pitches(notes):
            return sorted(p % 12 if ottava else p
                          for onset, _, p in notes if start <= onset < end)
        if pitches(theirs) != pitches(ours):
            differences.append(f"quarters {start:g}-{end:g} (grace notes): "
                               f"LilyPond {pitches(theirs)}, MusicXML {pitches(ours)}")
    # Elsewhere: note for note.
    def by_pitch(notes):
        # A pitch struck twice at once (two voices) is one note: LilyPond
        # plays it once, Verovio twice.
        keyed = defaultdict(list)
        for onset, length, pitch in sorted(notes, key=lambda note: note[0]):
            if in_window(onset):
                continue
            same = keyed[pitch]
            if same and abs(same[-1][0] - onset) <= ONSET_TOLERANCE:
                same[-1] = (same[-1][0], None)
            else:
                same.append((onset, length))
        return keyed

    mine, others = by_pitch(ours), by_pitch(theirs)
    for pitch in sorted(set(mine) | set(others)):
        left = list(others.get(pitch, []))
        for onset, length in mine.get(pitch, []):
            onsets = [o for o, _ in left]
            match = _near(onsets, onset)
            rolled = False
            if match is None:
                chord = _near(arpeggios, onset, before=0, after=ARPEGGIO_SPREAD)
                if chord is not None:
                    match, rolled = _near(onsets, chord), True
            if match is None:
                if _near(repeat_tied.get(pitch, []), onset) is None:
                    differences.append(
                        f"quarter {onset:g}, pitch {pitch}: not in LilyPond's MIDI")
                continue
            expected = left.pop(onsets.index(match))[1]
            loose = expected is None or length is None or rolled or \
                _near(unisons.get(pitch, []), match) is not None or \
                _near(articulated, match) is not None or \
                _near(scaled, match) is not None or \
                in_window(match + expected - ONSET_TOLERANCE)
            if not loose and abs(expected - length) > LENGTH_TOLERANCE:
                differences.append(f"quarter {onset:g}, pitch {pitch}: "
                                   f"length {length:g}, LilyPond {expected:g}")
        differences += [f"quarter {onset:g}, pitch {pitch}: missing" for onset, _ in left]
    return sorted(differences, key=lambda d: float(d.split(" ")[1].split("-")[0].rstrip(",")))
