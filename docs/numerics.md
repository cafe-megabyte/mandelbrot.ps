# Numerical design

## Grid and budget

`renderDPI` selects the calculation resolution and defaults to 72 dpi. A value of
0 uses the larger component of the output device's `HWResolution`. This controls
the raster dimensions and iteration budget without changing the device settings.

For raster width `W`, height `H`, and logarithmic zoom `z`:

```text
base = max(3/W, 2.5/H)
s = base * 2^(-z)
cr = x + (column + 0.5 - W/2) * s
ci = y + (H/2 - row - 0.5) * s
N = 512 + 256 * ceil(max(0, -9 - log2(s)))
```

The common spacing preserves geometry. The actual PS spacing is represented by
an exact native binary mantissa `m` and a separate integer exponent `e`, with
`1 <= m < 2`. Native rounding in the initial division and fractional power of two
selects that dyadic grid. Centre coordinates retain their original decimal text.
Each adaptive retry encloses that complete decimal value afresh.

The budget is evaluated with the integer identity
`ceil(-9-log2(m*2^e)) = -9-e`. This avoids a logarithm/ceiling error at exact powers
of two and avoids underflow at zoom 1200 and beyond. The signed counter is checked
before multiplication. Pixel indexing is restricted to the native precision's
exact half-integer range, with an explicit error for an unrepresentable raster.

The image fits the imageable A4 rectangle at a common physical sample pitch.
Dimensions are rounded to the nearest integer, with a minimum of one sample.
Any remaining gap is smaller than one sample. The opposite signs of the PS page
axis and top-down raster rows are handled by the image matrix, not by changing
the sample coordinates.

## Exact arithmetic and reference orbit

A fixed-point value consists of a sign and little-endian base-32768 digits.
With `F` fractional digits, the unit is `2^(-15F)`. The largest multiplication
accumulator is `(32767^2 + 32767 + 32767) = 2^30-1`; all arithmetic fits signed
32-bit integers. This remains true on an interpreter with single-precision reals.

Decimal fractional digits are read backwards using exact long division by ten.
The parser returns floor and ceiling endpoints, including negative input. It
never converts the whole coordinate to a native real. Multiplication retains
discard information and rounds outwards. Addition and subtraction are exact.

The reference and direct fallback use outward rectangular intervals:

```text
r' = square(r) - square(i) + cr
i' = 2 * product(r, i) + ci
M = square(r') + square(i')
```

The first iteration with `lower(M)>4` is escaped. If `upper(M)<=4`, the step is
bounded. An ambiguous interval restarts with another 128 fractional bits. The
initial requested precision is `max(128, floor(zoom)+128)`, rounded up to 15 bits.
There is no silent fallback to black.

Separate dyadic coordinate intervals cannot prove an exact rational equality
such as `1.2^2+1.6^2=4`, regardless of precision. For an ambiguous first bailout,
the program also checks this equality with exact integer numerators and their
common decimal/binary denominator. The reference centre receives the same check.
Equality therefore remains bounded, including non-dyadic decimal coordinates.

Repeating all four endpoints at a checkpoint repeats the entire deterministic
interval map. If every intermediate upper magnitude was at most four, this is
an invariant enclosure cycle. It certifies the remaining budget. A repeated
native approximate point alone is not used as a certificate. The real interval
`[-2,1/4]` and strict, conservative cardioid/period-two tests give additional
interior certificates.

## Native and compensated arithmetic

The program measures the significand length `p` by halving an increment around
one; `u=2^-p`. Native decisions use a propagated complex radius and conservative
rounding reserves. The analytic interior margin is `16384u`. On the tested box,
coordinate uncertainty is below `256u`, the cardioid derivative contribution
below `8704u`, and its evaluation reserve below `256u`. Borderline inputs follow
the orbit rather than using the certificate.

An uncertain native/perturbation sample in ordinary exponent range first tries
compensated pairs. Dekker splitting uses `2^ceil(p/2)+1`; compensated sums and
products retain two native components without allocating inside the orbit loop.
The orbit reserve is `64u^2` times the operation scale, plus coordinate error.
Cached squares, complex error propagation, and a separate high/low bailout margin
preserve strict equality. Uncertain pairs use full fixed-point intervals.

These bounds assume binary round-to-nearest basic arithmetic, as provided by the
target interpreter families. Positive bounds are inflated after evaluation by
`1+32u`; a `1e-30` reserve covers native underflow in bounded error expressions.
On an interpreter with more precise reals this reserve is conservative.

## Scaled perturbation

Let `Z` be the reference orbit at exact centre `c0`, and let `dc` be the exact
dyadic pixel displacement. A pixel is represented as `z=Z+2^E*d`. The normalized
perturbation follows:

```text
d' = 2*Z*d + 2^E*d*d + dc/2^E
```

`E` is an integer, so it can represent an exponent far below native underflow.
Power-of-two rescaling keeps components in native range. Tiny omitted nonlinear
or coordinate terms are included in the error radius. Reference components and
the signed reference bailout gap are enclosed independently by the fixed kernel.

