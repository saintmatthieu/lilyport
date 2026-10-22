"""The event listener, on small hand-written fixtures (needs LilyPond:
tools/fetch-lilypond.sh)."""
from pathlib import Path

import pytest

from lilyport.frontend.lilypond import dump_events, find_lilypond

FIXTURES = Path(__file__).with_name("fixtures")

try:
    find_lilypond()
except FileNotFoundError:
    pytestmark = pytest.mark.skip("LilyPond not found: run tools/fetch-lilypond.sh")


@pytest.fixture(scope="module")
def two_bars():
    return dump_events(FIXTURES / "two-bars.ly")


def notes(events):
    return [e for e in events if e["kind"] == "note"]


def test_pitches_are_spelled(two_bars):
    # The triplet's F sharp (bar 2), not a G flat.
    f_sharp = [n for n in notes(two_bars) if n["pitch"]["step"] == 3]
    assert [n["pitch"]["alter"] for n in f_sharp] == [0.5]


def test_staves_and_voices(two_bars):
    upper = {e["staff"] for e in notes(two_bars) if e["pitch"]["octave"] >= 0}
    lower = {e["staff"] for e in notes(two_bars) if e["pitch"]["octave"] < -1}
    assert len(upper) == 1 and len(lower) == 1 and upper != lower
    # Bar 1 of the upper staff has two voices.
    first_beat = [n for n in notes(two_bars) if n["t"] == [0, 1, 0, 1] and n["staff"] in upper]
    assert len({n["voice"] for n in first_beat}) == 2


def test_tuplet_grace_and_tie(two_bars):
    triplet = [n for n in notes(two_bars) if n["duration"]["factor"] == [2, 3]]
    assert len(triplet) == 3
    grace = [n for n in notes(two_bars) if n["t"][2] != 0]
    assert len(grace) == 1 and grace[0]["t"][2:] == [-1, 16]
    assert sum(e["kind"] == "tie" for e in two_bars) == 1


def test_score_and_staff_settings(two_bars):
    kinds = [e["kind"] for e in two_bars]
    assert kinds.count("time") == 1 and kinds.count("clef") == 2 and kinds.count("key") == 2
    time = next(e for e in two_bars if e["kind"] == "time")
    assert time["fraction"] == [3, 4]


def test_header_per_engraved_score():
    events = dump_events(FIXTURES / "headers.ly")
    headers = {e["score"]: e["fields"] for e in events if e["kind"] == "header"}
    # The MIDI-only score is not engraved: no events, no header.
    assert sorted(headers) == [1, 2, 3, 4]
    # A score's field hides the book's, which hides the top level's; markups as text.
    assert headers[1] == {"title": "Book title", "piece": "First",
                          "composer": "A. Composer", "copyright": "Public Domain"}
    assert headers[2]["title"] == "Second" and "piece" not in headers[2]
    # Book parts, in source order.
    assert [headers[3]["title"], headers[4]["title"]] == ["Part 1", "Part 2"]
