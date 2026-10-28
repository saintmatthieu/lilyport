"""The MusicXML writer, on the fixtures and (when fetched) the Mutopia pieces.
Needs LilyPond (tools/fetch-lilypond.sh)."""
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path

import pytest

from lilyport.frontend.lilypond import dump_events, find_lilypond
from lilyport.cli import main
from lilyport.model.assemble import assemble, parse_tempo
from lilyport.writers import musicxml

FIXTURES = Path(__file__).with_name("fixtures")
CORPUS = Path(__file__).resolve().parents[1] / ".corpus" / "mutopia"

try:
    find_lilypond()
except FileNotFoundError:
    pytestmark = pytest.mark.skip("LilyPond not found: run tools/fetch-lilypond.sh")


def convert(ly):
    return musicxml.to_element(assemble(dump_events(ly)))


def measures(root):
    return root.findall("part/measure")


def notes(measure):
    return measure.findall("note")


def check_timing(root):
    """Every measure's stream stays within the measure: no backup before its
    start, no voice past its end, and the measure lengths match the model's
    time signatures."""
    divisions = int(root.find("part/measure/attributes/divisions").text)
    beats = None
    bars = measures(root)
    for measure, following in zip(bars, bars[1:] + [None]):
        time = measure.find("attributes/time")
        if time is not None:
            beats = Fraction(int(time.findtext("beats")) * 4, int(time.findtext("beat-type")))
        cursor = longest = 0
        for element in measure:
            duration = int(element.findtext("duration") or 0)
            if element.tag == "backup":
                cursor -= duration
            elif element.tag == "forward" or (element.tag == "note"
                                              and element.find("chord") is None):
                cursor += duration
            assert cursor >= 0, measure.get("number")
            longest = max(longest, cursor)
        # The first part of a bar a repeat divides is short (the second is implicit).
        divided = following is not None and following.get("implicit") == "yes"
        if measure.get("implicit") != "yes" and measure.find("note/rest[@measure]") is None \
                and not divided:
            assert longest >= beats * divisions or measure.get("number").endswith("a"), \
                measure.get("number")


def test_two_bars():
    root = convert(FIXTURES / "two-bars.ly")
    check_timing(root)
    first, second, third = measures(root)
    # Two voices on the upper staff, one on the lower, numbered by staff.
    voices = {(n.findtext("staff"), n.findtext("voice")) for n in notes(first)}
    assert voices == {("1", "1"), ("1", "2"), ("2", "5")}
    assert len(first.findall("note/chord")) == 2
    triplet = [n for n in notes(second) if n.find("time-modification") is not None]
    assert [n.findtext("time-modification/actual-notes") for n in triplet] == ["3"] * 3
    assert triplet[0].find("notations/tuplet").get("type") == "start"
    assert triplet[-1].find("notations/tuplet").get("type") == "stop"
    grace = [n for n in notes(second) if n.find("grace") is not None]
    assert len(grace) == 1 and grace[0].find("duration") is None
    # LilyPond's beams: the four eighths of bar 1, the triplet.
    assert [n.findtext("beam") for n in notes(first) if n.findtext("type") == "eighth"] \
        == ["begin", "continue", "continue", "end"]
    assert [n.findtext("beam") for n in triplet] == ["begin", "continue", "end"]
    # The tie runs across the bar line.
    assert second.find("note/tie[@type='start']") is not None
    assert third.find("note/tie[@type='stop']") is not None


def test_bars():
    root = convert(FIXTURES / "bars.ly")
    check_timing(root)
    bars = measures(root)
    assert [m.get("number") for m in bars] == ["0", "1", "2", "3", "4", "4a"]
    assert bars[0].get("implicit") == "yes"
    # The multi-measure rest: one measure rest per bar.
    assert all(notes(m)[0].find("rest").get("measure") == "yes" for m in bars[2:4])
    # The cadenza is one bar of eight eighths.
    assert len(notes(bars[4])) == 8
    assert bars[-1].findtext("barline/bar-style") == "light-heavy"


