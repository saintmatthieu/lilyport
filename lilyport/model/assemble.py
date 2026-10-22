"""Builds the score model from the listener's events (frontend/events.ly)."""
import re
from collections import Counter, defaultdict
from fractions import Fraction

from .score import (Chord, Clef, Direction, Duration, Key, Measure, Metadata, Note, Part,
                    Pitch, Score, TimeSignature)

# Staves under these contexts make one instrument (one MusicXML part).
INSTRUMENT_GROUPS = {"PianoStaff", "GrandStaff"}
VOICES_PER_STAFF = 4
END_OF_TIME = (Fraction(10 ** 9), Fraction(0))
NATURAL_SEMITONES = [0, 2, 4, 5, 7, 9, 11]
CLEF_SIGNS = {"clefs.G": "G", "clefs.F": "F", "clefs.C": "C",
              "clefs.percussion": "percussion", "clefs.tab": "TAB"}
# Bar types that are just a bar line.
PLAIN_BARS = {"", "|"}
# "4 - 5": a finger substitution written as text (Mutopia's Moonlight).
FINGERING_TEXT = re.compile(r"^\s*\d(\s*-\s*\d)*\s*$")
MUTOPIA_FOOTER = re.compile(r"Mutopia-\d{4}/\d{1,2}/\d{1,2}-(\d+)")


def assemble(events, score=1):
    """The model of one \\score of the dump (1-based)."""
    events = [e for e in events if e["score"] == score]
    if not events:
        raise ValueError(f"no events for score {score}")
    builder = _Builder(events)
    return builder.build()


def _time(e):
    t = e["t"]
    return (Fraction(t[0], t[1]), Fraction(t[2], t[3]))


def _pitch(p):
    alter = Fraction(p["alter"]).limit_denominator(64) * 2
    return Pitch(p["step"], alter, p["octave"] + 4)


def _duration(d):
    return Duration(d["log"], d["dots"], Fraction(*d["factor"]))


def _key_tonics(fifths):
    """The (step, alteration) of the major and minor keys with this many sharps
    (flats if negative)."""
    step, semitones = 0, 0
    for _ in range(abs(fifths)):
        step, semitones = ((step + 4) % 7, (semitones + 7) % 12) if fifths > 0 else \
                          ((step + 3) % 7, (semitones + 5) % 12)

    def spelled(step, semitones):
        alter = (semitones - NATURAL_SEMITONES[step]) % 12
        return step, alter - 12 if alter > 6 else alter

    return spelled(step, semitones), spelled((step + 5) % 7, (semitones + 9) % 12)


