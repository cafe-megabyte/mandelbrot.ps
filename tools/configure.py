#!/usr/bin/env python3
"""Copy URL view parameters into a standalone, self-computing PostScript file."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
COORDINATE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\Z", re.ASCII)
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z", re.ASCII)


def view_from_url(url: str) -> dict[str, str]:
    fragment = urlsplit(url).fragment if not url.startswith("#") else url[1:]
    fields = {}
    for item in fragment.split("&"):
        key, separator, value = item.partition("=")
        if key not in {"x", "y", "zoom"}:
            continue
        if not separator or key in fields:
            raise ValueError(f"Missing or duplicate URL parameter: {key}")
        # A URL fragment is not form-encoded: an unescaped '+' remains a sign.
        fields[key] = unquote(value)
    if fields.keys() != {"x", "y", "zoom"}:
        raise ValueError("The URL fragment must contain x, y, and zoom")
    return fields


def numeric(value: str, name: str, maximum: Decimal | None = None) -> str:
    if not NUMBER.fullmatch(value):
        raise ValueError(f"{name} must be a finite nonnegative number")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid {name}") from error
    if not number.is_finite() or number < 0 or (maximum is not None and number > maximum):
        raise ValueError(f"{name} is outside the supported counter range")
    return value


def configure(source: str, values: dict[str, str], *, landscape: bool | None = None,
              margin: str | None = None) -> str:
    for key in ("x", "y"):
        if not COORDINATE.fullmatch(values[key]):
            raise ValueError(f"{key} must be a plain decimal coordinate")
    numeric(values["zoom"], "zoom", Decimal(8388606))
    for key in ("x", "y", "zoom"):
        value = f"({values[key]})" if key != "zoom" else values[key]
        source, count = re.subn(rf"^/{key} .+ def$", lambda _: f"/{key} {value} def",
                                source, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"The source is missing its public {key} declaration")
    if landscape is not None:
        source = re.sub(r"^/landscape (?:true|false) def$",
                        f"/landscape {str(landscape).lower()} def", source, count=1, flags=re.MULTILINE)
    if margin is not None:
        numeric(margin, "margin")
        source = re.sub(r"^/marginMM .+ def$", f"/marginMM {margin} def", source,
                        count=1, flags=re.MULTILINE)
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="A Mandelbrot URL or its #x=...&y=...&zoom=... fragment")
    parser.add_argument("--x", default="-0.75", help="Exact decimal real coordinate")
    parser.add_argument("--y", default="0", help="Exact decimal imaginary coordinate")
    parser.add_argument("--zoom", default="0", help="Nonnegative logarithmic zoom level")
    orientation = parser.add_mutually_exclusive_group()
    orientation.add_argument("--landscape", dest="landscape", action="store_true")
    orientation.add_argument("--portrait", dest="landscape", action="store_false")
    parser.set_defaults(landscape=None)
    parser.add_argument("--margin-mm", help="Requested minimum margin on each side")
    parser.add_argument("--source", type=Path, default=ROOT / "mandelbrot.ps")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        values = view_from_url(args.url) if args.url else dict(x=args.x, y=args.y, zoom=args.zoom)
        result = configure(args.source.read_text(), values, landscape=args.landscape,
                           margin=args.margin_mm)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
