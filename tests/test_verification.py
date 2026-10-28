"""lilyport's MusicXML read by programs that didn't write it (tests/verify.py):
valid against the MusicXML 4.0 schema (tools/fetch-schema.sh), and played by
Verovio as LilyPond plays the source. Needs LilyPond and the test extras."""
import tempfile
from pathlib import Path

import pytest

from lilyport.frontend.lilypond import dump_events, find_lilypond
from lilyport.model.assemble import assemble
from lilyport.writers.musicxml import to_string
from verify import (ADD_MIDI, SCHEMA, UNFOLD_REPEATS, lilypond_midi_files,
                    midi_differences, schema_errors)

FIXTURES = Path(__file__).with_name("fixtures")
CORPUS = Path(__file__).resolve().parents[1] / ".corpus"
# Files with several \book blocks name their MIDI files ambiguously; a
# score with only a \midi has a MIDI file and no events.
NO_MIDI = {"headers.ly", "tempo-twin.ly"}
# Compared with Verovio playing the repeats once: repeats set by hand
# (repeatCommands), which LilyPond plays once; ties into a second ending,
# a stop alone, which Verovio strikes again (LilyPond's unfolded MIDI holds).
PLAYED_ONCE = {"repeats-by-hand.ly", "tie-into-endings.ly"}

try:
    find_lilypond()
except FileNotFoundError:
    pytestmark = pytest.mark.skip("LilyPond not found: run tools/fetch-lilypond.sh")

SNORTUM = CORPUS / "imslp" / "snortum-op9" / "Frederic-Chopin-Nocturnes-Op9.ly"
# (file, scores to check: None for all)
PIECES = [pytest.param(path, None, id=path.stem) for path in sorted(FIXTURES.glob("*.ly"))] + [
    pytest.param(CORPUS / "mutopia" / "moonlight1-a4.converted.ly", None, id="moonlight"),
    pytest.param(CORPUS / "mutopia" / "chopin_nocturne_op9_n2.converted.ly", None,
                 id="nocturne-mutopia"),
    pytest.param(SNORTUM, [1], id="snortum-no1"),
    pytest.param(SNORTUM, [2], id="snortum-no2"),
    pytest.param(SNORTUM, [3], id="snortum-no3", marks=pytest.mark.xfail(
        reason="Verovio crashes on its cadenza (bar 155: one-note tuplets, a scaled "
               "chord); lilyport warns of ties leading nowhere: to look into")),
]


@pytest.mark.parametrize("ly, scores", PIECES)
def test_read_by_others(ly, scores):
    if not ly.exists():
        pytest.skip(f"{ly.name}: not fetched (tools/fetch-corpus.sh, or by hand)")
    if not SCHEMA.exists():
        pytest.skip("no MusicXML schema: run tools/fetch-schema.sh")
    with tempfile.TemporaryDirectory() as work:
        events = dump_events(ly, keep_midi_in=work, settings=[ADD_MIDI])
        midis = [] if ly.name in NO_MIDI else \
            [path.read_bytes() for path in lilypond_midi_files(work, ly.stem)]
    # Verovio plays the repeats: LilyPond's MIDI (and the events its
    # comparison reads) from the music unfolded.
    repeats = ly.name not in PLAYED_ONCE
    played = events
    if midis and repeats and any(e["kind"] == "repeat" for e in events):
        with tempfile.TemporaryDirectory() as work:
            played = dump_events(ly, keep_midi_in=work, settings=[ADD_MIDI, UNFOLD_REPEATS])
            midis = [path.read_bytes() for path in lilypond_midi_files(work, ly.stem)]
    problems = []
    for score in scores or sorted({e["score"] for e in events}):
        scored = [e for e in events if e["score"] == score]
        xml = to_string(assemble(scored, score))
        problems += [f"score {score}: {error}" for error in schema_errors(xml)]
        if midis:
            problems += [f"score {score}: {difference}" for difference in midi_differences(
                midis[score - 1], xml, [e for e in played if e["score"] == score], repeats)]
    assert not problems, "\n".join(problems[:30])