def test_markings():
    root = convert(FIXTURES / "markings.ly")
    check_timing(root)
    assert root.findtext("work/work-title") == "Markings"
    assert root.findtext("identification/creator[@type='composer']") == "Nobody"
    assert root.findtext("identification/rights") == "Public Domain"
    first, second, third, fourth, fifth, sixth = measures(root)
    assert first.find("direction/direction-type/dynamics/p") is not None
    slurs = [s.get("type") for s in first.iter("slur")]
    assert slurs == ["start", "stop"]
    assert first.find("note/notations/articulations/staccato") is not None
    assert first.find("note/notations/articulations/accent") is not None
    # In the chord <c~ e-3>, only C is tied and only E fingered.
    c, e = notes(second)[:2]
    assert c.find("tie") is not None and e.find("tie") is None
    assert e.findtext("notations/technical/fingering") == "3"
    assert c.find("notations/technical") is None
    assert second.find("note/notations/fermata") is not None
    wedges = [w.get("type") for w in third.iter("wedge")]
    assert wedges == ["crescendo", "stop"]
    assert [p.get("type") for p in fourth.iter("pedal")] == ["start", "stop"]
    assert fourth.findtext("direction/direction-type/words") == "dolce"
    assert fourth.find("note/notations/ornaments/trill-mark") is not None
    # \startTrillSpan to the resolution's first grace note: the trill and its
    # line on the F alone, the grace notes untrilled.
    trill, grace = notes(fifth)[:2]
    assert [(c.tag, c.get("type")) for c in trill.find("notations/ornaments")] == \
        [("trill-mark", None), ("wavy-line", "start"), ("wavy-line", "stop")]
    assert grace.find("grace") is not None and grace.find("notations/ornaments") is None
    # \ottava #1 over C and D: sounding pitches, drawn an octave lower.
    stream = [(e.tag, e.findtext("pitch/step") or e.find(".//octave-shift").get("type"))
              for e in sixth if e.tag in ("note", "direction")]
    assert stream == [("direction", "down"), ("note", "C"), ("note", "D"),
                      ("direction", "stop"), ("note", "E"), ("note", "F")]
    assert notes(sixth)[0].findtext("pitch/octave") == "7"


def test_mxl(tmp_path):
    score = assemble(dump_events(FIXTURES / "two-bars.ly"))
    musicxml.write(score, tmp_path / "two-bars.mxl")
    with zipfile.ZipFile(tmp_path / "two-bars.mxl") as archive:
        assert archive.namelist()[0] == "mimetype"
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        name = container.find("rootfiles/rootfile").get("full-path")
        assert ET.fromstring(archive.read(name)).tag == "score-partwise"


@pytest.mark.parametrize("piece", ["moonlight1-a4", "chopin_nocturne_op9_n2"])
def test_mutopia(piece):
    ly = CORPUS / f"{piece}.converted.ly"
    if not ly.exists():
        pytest.skip("run tools/fetch-corpus.sh")
    events = dump_events(ly)
    root = musicxml.to_element(assemble(events))
    check_timing(root)
    pitches = sum(1 for e in events if e["kind"] == "note")
    assert len(root.findall("part/measure/note/pitch")) == pitches
    if piece == "moonlight1-a4":
        # Its 2.10 beam settings (compat.ly): the triplets beamed in threes,
        # stems up while the melody is silent (bars 1-4).
        bar = root.find("part/measure[@number='1']")
        triplets = [n for n in notes(bar) if n.findtext("staff") == "1"]
        assert [n.findtext("beam") for n in triplets[:3]] == ["begin", "continue", "end"]
        assert {n.findtext("stem") for n in triplets} == {"up"}


def test_voice_one_is_voice_one():
    root = convert(FIXTURES / "late-voice-one.ly")
    high, low = sorted(notes(measures(root)[1]), key=lambda n: -int(n.findtext("pitch/octave")))
    assert (high.findtext("voice"), high.findtext("stem")) == ("1", "up")
    assert (low.findtext("voice"), low.findtext("stem")) == ("2", "down")


def test_starting_tempo():
    events = dump_events(FIXTURES / "tempo.ly")
    heading = musicxml.to_element(assemble(events, 1)).find("part/measure/direction")
    assert heading.findtext("direction-type/words") == "Adagio sostenuto"
    assert heading.find("sound").get("tempo") == "54"
    marks = musicxml.to_element(assemble(events, 2)).findall("part/measure/direction")
    assert len(marks) == 1
    assert marks[0].findtext("direction-type/words") == "Allegro"
    assert marks[0].findtext("direction-type/metronome/per-minute") == "132"
    assert marks[0].find("sound").get("tempo") == "132"
    # Tempo words, no \midi: LilyPond's default tempo, written and warned about.
    score = assemble(events, 3)
    words = musicxml.to_element(score).find("part/measure/direction")
    assert words.findtext("direction-type/words") == "Andante"
    assert words.find("sound").get("tempo") == "60"
    assert any("LilyPond's default" in w for w in score.warnings)
    assert not any("LilyPond's default" in w for w in assemble(events, 3, 66).warnings)


