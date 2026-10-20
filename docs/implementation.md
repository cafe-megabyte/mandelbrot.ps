# Implementation decisions

Accepted on 19 October 2026, following the Mandelbrot PostScript implementation
plan of the same date. All source, comments, tools, and documentation are English.
The resolution decision was revised on 20 October 2026 at the user's request.

| Decision | Implementation |
| --- | --- |
| Interpreters | Ghostscript and Acrobat Distiller; standard LanguageLevel 2, also accepted by Level 3 interpreters. No extension-dependent arithmetic or parallel execution. Level 1 is not required. |
| Real precision | Measure the significand at runtime. Do not infer it from a 64-bit executable. The installed Ghostscript 10.08.0 exposes 24-bit PostScript reals. |
| Zoom | No chosen zoom ceiling. Native, compensated, and scaled perturbation paths feed an adaptive fixed-point interval fallback. Integer, VM, and object-size limits still apply. |
| Page | A4; `landscape` selects orientation at setup time. Default landscape, requested margin zero. Use the actual imageable area and report device clipping. |
| Resolution | `renderDPI` defaults to 72 dpi, independently of the device. Positive values select calculation resolution; 0 reads `HWResolution` and uses its larger component for anisotropic devices. Never stretch the fractal. |
| Numerical target | Correct escape semantics and deterministic computation. Fix final-iteration escape. Exact browser raster hashes are not the target. Validate RGB to one byte per channel against the independent oracle on the test set. |

The default view is `x=-0.75`, `y=0`, `zoom=0`. The two supplied URLs are retained
as the `zoom20` and `zoom1200` cases in `tools/benchmark.py`. Coordinate text is
kept verbatim by `tools/configure.py`.

## Acceptance work

1. **Numerical prototype:** signed integer arithmetic, exact decimal enclosures,
   pixel centres, strict bailout, and palette were checked before page output.
2. **Deep arithmetic:** scaled exponents support values beyond real underflow.
   An exact reference orbit and conservative errors control perturbations.
   A proved endpoint prefix and an interval restart handle `x=-2, y=0` efficiently.
3. **Colour:** all 4096 palette entries are checked. Smooth phase reduction
   preserves integer iterations even when an iteration number exceeds the native
   real's exact integer range.
4. **Page:** one A4 page, portrait and landscape, strip heights 1 through 64,
   conjugate reuse, aligned pans, anisotropic resolution, and stack balance are
   tested. One lossless PDF is also inspected visually and by its MediaBox.
5. **Optimizations:** cached coordinates and squares, bound procedures, analytic
   interiors, exact enclosure cycles, compensated retries, reusable strips, and
   conjugate symmetry are implemented. Timing comparisons preserve raster bytes.
6. **Delivery:** the standalone PS, URL configuration helper, tests, numerical
   explanation, benchmark helper, and previews are included.

This is an independent PS implementation, not a mechanical port of the C/WASM
engine. General degree-eight series, Karatsuba multiplication, SIMD, and BLA
tables are not ported. Scaled perturbation and adaptive direct intervals remain
available for other deep centres; their runtime can be substantially longer.

Ghostscript validation is automated. Acrobat Distiller and a physical printer
are unavailable in this environment, so their execution is explicitly unverified.
For a Distiller check, set `renderDPI` (0 follows its device resolution), disable downsampling/lossy
compression, process all three reference views, and confirm one A4 page with the
selected orientation. No browser runtime has been extrapolated to PostScript.
