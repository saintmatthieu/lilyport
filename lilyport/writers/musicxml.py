"""MusicXML 4.0 (score-partwise) from the score model: `.musicxml`, or `.mxl`
compressed.

Written for MuseScore's importer first (Orchestrion reads scores through it;
see docs/design.md): no invisible notes, each staff's directions in time
order, ornaments as marks on their notes.
"""
import math
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path

from .. import __version__
from ..model.score import Chord, Clef, Direction

DOCTYPE = ('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
           '"http://www.musicxml.org/dtds/partwise.dtd">')
STEPS = "CDEFGAB"
TYPES = {-2: "long", -1: "breve", 0: "whole", 1: "half", 2: "quarter", 3: "eighth",
         4: "16th", 5: "32nd", 6: "64th", 7: "128th", 8: "256th"}
DYNAMICS = {"p", "pp", "ppp", "pppp", "ppppp", "pppppp", "f", "ff", "fff", "ffff", "fffff",
            "ffffff", "mp", "mf", "sf", "sfp", "sfpp", "fp", "rf", "rfz", "sfz", "sffz", "fz",
            "n", "pf", "sfzp"}
ACCIDENTALS = {-2: "flat-flat", -1: "flat", 0: "natural", 1: "sharp", 2: "double-sharp"}
BAR_STYLES = {"|.": "light-heavy", "||": "light-light", ".|": "heavy-light", ".": "heavy",
              "..": "heavy-heavy", ";": "dotted", "!": "dashed", "'": "tick"}
# LilyPond's articulation names -> (MusicXML notations group, element[, attributes]).
MARKS = {
    "accent": ("articulations", "accent"),
    "marcato": ("articulations", "strong-accent"),
    "staccato": ("articulations", "staccato"),
    "staccatissimo": ("articulations", "staccatissimo"),
    "tenuto": ("articulations", "tenuto"),
    "portato": ("articulations", "detached-legato"),
    "trill": ("ornaments", "trill-mark"),
    "prall": ("ornaments", "inverted-mordent"),
    "mordent": ("ornaments", "mordent"),
    "prallprall": ("ornaments", "inverted-mordent", {"long": "yes"}),
    "turn": ("ornaments", "turn"),
    "reverseturn": ("ornaments", "inverted-turn"),
    "upbow": ("technical", "up-bow"),
    "downbow": ("technical", "down-bow"),
    "stopped": ("technical", "stopped"),
    "open": ("technical", "open-string"),
    "flageolet": ("technical", "harmonic"),
    "thumb": ("technical", "thumb-position"),
    "fermata": (None, "fermata", {"type": "upright"}),
    "shortfermata": (None, "fermata", {"type": "upright", "shape": "angled"}),
    "longfermata": (None, "fermata", {"type": "upright", "shape": "square"}),
    "verylongfermata": (None, "fermata", {"type": "upright", "shape": "double-square"}),
}


def write(score, path):
    """Writes the score to path: compressed if it ends in .mxl."""
    path = Path(path)
    text = to_string(score)
    if path.suffix == ".mxl":
        name = path.with_suffix(".musicxml").name
        with zipfile.ZipFile(path, "w") as archive:
            # The mimetype comes first and uncompressed (MusicXML's container rules).
            archive.writestr("mimetype", "application/vnd.recordare.musicxml",
                             compress_type=zipfile.ZIP_STORED)
            archive.writestr("META-INF/container.xml", _container(name),
                             compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr(name, text, compress_type=zipfile.ZIP_DEFLATED)
    else:
        path.write_text(text, encoding="utf-8")


def to_string(score):
    root = to_element(score)
    ET.indent(root)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + DOCTYPE + "\n"
            + ET.tostring(root, encoding="unicode") + "\n")


def to_element(score):
    root = ET.Element("score-partwise", version="4.0")
    _header(root, score.metadata)
    part_list = ET.SubElement(root, "part-list")
    for index, part in enumerate(score.parts, 1):
        score_part = ET.SubElement(part_list, "score-part", id=f"P{index}")
        _text(score_part, "part-name", part.name)
    divisions = _divisions(score)
    for index, part in enumerate(score.parts, 1):
        _PartWriter(score, part, divisions).write(ET.SubElement(root, "part", id=f"P{index}"))
    return root


def _container(name):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<container><rootfiles>'
            f'<rootfile full-path="{name}" media-type="application/vnd.recordare.musicxml+xml"/>'
            '</rootfiles></container>\n')


def _text(parent, tag, text, **attributes):
    element = ET.SubElement(parent, tag, **attributes)
    element.text = str(text)
    return element


