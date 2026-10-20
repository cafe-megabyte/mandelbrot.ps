#!/usr/bin/env python3
"""Measure actual Ghostscript renders and optional reversible optimizations."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from configure import ROOT, configure

VIEWS = {
    "overview": dict(x="-0.75", y="0", zoom="0"),
    "zoom20": dict(x="-0.916497695153210002498843195227584798763509343899613668327219784259796142578125",
                   y="0.30649049995109267652617123279075849059081837477691578897065483033657073974609375", zoom="20"),
    "zoom1200": dict(x="-2", y="0", zoom="1200"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gs", default="gs")
    parser.add_argument("--dpi", type=float, default=12,
                        help="Calculation and output device resolution (default: 12)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--views", nargs="+", choices=VIEWS, default=list(VIEWS))
    parser.add_argument("--ablate", action="store_true", help="Also compare cache, symmetry, strips, binding, and sources")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    original = (ROOT / "mandelbrot.ps").read_text()
    original = re.sub(r"(?m)^/renderDPI \S+ def$", f"/renderDPI {args.dpi:g} def", original)
    variants = {"default": lambda s: s}
    if args.ablate:
        variants.update({
            "no-cache": lambda s: s.replace("/useCoordinateCache true def", "/useCoordinateCache false def"),
            "no-symmetry": lambda s: s.replace("/useSymmetry true def", "/useSymmetry false def"),
            "single-row": lambda s: s.replace("/stripRows 8 def", "/stripRows 1 def"),
            "unbound": lambda s: s.replace("} bind def", "} def"),
            "procedure-source": lambda s: s.replace("data false 3 colorimage", "{ data } false 3 colorimage"),
        })
    records, hashes = [], {}
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for repeat in range(args.repeat):
            # Reverse alternating rounds to reduce order and warm-cache bias.
            sequence = list(variants.items())
            if repeat % 2:
                sequence.reverse()
            for name in args.views:
                for variant, transform in sequence:
                    source = directory / "render.ps"
                    output = directory / "render.ppm"
                    source.write_text(transform(configure(original, VIEWS[name])))
                    command = [args.gs, "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=ppmraw",
                               f"-r{args.dpi}", f"-sOutputFile={output}", str(source)]
                    if sys.platform == "darwin":
                        command = ["/usr/bin/time", "-l"] + command
                    started = time.perf_counter()
                    result = subprocess.run(command, text=True, capture_output=True, check=True)
                    elapsed = time.perf_counter() - started
                    raw = output.read_bytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    previous = hashes.setdefault(name, digest)
                    if digest != previous:
                        raise RuntimeError(f"Raster changed for {name}/{variant}")
                    memory = re.search(r"(\d+)\s+maximum resident set size", result.stderr)
                    stats = re.search(r"Completed in ([\d.]+) seconds; precise pixel fallbacks: (\d+); compensated retries: (\d+)", result.stdout)
                    raster = re.search(r"A4 raster: (\d+) x (\d+)", result.stdout)
                    budget = re.search(r"Iteration budget: (\d+); fixed precision: (\d+)", result.stdout)
                    record = dict(view=name, variant=variant, run=repeat+1, dpi=args.dpi,
                                  wall_seconds=round(elapsed, 3), sha256=digest,
                                  width=int(raster[1]), height=int(raster[2]),
                                  iterations=int(budget[1]), initial_fraction_bits=int(budget[2]),
                                  peak_rss_bytes=int(memory[1]) if memory else None,
                                  render_cpu_seconds=float(stats[1]) if stats else None,
                                  fixed_fallbacks=int(stats[2]) if stats else None,
                                  compensated_retries=int(stats[3]) if stats else None)
                    records.append(record)
                    print(json.dumps(record), flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
