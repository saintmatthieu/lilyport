"""The format-neutral score model, which every writer reads.

Times are (main, grace) pairs of fractions of a whole note, from the start of
the score: grace time is negative for grace notes, before their main note at
the same main time. Staves and voices are numbered within their part, from 1.
"""
from dataclasses import dataclass, field
from fractions import Fraction

Time = tuple[Fraction, Fraction]


@dataclass(frozen=True)
class Pitch:
    step: int        # 0 = C ... 6 = B
    alter: Fraction  # in semitones: 1 is a sharp
    octave: int      # scientific: middle C is C4


@dataclass(frozen=True)
class Duration:
    log: int                      # 0 = whole, 1 = half, 2 = quarter... (-1 = breve)
    dots: int = 0
    factor: Fraction = Fraction(1)  # tuplets and scaling: 2/3 in a triplet

    @property
    def length(self) -> Fraction:
        """In whole notes."""
        return Fraction(2) ** -self.log * (2 - Fraction(1, 2 ** self.dots)) * self.factor


@dataclass
class Note:
    pitch: Pitch
    tie_start: bool = False
    tie_stop: bool = False
    fingerings: list[str] = field(default_factory=list)  # of this note in a chord


@dataclass
class Chord:
    """A note, a chord, or a rest (no notes)."""
    time: Time
    duration: Duration
    staff: int
    voice: int
    notes: list[Note]
    measure_rest: bool = False
    tuplet_starts: int = 0   # tuplets that begin (end) on this chord
    tuplet_stops: int = 0
    slurs: list[tuple[str, int]] = field(default_factory=list)  # ("start"|"stop", number)
    marks: list[str] = field(default_factory=list)   # LilyPond's names: "staccato", "fermata", "trill"...
    fingerings: list[str] = field(default_factory=list)  # "4", or "4-5" for a substitution
    arpeggio: bool = False
    stem: str | None = None  # "up"/"down" as the source sets it, None if automatic
    beam: str | None = None  # "begin"/"continue"/"end" in one of LilyPond's beams

    @property
    def grace(self) -> bool:
        return self.time[1] != 0


@dataclass
class Direction:
    """A mark tied to a time on a staff rather than to a note."""
    time: Time
    staff: int
    voice: int        # 0 if it belongs to no voice with notes
    kind: str         # "dynamic", "words", "wedge", "pedal", "tempo"
    text: str = ""
    type: str = ""    # wedge: "crescendo"/"diminuendo"/"stop"; pedal: "start"/"stop"
    placement: str | None = None  # "above"/"below"
    tempo_unit: Duration | None = None
    tempo_count: Fraction | None = None
    sound_tempo: Fraction | None = None  # playback, in quarter notes per minute


@dataclass
class Clef:
    time: Time
    staff: int
    sign: str        # "G", "F", "C", "percussion", "TAB"
    line: int
    octave_change: int = 0


@dataclass
class Key:
    time: Time
    staff: int
    fifths: int
    mode: str | None  # "major"/"minor", None if the tonic is neither's


@dataclass
class TimeSignature:
    time: Time
    beats: int
    beat_type: int
    symbol: str | None = None  # "common" (C) or "cut"


@dataclass
class Measure:
    number: str
    start: Fraction
    length: Fraction
    implicit: bool = False      # a pickup, or any bar shorter than its time signature
    right_bar: str | None = None  # LilyPond's bar type: "|.", "||"...


@dataclass
class Part:
    name: str
    staves: int
    chords: list[Chord] = field(default_factory=list)
    directions: list[Direction] = field(default_factory=list)
    clefs: list[Clef] = field(default_factory=list)
    keys: list[Key] = field(default_factory=list)


@dataclass
class Metadata:
    title: str | None = None
    subtitle: str | None = None
    piece: str | None = None       # the movement
    opus: str | None = None
    composer: str | None = None
    arranger: str | None = None
    poet: str | None = None
    rights: str | None = None      # the licence, and who holds it
    source: str | None = None      # where the edition is published (a URL)
    edition: str | None = None     # the edition it was made from


@dataclass
class Score:
    metadata: Metadata
    measures: list[Measure]
    time_signatures: list[TimeSignature]
    parts: list[Part]
    warnings: list[str] = field(default_factory=list)
