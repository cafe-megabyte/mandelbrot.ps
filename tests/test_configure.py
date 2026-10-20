"""Check that URL configuration preserves digits and cannot inject PS code."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("configure", ROOT / "tools/configure.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfigureTests(unittest.TestCase):
    def test_long_coordinates_are_preserved_verbatim(self):
        coordinate = "-0." + "1234567890" * 80
        fields = MODULE.view_from_url(f"https://example.test/#x={coordinate}&y=+0.5&zoom=1200")
        result = MODULE.configure((ROOT / "mandelbrot.ps").read_text(), fields, landscape=False)
        self.assertIn(f"/x ({coordinate}) def", result)
        self.assertIn("/y (+0.5) def", result)
        self.assertIn("/zoom 1200 def", result)
        self.assertIn("/landscape false def", result)
        declarations = [line for line in result.splitlines() if line.startswith("/")][:3]
        self.assertEqual([line.split()[0] for line in declarations], ["/x", "/y", "/zoom"])

    def test_missing_and_duplicate_parameters_are_rejected(self):
        for fragment in ["#x=0&y=0", "#x=0&x=1&y=0&zoom=1"]:
            with self.assertRaises(ValueError):
                MODULE.view_from_url(fragment)

    def test_nonfinite_negative_and_injected_values_are_rejected(self):
        source = (ROOT / "mandelbrot.ps").read_text()
        for fields in [dict(x="0) showpage (", y="0", zoom="0"),
                       dict(x="0", y="0", zoom="nan"),
                       dict(x="0", y="0", zoom="-1"),
                       dict(x="0", y="0", zoom="1e100")]:
            with self.assertRaises(ValueError):
                MODULE.configure(source, fields)


if __name__ == "__main__":
    unittest.main()
