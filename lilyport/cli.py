"""Command line:
  lilyport convert PIECE.ly -o PIECE.mxl   (or .musicxml)
  lilyport dump PIECE.ly [-o EVENTS.jsonl]"""
import argparse
import json
import sys

from . import __version__
from .frontend.lilypond import LilyPondError, dump_events
from .model.assemble import assemble
from .writers import musicxml


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lilyport", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert", help="write MusicXML (.mxl compressed, or .musicxml)")
    convert.add_argument("ly")
    convert.add_argument("-o", "--output", required=True)
    convert.add_argument("--score", type=int, default=1,
                         help="which \\score of the file (default: the first)")
    dump = commands.add_parser("dump", help="write the music LilyPond evaluated, as JSON lines")
    dump.add_argument("ly")
    dump.add_argument("-o", "--output", help="file to write (default: standard output)")
    args = parser.parse_args(argv)

    try:
        events = dump_events(args.ly)
    except LilyPondError as error:
        sys.stderr.write(error.log)
        sys.exit(f"lilyport: {error}")

    if args.command == "convert":
        score = assemble(events, args.score)
        for warning in score.warnings:
            print(f"lilyport: warning: {warning}", file=sys.stderr)
        musicxml.write(score, args.output)
    elif args.command == "dump":
        out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
        with out:
            for event in events:
                out.write(json.dumps(event, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
