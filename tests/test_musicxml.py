"""The MusicXML writer, on the fixtures and (when fetched) the Mutopia pieces.
Needs LilyPond (tools/fetch-lilypond.sh)."""
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path

import pytest

from lilyport.frontend.lilypond import dump_events, find_lilypond
from lilyport.model.assemble import assemble
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
    for measure in measures(root):
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
        if measure.get("implicit") != "yes" and measure.find("note/rest[@measure]") is None:
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
    first, second, third, fourth = measures(root)
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