class _Builder:
    def __init__(self, events):
        self.events = events
        self.warnings = []
        self.unhandled = Counter()

    def warn(self, message):
        self.warnings.append(message)

    def build(self):
        self._parts()
        self._voices()
        self._chords()
        self._ties()
        self._tuplets()
        self._beams()
        self._marks()
        self._staff_settings()
        self._time_signatures()
        self._measures()
        self._measure_rests()
        self._bar_lines()
        for kind, count in sorted(self.unhandled.items()):
            self.warn(f"{count} {kind} event(s) not written yet")
        return Score(self._metadata(), self.measures, self.time_signatures, self.parts,
                     self.warnings)

    # Parts and staves: a PianoStaff's staves are one part, any other staff its own.

    def _parts(self):
        groups = {}  # group key -> [(staff id, staff record)]
        for e in self.events:
            if e["kind"] == "staff":
                key = e["parent_id"] if e["parent"] in INSTRUMENT_GROUPS else ("staff", e["staff"])
                groups.setdefault(key, []).append(e)
        self.parts = []
        self.place = {}  # staff id -> (part, staff number)
        for staves in groups.values():
            name = next((s["instrument"] for s in staves if s.get("instrument")), "")
            part = Part(name, len(staves))
            self.parts.append(part)
            for number, staff in enumerate(staves, 1):
                self.place[staff["staff"]] = (part, number)

    # Voices: LilyPond's voice contexts come and go; each gets a number in its
    # part, on its home staff (the one most of its notes are on), shared with
    # voices that don't overlap it in time. Voices with stems up (\voiceOne)
    # choose first, so that they get the lower numbers, which importers draw
    # with stems up.

    def _voices(self):
        staves = defaultdict(Counter)
        stems = defaultdict(Counter)
        spans = {}
        for e in self.events:
            if e["kind"] in ("note", "rest", "multi-measure-rest") and e["voice"]:
                staves[e["voice"]][e["staff"]] += 1
                stems[e["voice"]][-e.get("stem", 0)] += 1
                start = _time(e)[0]
                end = start + _duration(e["duration"]).length
                old = spans.get(e["voice"], (start, end))
                spans[e["voice"]] = (min(old[0], start), max(old[1], end))
        self.voice = {}  # voice id -> (part, number)
        taken = defaultdict(list)  # (part id, number) -> spans
        homes = sorted(staves, key=lambda v: (stems[v].most_common(1)[0][0], spans[v][0], v))
        for voice in homes:
            part, staff = self.place[staves[voice].most_common(1)[0][0]]
            start, end = spans[voice]
            number = (staff - 1) * VOICES_PER_STAFF + 1
            while any(s < end and start < e for s, e in taken[(id(part), number)]):
                number += 1
            if number > staff * VOICES_PER_STAFF:
                self.warn(f"more than {VOICES_PER_STAFF} voices at once on staff {staff}")
            taken[(id(part), number)].append((start, end))
            self.voice[voice] = (part, number)

    # Notes, chords and rests: the notes of one voice at one time are a chord.

    def _chords(self):
        self.chords = {}  # (voice id, time) -> Chord
        self.tied = set()  # (voice id, time, pitch) of notes tied to the next
        for e in self.events:
            kind = e["kind"]
            if kind not in ("note", "rest", "multi-measure-rest") or not e["voice"]:
                continue
            if kind == "note" and "pitch" not in e:
                self.unhandled["unpitched note"] += 1
                continue
            part, number = self.voice[e["voice"]]
            staff_part, staff = self.place[e["staff"]]
            if staff_part is not part:
                self.warn(f"a voice crosses into another part at {e['bar']}: dropped")
                continue
            time = _time(e)
            key = (e["voice"], time)
            duration = _duration(e["duration"])
            chord = self.chords.get(key)
            if chord is None:
                chord = Chord(time, duration, staff, number, [],
                              measure_rest=kind == "multi-measure-rest",
                              stem={1: "up", -1: "down"}.get(e.get("stem")))
                self.chords[key] = chord
                part.chords.append(chord)
            elif chord.duration != duration:
                self.warn(f"bar {e['bar']}: a chord's notes differ in length; "
                          "written with the first's")
            if kind == "note":
                pitch = _pitch(e["pitch"])
                chord.notes.append(Note(pitch, fingerings=[str(f) for f in e.get("fingers", [])]))
                if e.get("tie"):
                    self.tied.add((e["voice"], time, pitch))
        for part in self.parts:
            part.chords.sort(key=lambda c: (c.time, c.voice))
        self.by_voice = defaultdict(list)  # voice id -> chords in time order
        for (voice, time), chord in sorted(self.chords.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            self.by_voice[voice].append(chord)

    def _chord_at(self, e):
        chord = self.chords.get((e["voice"], _time(e)))
        if chord is None:
            self.warn(f"bar {e['bar']}: a {e['kind']} on no note (a skip?): dropped")
        return chord

    def _slur_chord(self, e):
        """The note a slur starts or ends on; on a skip, the voice's next note
        (start) or previous one (end), as LilyPond draws it."""
        time = _time(e)
        chord = self.chords.get((e["voice"], time))
        if chord is None:
            chords = self.by_voice.get(e["voice"], [])
            if e["dir"] == -1:
                chord = next((c for c in chords if c.time > time), None)
            else:
                chord = next((c for c in reversed(chords) if c.time < time), None)
        if chord is None:
            self.warn(f"bar {e['bar']}: a {e['kind']} with no note: dropped")
        return chord

    def _ties(self):
        for e in self.events:
            if e["kind"] == "tie":
                chord = self._chord_at(e)
                if chord:
                    self.tied.update((e["voice"], chord.time, n.pitch) for n in chord.notes)
        for voice, chords in self.by_voice.items():
            for chord, following in zip(chords, chords[1:]):
                for note in chord.notes:
                    if (voice, chord.time, note.pitch) not in self.tied:
                        continue
                    target = next((n for n in following.notes if n.pitch == note.pitch), None)
                    if target is None:
                        self.warn(f"a tie from {chord.time[0]} leads to no equal note")
                        continue
                    note.tie_start = target.tie_stop = True

    def _tuplets(self):
        spans = defaultdict(list)  # voice id -> event times, stops first
        for e in self.events:
            if e["kind"] == "tuplet":
                spans[e["voice"]].append((_time(e), 0 if e["dir"] == 1 else 1))
        for voice, marks in spans.items():
            open_starts = []
            closed = []
            for time, is_start in sorted(marks):
                if is_start:
                    open_starts.append(time)
                elif open_starts:
                    closed.append((open_starts.pop(), time))
            closed += [(start, END_OF_TIME) for start in open_starts]
            for start, stop in closed:
                inside = [c for c in self.by_voice.get(voice, [])
                          if start <= c.time < stop and not c.grace]
                if inside:
                    inside[0].tuplet_starts += 1
                    inside[-1].tuplet_stops += 1

    def _beams(self):
        for e in self.events:
            if e["kind"] != "beam":
                continue
            times = [(Fraction(t[0], t[1]), Fraction(t[2], t[3])) for t in e["stems"]]
            chords = [self.chords.get((e["voice"], time)) for time in sorted(times)]
            if None in chords or len(chords) < 2:
                self.warn(f"bar {e['bar']}: a beam over stems with no notes: dropped")
                continue
            for chord in chords:
                chord.beam = "continue"
            chords[0].beam, chords[-1].beam = "begin", "end"

    # What is attached to notes, and directions.

    def _marks(self):
        open_slurs = defaultdict(list)  # (voice id, kind) -> numbers
        slur_events = sorted(
            (e for e in self.events if e["kind"] in ("slur", "phrasing-slur")),
            key=lambda e: (e["voice"], _time(e), e["dir"] != 1))
        for e in slur_events:
            chord = self._slur_chord(e)
            if chord is None:
                continue
            if e["dir"] == -1:
                busy = {n for (v, _), numbers in open_slurs.items() if v == e["voice"]
                        for n in numbers}
                number = next(n for n in range(1, 17) if n not in busy)
                open_slurs[(e["voice"], e["kind"])].append(number)
                chord.slurs.append(("start", number))
            elif open_slurs[(e["voice"], e["kind"])]:
                chord.slurs.append(("stop", open_slurs[(e["voice"], e["kind"])].pop()))
            else:
                self.warn(f"bar {e['bar']}: a {e['kind']} ends that didn't start")

        for e in self.events:
            kind = e["kind"]
            if kind == "articulation":
                chord = self._chord_at(e)
                if chord:
                    chord.marks.append(e["type"])
            elif kind == "fingering":
                chord = self._chord_at(e)
                if chord:
                    chord.fingerings.append(str(e["digit"]))
            elif kind == "arpeggio":
                chord = self._chord_at(e)
                if chord:
                    chord.arpeggio = True
            elif kind == "text":
                if FINGERING_TEXT.match(e["text"]):
                    chord = self._chord_at(e)
                    if chord:
                        chord.fingerings.append("-".join(re.findall(r"\d", e["text"])))
                else:
                    self._direction(e, "words", text=e["text"],
                                    placement={1: "above", -1: "below"}.get(e["dir"]))
            elif kind == "dynamic":
                self._direction(e, "dynamic", text=e["text"])
            elif kind in ("crescendo", "decrescendo"):
                wedge = "stop" if e["dir"] == 1 else \
                        "crescendo" if kind == "crescendo" else "diminuendo"
                self._direction(e, "wedge", type=wedge)
            elif kind == "sustain":
                self._direction(e, "pedal", type="stop" if e["dir"] == 1 else "start")
            elif kind == "tempo":
                self._direction(e, "tempo", text=e.get("text", ""), placement="above",
                                tempo_unit=_duration(e["unit"]) if "unit" in e else None,
                                tempo_count=Fraction(e["count"]).limit_denominator(1000)
                                if "count" in e else None)
            elif kind in ("una-corda", "tremolo", "breathe", "glissando", "repeat-commands",
                          "skip"):
                if kind != "skip":
                    self.unhandled[kind] += 1

    def _direction(self, e, kind, **fields):
        if e["staff"] in self.place:
            part, staff = self.place[e["staff"]]
        else:  # a score-wide event (tempo): the first staff
            part, staff = self.parts[0], 1
        voice = 0
        if e["voice"] in self.voice and self.voice[e["voice"]][0] is part:
            voice = self.voice[e["voice"]][1]
        part.directions.append(Direction(_time(e), staff, voice, kind, **fields))

    def _staff_settings(self):
        for e in self.events:
            if e["kind"] == "clef":
                part, staff = self.place[e["staff"]]
                sign = CLEF_SIGNS.get(e["glyph"])
                if sign is None:
                    self.warn(f"unknown clef {e['glyph']!r}: treble written")
                    sign, line = "G", 2
                else:
                    line = int(e["position"]) // 2 + 3
                part.clefs.append(Clef(_time(e), staff, sign, line,
                                       round(e["transposition"] / 7)))
            elif e["kind"] == "key":
                part, staff = self.place[e["staff"]]
                fifths = sum(round(alter * 2) for _, alter in e["alterations"])
                tonic = _pitch(e["tonic"])
                tonic = (tonic.step, int(tonic.alter))
                major, minor = _key_tonics(fifths)
                mode = "major" if tonic == major else "minor" if tonic == minor else None
                part.keys.append(Key(_time(e), staff, fifths, mode))

    def _time_signatures(self):
        self.time_signatures = []
        for e in self.events:
            if e["kind"] == "time":
                beats, beat_type = e["fraction"]
                symbol = None
                if e.get("style", "C") == "C":
                    symbol = {(4, 4): "common", (2, 2): "cut"}.get((beats, beat_type))
                self.time_signatures.append(TimeSignature(_time(e), beats, beat_type, symbol))
        if not self.time_signatures:
            self.time_signatures.append(TimeSignature((Fraction(0), Fraction(0)), 4, 4))

    def _nominal_length(self, at):
        current = self.time_signatures[0]
        for signature in self.time_signatures:
            if signature.time[0] <= at:
                current = signature
        return Fraction(current.beats, current.beat_type)

    # Measures: every event knows where its bar began (time - measurePosition);
    # a pickup's events have a negative position, and in a cadenza the position
    # stays put (the bar runs until timing is back on).

    def _measures(self):
        cadenzas = []
        for e in self.events:
            if e["kind"] == "timing":
                if not e["on"]:
                    cadenzas.append([_time(e)[0], None])
                elif cadenzas and cadenzas[-1][1] is None:
                    cadenzas[-1][1] = _time(e)[0]
        starts = {Fraction(0)}
        numbers = {}
        for e in self.events:
            pos = Fraction(e["pos"][0], e["pos"][1])
            if pos >= 0:
                start = _time(e)[0] - pos
                if any(on < start and (off is None or start < off) for on, off in cadenzas):
                    continue
                starts.add(start)
                numbers.setdefault(start, e["bar"])
        end = max((c.time[0] + c.duration.length for p in self.parts for c in p.chords
                   if not c.grace), default=Fraction(0))
        starts = sorted(s for s in starts if s < end) or [Fraction(0)]
        # Bars with no event starting in them (inside a multi-measure rest),
        # except in a cadenza: one bar.
        filled = []
        for start, following in zip(starts, starts[1:] + [end]):
            filled.append(start)
            nominal = self._nominal_length(start)
            while filled[-1] + nominal < following and \
                    not any(on == start for on, _ in cadenzas):
                filled.append(filled[-1] + nominal)
        self.measures = []
        previous = None
        used = Counter()
        for start, following in zip(filled, filled[1:] + [end]):
            number = numbers.get(start, previous + 1 if previous is not None else 1)
            length = following - start
            implicit = length < self._nominal_length(start)
            # LilyPond numbers the bar after a cadenza like the cadenza's.
            label = str(number) + ("" if not used[number] else "abcdefghij"[used[number] - 1])
            used[number] += 1
            self.measures.append(Measure(label, start, length, implicit))
            previous = number
        # A pickup shares its bar number with the first full bar.
        if len(self.measures) > 1 and self.measures[0].implicit \
                and self.measures[1].number.endswith("a"):
            self.measures[1].number = self.measures[0].number
            self.measures[0].number = str(int(self.measures[0].number) - 1)

    def _measure_rests(self):
        for part in self.parts:
            chords = []
            for chord in part.chords:
                if not chord.measure_rest:
                    chords.append(chord)
                    continue
                stop = chord.time[0] + chord.duration.length
                for measure in self.measures:
                    if chord.time[0] <= measure.start < stop:
                        chords.append(Chord((measure.start, Fraction(0)),
                                            Duration(0, 0, measure.length), chord.staff,
                                            chord.voice, [], measure_rest=True,
                                            marks=chord.marks if measure.start == chord.time[0]
                                            else []))
            part.chords = chords

    def _bar_lines(self):
        ends = {m.start + m.length: m for m in self.measures}
        for e in self.events:
            if e["kind"] != "bar-line" or e["type"] in PLAIN_BARS:
                continue
            at = _time(e)[0]
            if at in ends:
                ends[at].right_bar = e["type"]
            elif at != 0:
                self.warn(f"bar {e['bar']}: a {e['type']!r} bar line inside a bar: dropped")

    def _metadata(self):
        fields = next((e["fields"] for e in self.events if e["kind"] == "header"), {})

        def get(*names):
            for name in names:
                value = (fields.get(name) or "").strip()
                if value:
                    return value
            return None

        licence = get("license", "mutopiacopyright", "copyright")
        maintainer = get("maintainer")
        rights = f"{licence} — {maintainer}" if licence and maintainer else licence
        mutopia = MUTOPIA_FOOTER.search(fields.get("footer", ""))
        source = (f"https://www.mutopiaproject.org/cgibin/piece-info.cgi?id={mutopia.group(1)}"
                  if mutopia else None)
        if len(self.parts) == 1 and not self.parts[0].name:
            self.parts[0].name = get("mutopiainstrument", "instrument") or ""
        return Metadata(title=get("title"), subtitle=get("subtitle"), piece=get("piece"),
                        opus=get("opus"), composer=get("composer"), arranger=get("arranger"),
                        poet=get("poet"), rights=rights, source=source,
                        edition=get("source"))
