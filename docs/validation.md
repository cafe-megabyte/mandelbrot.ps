# Validation

Initially validated on 19 October 2026 with Ghostscript 10.08.0 on an Apple M5 Pro
(virtual machine, 24 GiB RAM). The interpreter exposes a 24-bit PostScript
significand. The resolution update was checked on 20 October 2026 as described
below. No result below is a browser-to-PostScript extrapolation.

## Automated checks

`make check` passes 32 tests (20 October 2026). The numerical oracle is a separate Python
implementation using arbitrary integers and outward interval arithmetic. It does
not call the production native, compensated, perturbation, or fixed-point orbit.

Coverage includes:

- All palette bytes, signed arithmetic and rounding, long decimal coordinates,
  exact rational equality on the escape circle, and compensated sums/products.
- The first escape iteration, equality at four, final-iteration escape, smooth
  colour wrapping, and budgets immediately around powers of two.
- Even/odd rasters, fractional zoom, both supplied views at zoom 20 and 1200,
  an unrelated complex centre at zoom 1200, and samples at zoom 12000.
- Independent checks of escape iteration for endpoint pixels with the accelerated
  interval restart; RGB differences at most one byte per channel on the test set.
- Exact symmetry alignment, unpaired panned rows, cache/cycle ablations, coordinate
  caches beyond 65535 elements, horizontal chunks, partial final chunks, strip
  heights 1/4/8/16/64, both orientations, and anisotropic device resolution.
- Exactly one output page, a zero operand stack before and after composition,
  and a reusable RGB buffer no larger than 65535 bytes.

## Calculation resolution update, 20 October 2026

`renderDPI` now defaults to 72, independently of the output device. The complete
32-test suite passes, including four added tests for resolution selection and
validation. Executing the actual Level 2 page setup on a 300 dpi Ghostscript
device gives a 72 dpi, 842 x 595 calculation raster. A custom value of 36.5 gives
427 x 302 samples. In both cases the output device remains at 300 dpi. Setting
`renderDPI` to 0 on a 3 x 6 dpi device selects 6 dpi and a 70 x 50 calculation
raster. Negative and nonnumeric settings produce an explicit configuration error.

The benchmark helper sets both calculation and device resolution from `--dpi`.
A fresh overview run at 6 dpi completed with a 70 x 50 raster and a 512-iteration
budget; its record is in `tmp/benchmark-resolution-override.json`. The complete
72 dpi renders, PDF, and previews below are retained from 19 October.

## Complete device renders

Command: `python3 tools/benchmark.py --dpi 72 --json tmp/benchmark-72.json`.
Calculation resolution matched the device resolution in these 19 October runs. These are single
local runs, not guaranteed runtimes. Wall time includes interpreter startup and
reference preparation; CPU time below measures the render loop. Peak RSS includes
the interpreter, its page storage, and output-device allocations.

| View | Raster | Budget | Wall seconds | Render CPU seconds | Peak RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: |
| overview | 842 x 595 | 512 | 17.203 | 17.17 | 23.0 |
| zoom20 | 842 x 595 | 5,376 | 264.863 | 264.76 | 23.4 |
| zoom1200 | 842 x 595 | 307,456 | 171.518 | 171.45 | 23.5 |

| View | Fixed-point fallback calls | Compensated retries | PPM SHA-256 prefix |
| --- | ---: | ---: | --- |
| overview | 145 | 5,455 | `70aefa733d4c1394` |
| zoom20 | 14,747 | 414,957 | `80c2f2738e3408eb` |
| zoom1200 | 14,132 | 0 | `5fcbfaa6703415a2` |

Higher resolutions and other centres can take substantially longer. No 300/600
dpi timing or Distiller runtime is claimed. The PS emits progress after completed
strips; a difficult pixel can delay the next progress message.

## Optimization comparisons

Command: `python3 tools/benchmark.py --dpi 6 --views overview --repeat 3 --ablate`.
Order was reversed on alternating rounds. All 18 resulting PPM files have the
same complete SHA-256 hash, including the symmetry and data-source variants.

| Variant | Median wall seconds | Observed range |
| --- | ---: | --- |
| default | 0.351 | 0.344-0.360 |
| no-cache | 0.348 | 0.345-0.353 |
| no-symmetry | 0.657 | 0.654-0.663 |
| single-row | 0.353 | 0.349-0.356 |
| unbound | 1.073 | 1.053-1.076 |
| procedure-source | 0.344 | 0.343-0.348 |

Binding and conjugate reuse have clear benefits in this control. Coordinate
caching, strip heights, and literal/procedural sources differ by only milliseconds
here; no general speed advantage is asserted for those small differences. The
eight-row literal-string path keeps a bounded buffer and reduces PDF image calls.

## Page and visual inspection

`output/pdf/mandelbrot.pdf` was produced from the standalone PS with a 72 dpi
pdfwrite device, rotation disabled, downsampling disabled, and Flate image
compression. It contains exactly one page with MediaBox
`[0, 0, 841.89, 595.28]`, matching landscape A4 to 0.01 point. Both inline and
referenced image filters are lossless Flate, not JPEG.

The PDF was rendered with Poppler and visually inspected. The overview and both
deep previews show correct orientation, continuous strips, and no distortion.
The overview PNG is rendered from the 72 dpi PDF; the two deep control previews
were calculated directly by the PS on a 36 dpi image device.

## Portability still requiring target access

Acrobat Distiller and physical printers were not installed or connected. Their
execution and device colour management have not been verified. The PS uses
standard Level 2 operators and arithmetic bounded for signed 32-bit integers;
Ghostscript tests alone do not establish Adobe implementation compatibility.

The source contains one `showpage`, no external-file reads, and only ASCII text.
Its first configurable declarations are `x`, `y`, and `zoom`.

Source SHA-256 for the original 19 October validation:

`42cda834431f819632fd23a09c3ef5d6e8b8f13a1007f68a4767ab707281ecac`

Source SHA-256 after the 20 October resolution update:

`839e8cdf5d85b0b2aa81de7168b4ac721e9625d52a6866671f8b1ee7816a69a6`
