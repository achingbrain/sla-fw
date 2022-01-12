TEMPLATE = slafw.pot
LANGS = cs de en es fr it pl

SOURCES = $(wildcard ../*.py)

IN = $(wildcard */LC_MESSAGES/*.po)

OUT = $(IN:.po=.mo)

compile: $(OUT)

extract: $(TEMPLATE)

check: $(addprefix check_,$(LANGS))
	@echo $^

process: $(addprefix process_,$(LANGS))
	@echo $^

check_%: %/LC_MESSAGES/slafw.po ${TEMPLATE}
	@echo
	@echo "Checking $<"
	msgfmt --check-format $<
	msgcmp $^

process_%: %/LC_MESSAGES/slafw.po
	@echo
	msguniq -s $< > /tmp/slafw.po.uniq
	msgattrib --clear-previous --no-obsolete /tmp/slafw.po.uniq > $<
	msgattrib --set-obsolete --ignore-file=$(TEMPLATE) -o /tmp/slafw.po.uniq $<
	msgattrib --no-obsolete /tmp/slafw.po.uniq > $<
	rm /tmp/slafw.po.uniq
clean:
	rm -f $(TEMPLATE)
	rm -f $(OUT)

$(TEMPLATE): $(SOURCES)
	touch $@
	xgettext --from-code utf-8 -j -kN_ -o $@ $?

%.mo: %.po
	msgfmt --check-format -o $@ $<