def _header(root, metadata):
    if metadata.title or metadata.opus:
        work = ET.SubElement(root, "work")
        if metadata.opus:
            _text(work, "work-number", metadata.opus)
        if metadata.title:
            _text(work, "work-title", metadata.title)
    if metadata.piece:
        _text(root, "movement-title", metadata.piece)
    identification = ET.SubElement(root, "identification")
    for kind, name in (("composer", metadata.composer), ("arranger", metadata.arranger),
                       ("poet", metadata.poet)):
        if name:
            _text(identification, "creator", name, type=kind)
    if metadata.rights:
        _text(identification, "rights", metadata.rights)
    encoding = ET.SubElement(identification, "encoding")
    _text(encoding, "software", f"lilyport {__version__}")
    if metadata.source:
        _text(identification, "source", metadata.source)
    if metadata.edition or metadata.subtitle:
        miscellaneous = ET.SubElement(identification, "miscellaneous")
        if metadata.subtitle:
            _text(miscellaneous, "miscellaneous-field", metadata.subtitle, name="subtitle")
        if metadata.edition:
            _text(miscellaneous, "miscellaneous-field", metadata.edition, name="edition")


def _divisions(score):
    """Divisions of a quarter note that make every duration and onset whole."""
    fractions = [m.start for m in score.measures] + [m.length for m in score.measures]
    for part in score.parts:
        fractions += [c.time[0] for c in part.chords] + [c.duration.length for c in part.chords]
        fractions += [d.time[0] for d in part.directions] + [c.time[0] for c in part.clefs]
        fractions += [k.time[0] for k in part.keys]
    return math.lcm(*((f * 4).denominator for f in fractions))


