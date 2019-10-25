TEMPLATE = sl1fw.pot

SOURCES = $(wildcard ../*.py ../pages/*.py)

IN = $(wildcard */LC_MESSAGES/*.po)

OUT = $(IN:.po=.mo)

compile: $(OUT)

extract: $(TEMPLATE)

clean:
	rm -f $(TEMPLATE)
	rm -f $(OUT)

$(TEMPLATE): $(SOURCES)
	touch $@
	xgettext --from-code utf-8 -j -kN_ -o $@ $?

%.mo: %.po
	msgfmt -o $@ $<