For perturbation radius `a`, reference error `b`, `S=2^E`, and coordinate error
`q`, the propagated radius encloses:

```text
(2*|Z| + 2*S*|d| + S*a)*a + 2*b*(|d|+a) + q + rounding
```

Magnitude testing uses the reference gap plus the correction
`2*Re(conj(Z)*d)+S*|d|^2` in scaled units, with its own propagated error. Every
iteration is tested unless the endpoint prefix below supplies a proof. Saturated
gap sentinels prove only a sign; actual reference/perturbation components are
used separately for the smooth-colour magnitude. An escaped reference can be
rebased against `Z0=0`; its uncertainty is included. A certified reference cycle
can instead be reused directly.

## Endpoint prefix at c0 = -2

Here `Z1=-2` and `Zn=2` for `n>=2`. Write `h=dc`. For `n>=2`:

```text
D_n = -(4^n/6 + 1/3)
delta_n = D_n*h + R_n
|R_n|_1 <= (4^n*|h|_1)^2
```

The remainder bound follows by induction from
`delta_(n+1)=4*delta_n+delta_n^2+h`, provided `4^n*|h|_1<=1/16`.
The starting error at iteration two is `h^2`. If `Q=4^n*|h|_1`, the next
remainder is at most `(4+(1+Q)^2)*Q^2`, strictly below `16*Q^2` on that domain.

Only positive real displacements use the prefix. For every skipped step,
the linear real component is negative. The bailout gap is at most
`-(2/3)*4^k*Re(h) + 6*(4^k*|h|_1)^2`. The program requires the stronger condition
`16*4^n*|h|_1^2 < Re(h)`, with input and rounding reserves. This proves that no
earlier escape was skipped, including iteration one. The native seed keeps
`Q` below approximately `2^-60` over the whole raster.

An uncertain endpoint pixel restarts the same prefix with outward fixed-point
intervals, initially at 192 bits. A smaller prefix is selected as precision grows.
Its explicit remainder encloses the quadratic tail, the omitted `-h/3`, and the
original tiny parameter displacement. If that reduced-precision enclosure is no
longer valid, the original full-precision pixel fallback is used. Thus the prefix
accelerates a proved calculation; it is not an assumed shared colour or a fill
from matching corners.

The exact vertical sample at `Re(c)=-2`, `Im(c)!=0` escapes in iteration one.
Its positive, potentially subnormal `Im(c)^2` is not rounded away in the bailout
decision. Exact real samples in `[-2,1/4]` are bounded by their invariant interval.

## Colour and symmetry

The seven palette stops follow the reference application. Every channel is an
integer rational interpolation rounded by `floor(v+1/2)`. There are 4096 entries.
Smooth colouring uses the first escape iteration and magnitude, including an
escape in iteration `N`. Phase reduction uses `(n+1) mod 128` before multiplying
by 96: `128*96` is a multiple of 4096. This avoids large floating iteration counts
and signed overflow. Negative indices are normalized modulo 4096.

Native `ln` supplies the final logarithms. RGB endpoint comparisons request a
more precise orbit if the colour enclosure exceeds one byte per channel.
Mathematical escape certification and colour rounding are separate; the language
does not prescribe identical transcendental rounding on every interpreter.

Conjugate reuse is enabled only when `2*y/s` is an exact integer and the reflected
rows overlap the raster. A native candidate is verified by exact fixed arithmetic.
No view is snapped to the real axis. A strip is painted once normally and once
with its vertical image matrix reversed; no half-image cache is retained.

## Memory and resource failures

The compact palette is 12,288 bytes. A reusable RGB strip is at most 65,535 bytes
(49,152 with the default 2048-column, eight-row strip). Large widths are split
horizontally. Optional coordinate caches contain `W+H` native values. Reference
records contain eight values per computed step in 4096-element blocks, allocated
on demand; proved cycles need only their prefix. Fixed workspace grows with the
requested precision, not the full image size. Interpreter display lists and the
output device's page storage are additional.

Save/restore releases each failed precision attempt and each pixel fallback.
Arrays, strings, signed counters, memory, and execution time remain finite. An
object-size or precision failure is reported rather than producing a black pixel.
As with any finite interval method, difficult exact comparisons beyond recognized
certificates can require further precision up to those resource limits.

## Sources

- [Reference view conversion and budget](https://github.com/cafe-megabyte/Mandelbrot/blob/cd7d63135096ac0f6ffe4d546422cc6f6c54d02f/web/view.js)
- [Reference scalar kernel and palette](https://github.com/cafe-megabyte/Mandelbrot/blob/cd7d63135096ac0f6ffe4d546422cc6f6c54d02f/core/mandelbrot.c)
- [Independent oracle design used for comparison](https://github.com/cafe-megabyte/Mandelbrot/blob/cd7d63135096ac0f6ffe4d546422cc6f6c54d02f/tests/numerical-oracle.js)
- [Adobe PostScript Language Reference, third edition](https://www.adobe.com/jp/print/postscript/pdfs/PLRM.pdf)
- [Ghostscript language and implementation limits](https://ghostscript.readthedocs.io/en/latest/Language.html)