class _PartWriter:
    def __init__(self, score, part, divisions):
        self.score = score
        self.part = part
        self.divisions = divisions

    def units(self, wholes):
        units = wholes * 4 * self.divisions
        assert units.denominator == 1, wholes
        return int(units)

    def write(self, element):
        for index, measure in enumerate(self.score.measures):
            self.measure(ET.SubElement(element, "measure", number=measure.number,
                                       **({"implicit": "yes"} if measure.implicit else {})),
                         measure, first=index == 0)

    def in_measure(self, items, measure):
        end = measure.start + measure.length
        return [i for i in items if measure.start <= i.time[0] < end]

    def measure(self, element, measure, first):
        part = self.part
        start = measure.start
        clefs = self.in_measure(part.clefs, measure)
        keys = self.in_measure(part.keys, measure)
        times = self.in_measure(self.score.time_signatures, measure)
        at_start = lambda items: [i for i in items if i.time[0] == start]
        if measure.repeat_start or measure.volta_start:
            barline = ET.SubElement(element, "barline", location="left")
            if measure.repeat_start:
                _text(barline, "bar-style", "heavy-light")
            if measure.volta_start:
                self.ending(barline, measure.volta_start, "start")
            if measure.repeat_start:
                ET.SubElement(barline, "repeat", direction="forward")
        self.attributes(element, at_start(keys), at_start(times), at_start(clefs), first)

        # Staff-wide changes inside the bar go into the stream at their time.
        staff_items = [c for c in clefs if c.time[0] != start] + \
                      [k for k in keys if k.time[0] != start]
        chords = self.in_measure(part.chords, measure)
        directions = self.in_measure(part.directions, measure)
        voices = sorted({c.voice for c in chords})
        passes = {voice: [c for c in chords if c.voice == voice] +
                  [d for d in directions if d.voice == voice] for voice in voices}
        # Directions of no voice, and staff-wide changes: with the first voice
        # on their staff (or a pass of their own if the staff has none).
        first_voice = {}
        for voice in voices:
            staff = next(c.staff for c in chords if c.voice == voice)
            first_voice.setdefault(staff, voice)
        loose = [d for d in directions if d.voice not in passes] + staff_items
        for item in loose:
            voice = first_voice.get(item.staff)
            if voice is None:
                passes.setdefault(("staff", item.staff), []).append(item)
            else:
                passes[voice].append(item)

        cursor = start
        for items in passes.values():
            if cursor != start:
                self.move(element, cursor, start)
                cursor = start
            # At one time: pedal releases, then other directions, then notes.
            for item in sorted(items, key=lambda i: (i.time, isinstance(i, Chord),
                                                     getattr(i, "type", "") != "stop")):
                if item.time[0] != cursor:
                    self.move(element, cursor, item.time[0])
                    cursor = item.time[0]
                if isinstance(item, Chord):
                    self.chord(element, item, measure)
                    if not item.grace:
                        cursor += measure.length if item.measure_rest else item.duration.length
                elif isinstance(item, Direction):
                    self.direction(element, item)
                elif isinstance(item, Clef):
                    self.attributes(element, [], [], [item], False)
                else:  # a key
                    self.attributes(element, [item], [], [], False)

        style = "light-heavy" if measure.repeat_end else BAR_STYLES.get(measure.right_bar)
        if style or measure.volta_stop:
            barline = ET.SubElement(element, "barline", location="right")
            if style:
                _text(barline, "bar-style", style)
            if measure.volta_stop:
                self.ending(barline, measure.volta_stop,
                            "stop" if measure.volta_stop.closed else "discontinue")
            if measure.repeat_end:
                ET.SubElement(barline, "repeat", direction="backward",
                              **({"times": str(measure.repeat_end)}
                                 if measure.repeat_end != 2 else {}))

    def ending(self, barline, volta, kind):
        number = ", ".join(str(n) for n in volta.numbers)
        if kind == "start":
            _text(barline, "ending", volta.text, number=number, type=kind)
        else:
            ET.SubElement(barline, "ending", number=number, type=kind)

    def move(self, element, cursor, target):
        if target > cursor:
            _text(ET.SubElement(element, "forward"), "duration", self.units(target - cursor))
        else:
            _text(ET.SubElement(element, "backup"), "duration", self.units(cursor - target))

    def attributes(self, element, keys, times, clefs, first):
        if not (keys or times or clefs or first):
            return
        attributes = ET.SubElement(element, "attributes")
        if first:
            _text(attributes, "divisions", self.divisions)
        # One key for all staves, unless they differ.
        if keys and all((k.fifths, k.mode) == (keys[0].fifths, keys[0].mode) for k in keys) \
                and len(keys) == self.part.staves:
            keys = [keys[0]]
            numbered = False
        else:
            numbered = True
        for key in keys:
            element_key = ET.SubElement(attributes, "key",
                                        **({"number": str(key.staff)} if numbered else {}))
            _text(element_key, "fifths", key.fifths)
            if key.mode:
                _text(element_key, "mode", key.mode)
        for time in times:
            element_time = ET.SubElement(attributes, "time",
                                         **({"symbol": time.symbol} if time.symbol else {}))
            _text(element_time, "beats", time.beats)
            _text(element_time, "beat-type", time.beat_type)
        if first and self.part.staves > 1:
            _text(attributes, "staves", self.part.staves)
        for clef in clefs:
            element_clef = ET.SubElement(attributes, "clef", number=str(clef.staff))
            _text(element_clef, "sign", clef.sign)
            _text(element_clef, "line", clef.line)
            if clef.octave_change:
                _text(element_clef, "clef-octave-change", clef.octave_change)

    def chord(self, element, chord, measure):
        for index, note in enumerate(chord.notes or [None]):
            self.note(element, chord, note, index, measure)

    def note(self, element, chord, note, index, measure):
        duration = chord.duration
        xml = ET.SubElement(element, "note")
        if chord.grace:
            ET.SubElement(xml, "grace")
        if index > 0:
            ET.SubElement(xml, "chord")
        if note is None:
            ET.SubElement(xml, "rest", **({"measure": "yes"} if chord.measure_rest else {}))
        else:
            pitch = ET.SubElement(xml, "pitch")
            _text(pitch, "step", STEPS[note.pitch.step])
            if note.pitch.alter:
                alter = note.pitch.alter
                _text(pitch, "alter", alter.numerator if alter.denominator == 1 else float(alter))
            _text(pitch, "octave", note.pitch.octave)
        if not chord.grace:
            _text(xml, "duration",
                  self.units(measure.length if chord.measure_rest else duration.length))
        if note is not None:
            if note.tie_stop:
                ET.SubElement(xml, "tie", type="stop")
            if note.tie_start:
                ET.SubElement(xml, "tie", type="start")
        _text(xml, "voice", chord.voice)
        if not chord.measure_rest:
            _text(xml, "type", TYPES.get(duration.log, "quarter"))
            for _ in range(duration.dots):
                ET.SubElement(xml, "dot")
            if duration.factor != 1:
                modification = ET.SubElement(xml, "time-modification")
                _text(modification, "actual-notes", duration.factor.denominator)
                _text(modification, "normal-notes", duration.factor.numerator)
        if chord.stem and note is not None:
            _text(xml, "stem", chord.stem)
        if self.part.staves > 1:
            _text(xml, "staff", chord.staff)
        if chord.beam and note is not None and index == 0:
            # The primary beam, on a chord's first note (as MuseScore writes it;
            # Verovio rejects it on the others). Importers draw the secondary
            # beams from the durations.
            _text(xml, "beam", chord.beam, number="1")
        self.notations(xml, chord, note, first=index == 0)

    def notations(self, xml, chord, note, first):
        notations = ET.Element("notations")
        if note is not None:
            if note.tie_stop:
                ET.SubElement(notations, "tied", type="stop")
            if note.tie_start:
                ET.SubElement(notations, "tied", type="start")
        groups = {}  # articulations, ornaments, technical

        def group_element(name):
            if name not in groups:
                groups[name] = ET.SubElement(notations, name)
            return groups[name]

        if first:
            for kind, number in chord.slurs:
                ET.SubElement(notations, "slur", type=kind, number=str(number))
            hidden = {} if chord.tuplet_shown else {"bracket": "no", "show-number": "none"}
            for _ in range(chord.tuplet_starts):
                ET.SubElement(notations, "tuplet", type="start", **hidden)
            for _ in range(chord.tuplet_stops):
                ET.SubElement(notations, "tuplet", type="stop")
            for mark in chord.marks:
                if mark not in MARKS:
                    continue
                group, tag, *attributes = MARKS[mark]
                parent = notations if group is None else group_element(group)
                ET.SubElement(parent, tag, **(attributes[0] if attributes else {}))
            for kind in chord.trill_line:
                ET.SubElement(group_element("ornaments"), "wavy-line", type=kind, number="1")
            # After all the ornaments (MusicXML's order).
            for placement, alter in chord.ornament_alters.items():
                _text(group_element("ornaments"), "accidental-mark", ACCIDENTALS[alter],
                      placement=placement)
        fingerings = (chord.fingerings if first else []) + (note.fingerings if note else [])
        if fingerings:
            technical = group_element("technical")
            for fingering in fingerings:
                fingers = fingering.split("-")
                _text(technical, "fingering", fingers[0])
                for finger in fingers[1:]:
                    _text(technical, "fingering", finger, substitution="yes")
        if chord.arpeggio and note is not None:
            ET.SubElement(notations, "arpeggiate")
        if len(notations):
            xml.append(notations)

    def direction(self, element, direction):
        if direction.kind == "tempo" and not direction.text and not direction.tempo_count:
            # Only a playback tempo: no mark to show.
            if direction.sound_tempo:
                ET.SubElement(element, "sound", tempo=_number(direction.sound_tempo))
            return
        placement = direction.placement or (
            "below" if direction.kind in ("dynamic", "wedge", "pedal")
            or (direction.kind == "octave-shift" and direction.type == "up") else "above")
        xml = ET.SubElement(element, "direction", placement=placement)
        kind_element = ET.SubElement(xml, "direction-type")
        if direction.kind == "dynamic":
            dynamics = ET.SubElement(kind_element, "dynamics")
            if direction.text in DYNAMICS:
                ET.SubElement(dynamics, direction.text)
            else:
                _text(dynamics, "other-dynamics", direction.text)
        elif direction.kind == "words":
            _text(kind_element, "words", direction.text)
        elif direction.kind == "wedge":
            ET.SubElement(kind_element, "wedge", type=direction.type)
        elif direction.kind == "octave-shift":
            ET.SubElement(kind_element, "octave-shift", type=direction.type, number="1",
                          **({"size": str(direction.size)} if direction.type != "stop" else {}))
        elif direction.kind == "pedal":
            ET.SubElement(kind_element, "pedal", type=direction.type, line="no", sign="yes")
        elif direction.kind == "tempo":
            if direction.text:
                _text(kind_element, "words", direction.text, **{"font-weight": "bold"})
            if direction.tempo_unit and direction.tempo_count:
                if direction.text:
                    kind_element = ET.SubElement(xml, "direction-type")
                metronome = ET.SubElement(kind_element, "metronome")
                _text(metronome, "beat-unit", TYPES.get(direction.tempo_unit.log, "quarter"))
                for _ in range(direction.tempo_unit.dots):
                    ET.SubElement(metronome, "beat-unit-dot")
                _text(metronome, "per-minute", _number(direction.tempo_count))
        if direction.voice:
            _text(xml, "voice", direction.voice)
        if self.part.staves > 1:
            _text(xml, "staff", direction.staff)
        if direction.sound_tempo:
            ET.SubElement(xml, "sound", tempo=_number(direction.sound_tempo))


def _number(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{float(value):g}"
