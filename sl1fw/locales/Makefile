TEMPLATE = sl1fw.pot
LANGS = cs de en es fr it pl

SOURCES = $(wildcard ../*.py ../pages/*.py ../pages/print/*.py)

IN = $(wildcard */LC_MESSAGES/*.po)

OUT = $(IN:.po=.mo)

compile: $(OUT)

extract: $(TEMPLATE)

check: $(addprefix check_,$(LANGS))
	@echo $^

process: $(addprefix process_,$(LANGS))
	@echo $^

check_%: %/LC_MESSAGES/sl1fw.po ${TEMPLATE}
	@echo
	@echo "Checking $<"
	msgfmt --check-format $<
	msgcmp $^

process_%: %/LC_MESSAGES/sl1fw.po
	@echo
	msguniq -s $< > /tmp/sl1fw.po.uniq
	msgattrib --clear-previous --no-obsolete /tmp/sl1fw.po.uniq > $<
	msgattrib --set-obsolete --ignore-file=$(TEMPLATE) -o /tmp/sl1fw.po.uniq $<
	msgattrib --no-obsolete /tmp/sl1fw.po.uniq > $<
	rm /tmp/sl1fw.po.uniq
clean:
	rm -f $(TEMPLATE)
	rm -f $(OUT)

$(TEMPLATE): $(SOURCES)
	touch $@
	xgettext --from-code utf-8 -j -kN_ -o $@ $?

%.mo: %.po
	msgfmt --check-format -o $@ $<
