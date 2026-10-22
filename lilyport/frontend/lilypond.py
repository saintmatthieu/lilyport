"""Running LilyPond with lilyport's event listener."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

EVENTS_LY = Path(__file__).with_name("events.ly")
COMPAT_LY = Path(__file__).with_name("compat.ly")
REPO_TOOLS = Path(__file__).resolve().parents[2] / ".tools"


class LilyPondError(RuntimeError):
    def __init__(self, message, log):
        super().__init__(message)
        self.log = log


def find_lilypond():
    """The LilyPond to run: $LILYPOND, else the newest one in the repository's
    .tools/ (tools/fetch-lilypond.sh), else `lilypond` on the PATH."""
    if os.environ.get("LILYPOND"):
        return os.environ["LILYPOND"]
    installs = sorted(REPO_TOOLS.glob("lilypond-*/bin/lilypond"),
                      key=lambda p: [int(x) for x in p.parts[-3].split("-")[1].split(".")])
    if installs:
        return str(installs[-1])
    found = shutil.which("lilypond")
    if found:
        return found
    raise FileNotFoundError("LilyPond not found: run tools/fetch-lilypond.sh, "
                            "or set LILYPOND")


def dump_events(ly_file, lilypond=None, keep_midi_in=None):
    """Runs LilyPond on ly_file with the event listener and returns the events
    (a list of dicts, see events.ly). No PDF is written; a \\midi block's MIDI
    file goes to keep_midi_in if given, else is discarded."""
    ly_file = Path(ly_file).resolve()
    with tempfile.TemporaryDirectory(prefix="lilyport-") as work:
        events_path = Path(work) / "events.jsonl"
        output_dir = Path(keep_midi_in) if keep_midi_in else Path(work)
        command = [lilypond or find_lilypond(),
                   "-dno-print-pages",
                   f"-dinclude-settings={COMPAT_LY}",
                   f"-dinclude-settings={EVENTS_LY}",
                   "-o", str(output_dir / ly_file.stem),
                   str(ly_file)]
        result = subprocess.run(command, cwd=ly_file.parent, capture_output=True,
                                text=True, env={**os.environ, "LILYPORT_EVENTS": str(events_path)})
        if result.returncode != 0:
            errors = [line for line in result.stderr.splitlines() if "error:" in line]
            raise LilyPondError(f"LilyPond failed on {ly_file}: {errors[0] if errors else 'see log'}",
                                result.stderr)
        if not events_path.exists():
            raise LilyPondError(f"No events from {ly_file} (does it have a \\layout?)",
                                result.stderr)
        with open(events_path, encoding="utf-8") as events:
            return [json.loads(line) for line in events]
