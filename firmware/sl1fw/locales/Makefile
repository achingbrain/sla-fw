TEMPLATE = sl1fw.pot
LANGS=cs de en es fr it pl

SOURCES = $(wildcard ../*.py ../pages/*.py)

IN = $(wildcard */LC_MESSAGES/*.po)

OUT = $(IN:.po=.mo)

compile: $(OUT)

extract: $(TEMPLATE)

check: $(addprefix check_,$(LANGS))
	@echo $^

check_%: %/LC_MESSAGES/sl1fw.po ${TEMPLATE}
	@echo
	@echo "Checking $<"
	msgcmp $^

clean:
	rm -f $(TEMPLATE)
	rm -f $(OUT)

$(TEMPLATE): $(SOURCES)
	touch $@
	xgettext --from-code utf-8 -j -kN_ -o $@ $?

%.mo: %.po
	msgfmt --check-format -o $@ $<
