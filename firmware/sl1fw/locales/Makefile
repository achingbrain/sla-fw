TEMPLATE = sl1fw.pot

SOURCES = ../*.py

IN = $(wildcard */LC_MESSAGES/*.po)

OUT = $(IN:.po=.mo)

compile: $(OUT)

extract: $(TEMPLATE)

clean:
	rm -f $(TEMPLATE)
	rm -f $(OUT)

$(TEMPLATE): $(SOURCES)
	touch $@
	xgettext -j -o $@ $?

%.mo: %.po
	msgfmt -o $@ $<
