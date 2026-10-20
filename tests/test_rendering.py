"""Check the page device and strip compositor independently of orbit cost."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_mandelbrot import GS, LIBRARY, postscript


def read_ppm(path):
    data = Path(path).read_bytes()
    offset = 0

    def token():
        nonlocal offset
        while True:
            while data[offset:offset+1].isspace():
                offset += 1
            if data[offset:offset+1] != b"#":
                break
            offset = data.index(b"\n", offset) + 1
        end = offset
        while not data[end:end+1].isspace():
            end += 1
        value, offset = data[offset:end], end
        return value

    assert token() == b"P6"
    width, height, maximum = int(token()), int(token()), int(token())
    assert maximum == 255
    pixels = data[offset+1:]
    assert len(pixels) == width * height * 3
    return width, height, pixels


def render_mock(*, strip=8, symmetry=False, portrait=False, imaginary="0",
                mirror_sum=24, anisotropic=False, chunk=None):
    body = f"""
/verbose false def /landscape {str(not portrait).lower()} def
/renderDPI 0 def
/stripRows {strip} def /useSymmetry {str(symmetry).lower()} def /y ({imaginary}) def
validate preparePalette preparePage prepareView
/expectedMirrorSum {mirror_sum} def
% Encode conjugate row pairs identically and each column differently. The
% numerical tests cover the real kernel; this isolates image matrices/buffers.
/pixel {{ /mockY exch def /mockX exch def
  mockX 11 mul mockY 2 mul expectedMirrorSum sub abs 19 mul add 4096 mod 3 mul
}} bind def
count (stack-before:) print printValue (\\n) print
render showpage
buffer length 65535 le (buffer-ok:) print printValue (\\n) print
count (stack-after:) print printValue (\\n) print
end MandelbrotJobSave restore
"""
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "render.ps"
        library = LIBRARY
        if chunk:
            library = library.replace("/maxChunk 2048 65535 stripRows 3 mul idiv min def",
                                      f"/maxChunk {chunk} def")
        source.write_text(library + body)
        target = Path(directory) / "page-%02d.ppm"
        command = [GS, "-q", "-dBATCH", "-dNOPAUSE", "-dLanguageLevel=2",
                   "-sDEVICE=ppmraw", "-r3x6" if anisotropic else "-r3",
                   f"-sOutputFile={target}", str(source)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        assert "stack-before:0" in result.stdout, result.stdout
        assert "stack-after:0" in result.stdout, result.stdout
        assert "buffer-ok:true" in result.stdout, result.stdout
        pages = list(Path(directory).glob("page-*.ppm"))
        assert len(pages) == 1
        return read_ppm(pages[0])


def page_setup(*, device_dpi="300", render_dpi=None):
    """Inspect actual page setup without paying for an orbit or an output page."""
    override = "" if render_dpi is None else f"/renderDPI {render_dpi} def\n"
    body = """
/verbose false def
validate preparePage
dpi printValue ( ) print rasterWidth printValue ( ) print rasterHeight printValue
currentpagedevice /HWResolution get { ( ) print printValue } forall (\n) print
end MandelbrotJobSave restore
"""
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "setup.ps"
        source.write_text(LIBRARY + override + body)
        result = subprocess.run(
            [GS, "-q", "-dBATCH", "-dNOPAUSE", "-dLanguageLevel=2",
             "-sDEVICE=ppmraw", f"-r{device_dpi}", "-sOutputFile=/dev/null", str(source)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return tuple(map(float, result.stdout.split()))


@unittest.skipUnless(shutil.which(GS), "Ghostscript is required")
class RenderingTests(unittest.TestCase):
    def test_default_sampling_is_72_dpi_on_a_300_dpi_device(self):
        self.assertEqual(page_setup(), (72, 842, 595, 300, 300))

    def test_custom_sampling_accepts_fractional_dpi(self):
        self.assertEqual(page_setup(render_dpi="36.5"), (36.5, 427, 302, 300, 300))

    def test_zero_selects_the_larger_device_resolution(self):
        self.assertEqual(page_setup(device_dpi="3x6", render_dpi="0"), (6, 70, 50, 3, 6))

    def test_invalid_sampling_resolution_has_a_clear_error(self):
        for value in ("-1", "(72)", "true"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(AssertionError, "renderDPI must be"):
                    postscript(f"/renderDPI {value} def validate")

    def test_one_a4_page_and_orientation(self):
        landscape = render_mock()
        portrait = render_mock(portrait=True)
        self.assertEqual(landscape[:2], (35, 25))
        self.assertEqual(portrait[:2], (25, 35))

    def test_strip_heights_and_mirroring_are_identical(self):
        baseline = render_mock(strip=1)
        for height in (4, 8, 16, 64):
            with self.subTest(height=height):
                self.assertEqual(render_mock(strip=height), baseline)
                self.assertEqual(render_mock(strip=height, symmetry=True), baseline)

    def test_aligned_panned_symmetry_and_unpaired_rows(self):
        # At 3 dpi the raster is 35x25, giving the exact binary32 step below.
        imag = "0.0500000007450580596923828125"
        expected = render_mock(strip=1, imaginary=imag, mirror_sum=25)
        self.assertEqual(render_mock(strip=8, imaginary=imag, mirror_sum=25,
                                     symmetry=True), expected)

    def test_anisotropic_device_resolution(self):
        result = render_mock(anisotropic=True)
        self.assertEqual(result[:2], (35, 50))
        self.assertGreater(len(set(result[2])), 32)

    def test_horizontal_chunks_and_partial_last_chunk(self):
        expected = render_mock(strip=8)
        self.assertEqual(render_mock(strip=8, chunk=3), expected)
        self.assertEqual(render_mock(strip=8, chunk=3, symmetry=True), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