def test_tempo_of_midi_twin():
    score = assemble(dump_events(FIXTURES / "tempo-twin.ly"))
    words = musicxml.to_element(score).find("part/measure/direction")
    assert words.findtext("direction-type/words") == "Not fast"
    assert words.find("sound").get("tempo") == "72"
    assert not score.warnings


def test_tempo_option(tmp_path):
    assert parse_tempo("4=54") == 54
    assert parse_tempo("4.=40") == 60
    assert parse_tempo("2 = 30") == 60
    with pytest.raises(ValueError):
        parse_tempo("3=60")
    out = tmp_path / "tempo.musicxml"
    main(["convert", str(FIXTURES / "tempo.ly"), "-o", str(out), "--tempo", "4.=40"])
    heading = ET.parse(out).getroot().find("part/measure/direction")
    assert heading.findtext("direction-type/words") == "Adagio sostenuto"
    assert heading.find("sound").get("tempo") == "60"


def test_text_marks():
    root = convert(FIXTURES / "text-marks.ly")
    check_timing(root)
    first, second = measures(root)
    # The hidden 8 = 132 only sets the playback tempo (in quarters).
    assert first.find("direction/direction-type/metronome") is None
    assert first.find("sound").get("tempo") == "66"
    # Ped. on C, * on E, Ped. on F; Ped. again on G: released first.
    pedals = [(m.get("number"), p.get("type")) for m in (first, second)
              for p in m.iter("pedal")]
    assert pedals == [("1", "start"), ("1", "stop"), ("1", "start"),
                      ("2", "stop"), ("2", "start"), ("2", "stop")]
    # The turn on D, its upper note flat, its lower natural; no text left.
    d = notes(first)[1]
    assert d.find("notations/ornaments/turn") is not None
    alters = {a.get("placement"): a.text for a in d.iter("accidental-mark")}
    assert alters == {"above": "flat", "below": "natural"}
    assert root.find(".//words") is None
    assert notes(first)[2].findtext("notations/technical/fingering") == "54"


def test_slurs_pair_in_file_order():
    root = convert(FIXTURES / "slurs.ly")
    open_slurs = {}
    pairs = []
    for note in root.iter("note"):
        for slur in note.iter("slur"):
            number, step = slur.get("number"), note.findtext("pitch/step")
            if slur.get("type") == "start":
                assert number not in open_slurs
                open_slurs[number] = step
            else:
                pairs.append((open_slurs.pop(number), step))
    # The upper staff's C to F, and the lower staff's four pairs per bar.
    assert ("C", "F") in pairs and len(pairs) == 5
    assert pairs.count(("C", "D")) == 1 and pairs.count(("B", "C")) == 1


def test_dynamics_lines():
    root = convert(FIXTURES / "dynamics-lines.ly")
    check_timing(root)
    assert root.findtext("part/measure/attributes/staves") == "2"
    marks = [(next(iter(d.find("direction-type"))).tag, d.findtext("staff"), d.get("placement"))
             for d in root.iter("direction")]
    assert ("dynamics", "1", "below") in marks and ("wedge", "1", "below") in marks
    assert ("words", "1", "below") in marks  # ^"cresc." in the line between the staves
    assert [m for m in marks if m[0] == "pedal"] == [("pedal", "2", "below")] * 2


def test_scaled_durations_and_after_grace():
    root = convert(FIXTURES / "scaled-and-after-grace.ly")
    check_timing(root)
    first, second, _, fourth = measures(root)
    # a8*2/3 b4*2/3 make one triplet, c d e another: tuplets LilyPond draws
    # no bracket for.
    starts = first.findall("note/notations/tuplet[@type='start']")
    assert len(starts) == 2
    assert {(t.get("bracket"), t.get("show-number")) for t in starts} == {("no", "none")}
    # The resolution after the trilled F: grace notes before the G.
    stream = [(n.findtext("pitch/step"), n.find("grace") is not None) for n in notes(second)]
    assert stream == [("F", False), ("E", True), ("F", True), ("G", False)]
    assert second.find("backup") is None
    # c4*1/2 s8: the quarter as drawn, lasting until the next note.
    quarter = notes(fourth)[0]
    assert (quarter.findtext("type"), quarter.findtext("duration")) == \
        ("quarter", root.findtext("part/measure/attributes/divisions"))
    assert quarter.find("time-modification") is None and fourth.find("forward") is None


