#!/usr/bin/env python3
"""Exercise the actual PostScript program against independent integer intervals."""

from __future__ import annotations

import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "mandelbrot.ps").read_text()
LIBRARY = SOURCE.split("% -- Execution --")[0]
GS = os.environ.get("GS", "gs")
STOPS = [(0, 0, 7, 100), (655, 32, 107, 203), (1638, 180, 255, 255),
         (1966, 255, 245, 208), (2703, 255, 170, 0), (3522, 55, 13, 91),
         (4096, 0, 7, 100)]
COLOURFUL = (
    "-0.916497695153210002498843195227584798763509343899613668327219784259796142578125",
    "0.30649049995109267652617123279075849059081837477691578897065483033657073974609375",
)
DUMP = """
/dumpBig { dup 0 get printValue (:) print
  1 1 K { 1 index exch get printValue (,) print } for pop (\\n) print } bind def
"""


def postscript(body: str, *, library: str = LIBRARY, timeout: int = 180) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "test.ps"
        path.write_text(library + "\n/verbose false def\n" + DUMP + body + "\nend quit\n")
        result = subprocess.run(
            [GS, "-q", "-dBATCH", "-dNOPAUSE", "-dNODISPLAY", str(path)],
            text=True, capture_output=True, timeout=timeout,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout.splitlines()


def decode_big(text: str) -> int:
    sign, digits = text.split(":")
    return int(sign) * sum(int(digit) << (15 * j)
                           for j, digit in enumerate(digits.rstrip(",").split(",")))


def palette(index: int) -> tuple[int, int, int]:
    index %= 4096
    for first, second in zip(STOPS, STOPS[1:]):
        if index < second[0]:
            span = second[0] - first[0]
            return tuple((2 * (first[j] * span + (index - first[0]) *
                               (second[j] - first[j])) + span) // (2 * span)
                         for j in (1, 2, 3))
    raise AssertionError(index)


def colour(iteration: int, magnitude: float) -> tuple[int, int, int]:
    # Reduce the integer term before multiplying, independently of float(n).
    phase = 96 * ((iteration + 1) % 128) - math.ceil(
        96 * math.log2(0.5 * math.log2(magnitude)))
    return palette(phase)


def oracle(real: Fraction, imag: Fraction, limit: int, initial_bits: int = 192):
    """Outward integer intervals; never reuse the production orbit or shortcut."""
    for bits in range(initial_bits, initial_bits + 4097, 128):
        unit = 1 << bits

        def enclose(value):
            scaled = value * unit
            low = scaled.numerator // scaled.denominator
            return low, -((-scaled.numerator) // scaled.denominator)

        def square(value):
            a, b = value
            low = 0 if a <= 0 <= b else min(a * a, b * b)
            high = max(a * a, b * b)
            return low // unit, -((-high) // unit)

        def multiply(a, b):
            corners = [x * y for x in a for y in b]
            return min(corners) // unit, -((-max(corners)) // unit)

        cr, ci = enclose(real), enclose(imag)
        r = i = (0, 0)
        checkpoint = (r, i)
        next_checkpoint, span = 16, 16
        for iteration in range(1, limit + 1):
            rr, ii, ri = square(r), square(i), multiply(r, i)
            r = rr[0] - ii[1] + cr[0], rr[1] - ii[0] + cr[1]
            i = 2 * ri[0] + ci[0], 2 * ri[1] + ci[1]
            rr, ii = square(r), square(i)
            low, high = rr[0] + ii[0], rr[1] + ii[1]
            if iteration == 1 and real*real + imag*imag == 4:
                low = high = 4*unit
            if low > 4 * unit:
                a = colour(iteration, float(Fraction(low, unit)))
                b = colour(iteration, float(Fraction(high, unit)))
                if all(abs(x - y) <= 1 for x, y in zip(a, b)):
                    return iteration, a
                break
            if high > 4 * unit:
                break
            if (r, i) == checkpoint:
                return 0, (0, 0, 0)
            if iteration == next_checkpoint:
                checkpoint = r, i
                span *= 2
                next_checkpoint = iteration + span
        else:
            return 0, (0, 0, 0)
    raise AssertionError("The independent oracle could not resolve the point")


def view_setup(width=16, height=12, real="-0.75", imag="0", zoom=0, options=""):
    return (f"/x ({real}) def /y ({imag}) def /zoom {zoom} def\n"
            f"{options}\nvalidate preparePalette /rasterWidth {width} def "
            f"/rasterHeight {height} def prepareView\n")


def pixel_grid(width, height, real, imag, zoom, options=""):
    output = postscript(view_setup(width, height, real, imag, zoom, options) + """
F = fixedStep dumpBig iterations =
0 1 rasterHeight 1 sub { /testY exch def
  0 1 rasterWidth 1 sub { testY pixel = } for
} for
(stack:) print count =
""")
    fraction_digits = int(output[0])
    spacing = Fraction(decode_big(output[1]), 1 << (15 * fraction_digits))
    limit = int(output[2])
    assert output[-1] == "stack:0", output[-1]
    offsets = [int(value) for value in output[3:-1]]
    rgb = [(0, 0, 0) if offset < 0 else palette(offset // 3) for offset in offsets]
    return spacing, limit, rgb


@unittest.skipUnless(shutil.which(GS), "Ghostscript is required")
class ArithmeticTests(unittest.TestCase):
    def test_decimal_parser_and_outward_endpoints(self):
        values = ["0", "-0", "+.5", "-.125", "1.", "32769", "-99999.1",
                  "0.1", "-0.00000000000000000000000000000000000000001",
                  "-2.00000000000000000000000000000000000000000000000001"]
        random.seed(247)
        values += [f"{random.randint(-999999, 999999)}.{random.randrange(10**35):035}"
                   for _ in range(30)]
        body = "/integerDigits 5 def /stepMantissa 1 def /stepExponent -10 def 128 initializeFixed F =\n"
        for value in values:
            body += f"({value}) crL crH parseDecimal crL dumpBig crH dumpBig\n"
        body += "count ="
        output = postscript(body)
        unit = 1 << (15 * int(output[0]))
        for j, value in enumerate(values):
            exact = Fraction(value) * unit
            self.assertEqual(decode_big(output[1 + 2*j]), exact.numerator // exact.denominator, value)
            self.assertEqual(decode_big(output[2 + 2*j]), -((-exact.numerator) // exact.denominator), value)
        self.assertEqual(output[-1], "0")

    def test_signed_arithmetic_and_rounding(self):
        random.seed(952)
        values = [(str(random.uniform(-2, 2)), str(random.uniform(-2, 2))) for _ in range(60)]
        body = "/integerDigits 3 def /stepMantissa 1 def /stepExponent -10 def 128 initializeFixed F =\n"
        for a, b in values:
            body += (f"({a}) crL crH parseDecimal ({b}) ciL ciH parseDecimal\n"
                     "crL dumpBig ciL dumpBig crL ciL tempA bigAdd tempA dumpBig\n"
                     "crL ciL tempA bigSubtract tempA dumpBig\n"
                     "crL ciL tempA multiplyDown tempA dumpBig\n"
                     "crL ciL tempA multiplyUp tempA dumpBig\n")
        body += "count ="
        output = postscript(body)
        unit = 1 << (15 * int(output[0]))
        for j, _ in enumerate(values):
            a, b, total, difference, low, high = map(decode_big, output[1+6*j:7+6*j])
            self.assertEqual(total, a + b)
            self.assertEqual(difference, a - b)
            self.assertEqual(low, (a * b) // unit)
            self.assertEqual(high, -((-a * b) // unit))
        self.assertEqual(output[-1], "0")

    def test_all_palette_bytes(self):
        output = postscript("preparePalette palette { = } forall count =")
        expected = [value for index in range(4096) for value in palette(index)]
        self.assertEqual(list(map(int, output[:-1])), expected)
        self.assertEqual(output[-1], "0")

    def test_negative_phase_wrap_and_large_iteration(self):
        cases = [(1, 1e20), (2, 36), (100, 4.1), (305920, 5), (2147483392, 9)]
        output = postscript("preparePalette\n" + "\n".join(
            f"{n} {m} phaseIndex =" for n, m in cases))
        for actual, (n, m) in zip(map(int, output), cases):
            self.assertTrue(all(abs(a-b) <= 1 for a, b in zip(palette(actual), colour(n, m))))

    def test_compensated_products_and_sums(self):
        random.seed(882)
        pairs = [(random.uniform(-2, 2), random.uniform(-1e-8, 1e-8),
                  random.uniform(-2, 2), random.uniform(-1e-8, 1e-8)) for _ in range(30)]
        body = "/integerDigits 3 def /stepMantissa 1 def /stepExponent -10 def 128 initializeFixed F =\n"
        for values in pairs:
            body += "/values [" + " ".join(map(str, values)) + "] def\n"
            body += "values { 0 tempA fromDyadic tempA dumpBig } forall\n"
            for operation in ("ddAdd", "ddMultiply"):
                body += (f"values aload pop {operation} /dl exch def /dh exch def "
                         "dh 0 tempA fromDyadic tempA dumpBig dl 0 tempA fromDyadic tempA dumpBig\n")
        output = postscript(body)
        unit = 1 << (15*int(output[0]))
        for j in range(len(pairs)):
            ah, al, bh, bl, sh, sl, ph, pl = [Fraction(decode_big(x), unit)
                                             for x in output[1+8*j:9+8*j]]
            reserve = Fraction(64, 1 << 48)
            self.assertLessEqual(abs(sh+sl-(ah+al+bh+bl)), reserve*(abs(ah)+abs(bh)+1))
            self.assertLessEqual(abs(ph+pl-(ah+al)*(bh+bl)), reserve*(abs(ah*bh)+1))


@unittest.skipUnless(shutil.which(GS), "Ghostscript is required")
class NumericalTests(unittest.TestCase):
    def test_escape_equality_and_last_iteration(self):
        for real, imag, limit, expected in [("0", "0", 16, 0), ("-1", "0", 32, 0),
                                           ("1", "0", 3, 3), ("2", "0", 2, 2),
                                           ("2", "0", 1, 0), ("-2", "0", 40, 0)]:
            with self.subTest(real=real, limit=limit):
                output = postscript(view_setup(1, 1, real, imag, options="/useNative false def") +
                                    f"/iterations {limit} def 0 0 fixedPixel pop pop = count =")
                self.assertEqual(int(output[0]), expected)
                self.assertEqual(output[-1], "0")

    def check_grid(self, width, height, real, imag, zoom, options=""):
        spacing, limit, actual = pixel_grid(width, height, real, imag, zoom, options)
        for row in range(height):
            for column in range(width):
                cr = Fraction(real) + Fraction(2*column+1-width, 2) * spacing
                ci = Fraction(imag) + Fraction(height-2*row-1, 2) * spacing
                # Exact real parameters in [-2,1/4] have a known invariant
                # interval. Test that theorem separately from the slow oracle.
                if ci == 0 and -2 <= cr <= Fraction(1, 4):
                    expected = (0, 0, 0)
                else:
                    _, expected = oracle(cr, ci, limit, max(192, 2*math.ceil(zoom) + 256))
                got = actual[row*width+column]
                self.assertTrue(all(abs(a-b) <= 1 for a, b in zip(got, expected)),
                                (column, row, real, imag, zoom, got, expected))

    def test_overview_and_odd_grid(self):
        self.check_grid(10, 7, "-0.75", "0", 0)

    def test_fractional_zoom_and_nonzero_imaginary_coordinate(self):
        self.check_grid(8, 6, "-0.743", "0.13", 3.25)

    def test_colourful_zoom20(self):
        self.check_grid(8, 6, *COLOURFUL, 20)

    def test_extreme_zoom1200_even_grid(self):
        self.check_grid(8, 6, "-2", "0", 1200)

    def test_extreme_zoom1200_odd_grid(self):
        self.check_grid(7, 5, "-2", "0", 1200)

    def test_extreme_zoom_at_an_unrelated_complex_centre(self):
        # A large scaled-gap exponent proves escape, but its sentinel must
        # never replace the reference magnitude in the colour calculation.
        self.check_grid(2, 2, *COLOURFUL, 1200)

    def test_wide_endpoint_fallback_matches_escape_iteration(self):
        points = [(211, 0), (420, 0), (211, 148), (420, 148), (300, 70), (300, 148)]
        body = view_setup(421, 298, "-2", "0", 1200)
        body += "F = fixedStep dumpBig iterations =\n"
        for col, row in points:
            body += f"{col} {row} cuspPixel /hi exch def /lo exch def /n exch def n = n lo phaseIndex =\n"
        output = postscript(body)
        spacing = Fraction(decode_big(output[1]), 1 << (15 * int(output[0])))
        limit = int(output[2])
        for j, (col, row) in enumerate(points):
            cr = -2 + Fraction(2*col+1-421, 2)*spacing
            ci = Fraction(298-2*row-1, 2)*spacing
            iteration, expected = oracle(cr, ci, limit, 2800)
            self.assertEqual(int(output[3+2*j]), iteration, (col, row))
            self.assertTrue(all(abs(a-b) <= 1 for a, b in zip(palette(int(output[4+2*j])), expected)))

    def test_coordinate_cache_and_cycle_switches_preserve_results(self):
        a = pixel_grid(7, 5, "-0.75", "0", 0)[2]
        b = pixel_grid(7, 5, "-0.75", "0", 0,
                       "/useCoordinateCache false def /useCycle false def")[2]
        self.assertEqual(a, b)

    def test_chunked_coordinate_caches(self):
        for width, height, accessor in [(65537, 1, "getColumnOffset"),
                                        (1, 65537, "getRowOffset")]:
            output = postscript(view_setup(width, height, "0", "0", 0) +
                                f"0 {accessor} = 65536 {accessor} = count =")
            self.assertEqual(float(output[0]), -float(output[1]))
            self.assertEqual(output[-1], "0")

    def test_direct_and_accelerated_agree(self):
        for view in [(8, 6, "-0.75", "0", 0), (5, 4, *COLOURFUL, 20)]:
            with self.subTest(view=view):
                a = pixel_grid(*view)[2]
                b = pixel_grid(*view, "/useNative false def /useDoubleDouble false def /usePerturbation false def /useInterior false def")[2]
                for x, y in zip(a, b):
                    self.assertTrue(all(abs(i-j) <= 1 for i, j in zip(x, y)), (x, y))

    def test_budget_thresholds(self):
        for width, height, zoom in [(1536, 1280, 0), (1536, 1280, 1),
                                    (1535, 1279, 0), (1537, 1281, 0),
                                    (31, 20, 0.5), (4961, 7016, 0), (80, 60, 1200)]:
            body = view_setup(width, height, "0", "0", zoom,
                              "/usePerturbation false def")
            out = postscript(body + "iterations =")
            step = max(3/width, 2.5/height)
            expected = 512 + 256*math.ceil(max(0, -9-math.log2(step)+zoom))
            self.assertEqual(int(out[0]), expected, (width, height, zoom))

    def test_no_zoom1200_cutoff(self):
        output = postscript(view_setup(2, 2, "-2", "0", 12000) +
                            "0 0 pixel = 1 0 pixel = count =")
        self.assertGreaterEqual(int(output[0]), 0)
        self.assertGreaterEqual(int(output[1]), 0)
        self.assertEqual(output[-1], "0")

    def test_nondyadic_exact_circle_equality(self):
        # 1.2^2+1.6^2 is exactly four. More binary precision alone can never
        # prove this equality from separate rounded coordinate intervals.
        output = postscript(view_setup(1, 1, "1.2", "1.6", 4) +
                            "centreOnCircle = 0 0 fixedPixel pop pop = count =")
        self.assertEqual(output, ["true", "2", "0"])
        self.check_grid(2, 2, "1.2", "1.6", 4)

    def test_exact_symmetry_alignment(self):
        # W=24,H=16 gives step=5/32; y=5/64 shifts the mirror sum by one.
        for imag, expected in [("0", 15), ("0.078125", 16), ("0.01", -1)]:
            out = postscript(view_setup(24, 16, imag=imag) + "mirrorSum =")
            self.assertEqual(int(out[0]), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
