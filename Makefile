GS ?= gs
PYTHON ?= python3
DPI ?= 72

.PHONY: check preview pdf

check:
	$(PYTHON) -m unittest discover -s tests -v

preview:
	mkdir -p previews
	$(GS) -q -dBATCH -dNOPAUSE -sDEVICE=png16m -r$(DPI) -sOutputFile=previews/overview.png mandelbrot.ps

pdf:
	mkdir -p output/pdf
	$(GS) -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -r$(DPI) -dAutoRotatePages=/None -dDownsampleColorImages=false -dAutoFilterColorImages=false -dColorImageFilter=/FlateEncode -sOutputFile=output/pdf/mandelbrot.pdf mandelbrot.ps