def test_repeats():
    root = convert(FIXTURES / "repeats.ly")
    check_timing(root)
    bars = {m.get("number"): m for m in measures(root)}

    def barline(number, location):
        element = bars[number].find(f"barline[@location='{location}']")
        if element is None:
            return None
        return [(c.tag, c.get("direction") or c.get("type"), c.get("number"), c.get("times"))
                for c in element if c.tag != "bar-style"]

    # No repeat sign at the start of the score; alternative endings.
    assert barline("1", "left") is None
    assert barline("3", "left") == [("ending", "start", "1", None)]
    assert bars["3"].findtext("barline/ending") == "1."
    assert barline("3", "right") == [("ending", "stop", "1", None),
                                     ("repeat", "backward", None, None)]
    assert barline("4", "right") == [("ending", "discontinue", "2", None)]
    # After an upbeat: the bar divided at the repeat signs, its second part implicit.
    assert [(n, bars[n].get("implicit")) for n in ("5", "5a", "7", "7a")] == \
        [("5", None), ("5a", "yes"), ("7", None), ("7a", "yes")]
    assert barline("5a", "left") == [("repeat", "forward", None, None)]
    assert barline("7", "right") == [("repeat", "backward", None, None)]
    # Played three times, the first ending twice.
    assert barline("9", "right") == [("ending", "stop", "1, 2", None),
                                     ("repeat", "backward", None, "3")]
    assert bars["9"].findtext("barline/ending") == "1., 2."


def test_repeats_by_hand():
    root = convert(FIXTURES / "repeats-by-hand.ly")
    check_timing(root)
    bars = measures(root)
    assert bars[1].find("barline[@location='left']/repeat").get("direction") == "forward"
    assert bars[2].findtext("barline/ending") == "1"
    right = bars[2].find("barline[@location='right']")
    assert right.find("ending").get("type") == "stop"
    assert right.find("repeat").get("direction") == "backward"
    assert bars[3].find("barline[@location='right']/ending").get("type") == "discontinue"


def test_hidden_tie():
    score = assemble(dump_events(FIXTURES / "hidden-tie.ly"))
    assert not [w for w in score.warnings if "tie" in w]
    root = musicxml.to_element(score)
    check_timing(root)
    tied = [(n.findtext("voice"), n.findtext("pitch/step"), n.find("tie").get("type"))
            for n in root.iter("note") if n.find("tie") is not None]
    # The B flat tied from voice 1 into voice 2 (the G within voice 1); the
    # hidden note not written.
    assert sorted(tied) == [("1", "B", "start"), ("1", "G", "start"), ("1", "G", "stop"),
                            ("2", "B", "stop")]
    assert len([n for n in root.iter("note") if n.findtext("voice") == "2"]) == 2


def test_tie_into_endings():
    root = convert(FIXTURES / "tie-into-endings.ly")
    check_timing(root)

    def ties(measure):
        first = notes(measures(root)[measure])[0]
        return [t.get("type") for t in first.findall("tie")]

    # Into the first ending as usual, into the second a stop alone.
    assert ties(2) == ["stop"] and ties(3) == ["stop"]
    assert ties(6) == ["stop"] and ties(7) == ["stop"]


def test_overlap_in_one_voice():
    root = convert(FIXTURES / "overlap-in-one-voice.ly")
    check_timing(root)
    first, second, third = measures(root)
    # The chords that overlap the B: a voice of their own, from the eighth.
    voices = [(n.findtext("voice"), n.findtext("pitch/step"), n.find("chord") is not None)
              for n in notes(first)]
    assert voices == [("1", "B", False), ("2", "F", False), ("2", "B", True),
                      ("2", "F", False), ("2", "B", True)]
    assert first.find("backup") is not None and first.find("forward") is not None
    # ees2.*1/2: a dotted half, in a voice of its own under the rest of its voice.
    rest, bass = sorted(notes(second), key=lambda n: int(n.findtext("duration")))
    assert (bass.findtext("type"), bass.find("dot") is not None) == ("half", True)
    assert int(bass.findtext("duration")) == 2 * int(rest.findtext("duration"))
    assert bass.find("time-modification") is None
    assert bass.findtext("voice") != rest.findtext("voice")
    assert notes(third)[0].findtext("voice") == "1"
