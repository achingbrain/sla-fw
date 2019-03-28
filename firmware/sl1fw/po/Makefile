TARGET = extract.pot

SOURCES = ../*.py

TRANSLATIONS = *.po

OUT = $(TRANSLATIONS:.po=.mo)

%.mo: %.po
	/usr/lib/python2.7/Tools/i18n/msgfmt.py $<

extract: $(TARGET)

clean:
	rm -f $(TARGET)
	rm -f $(OUT)

$(TARGET): $(SOURCES)
	touch $@
	xgettext -j -o $@ $?
