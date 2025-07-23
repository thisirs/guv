DOMAIN = guv
LOCALEDIR = src/guv/locale
PYFILES = $(shell find src/guv -name '*.py' | sort)

test:
	uv run --no-editable pytest -v -rA --cache-clear

doc:
	uv run --group doc sphinx-build --builder html --fail-on-warning docs public

completion:
	for lang in $(shell ls $(LOCALEDIR)); do \
		LANG=$$lang uv run python -c "from guv.runner import print_completer; print_completer(shell='zsh')" > src/guv/data/_guv_zsh_$$lang; \
		LANG=$$lang uv run python -c "from guv.runner import print_completer; print_completer(shell='bash')" > src/guv/data/_guv_bash_$$lang; \
	done

i18n:
	@echo "Extracting messages from source files..."
	xgettext --language=Python --keyword=_ --output=$(DOMAIN).pot $(PYFILES)
	@echo "Updating translation files..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgmerge --update --backup=none $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po $(DOMAIN).pot; \
	done
	@echo "Compiling .po files to .mo..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgfmt -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).mo $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po; \
	done
	@echo "Checking for untranslated strings..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgfmt --check-format --verbose -o /dev/null $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po; \
	done

i18n-extract:
	@echo "Extracting messages from source files..."
	xgettext --language=Python --keyword=_ --output=$(DOMAIN).pot $(PYFILES)

i18n-update:
	@echo "Updating translation files..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgmerge --update --backup=none $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po $(DOMAIN).pot; \
	done

i18n-compile:
	@echo "Compiling .po files to .mo..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgfmt -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).mo $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po; \
	done

i18n-clean:
	rm -f $(DOMAIN).pot
	find $(LOCALEDIR) -name '*.mo' -delete

i18n-prune:
	@echo "Removing obsolete entries from .po files..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgattrib --no-obsolete -o $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po; \
	done

i18n-check:
	@echo "Checking for untranslated strings..."
	for lang in $(shell ls $(LOCALEDIR)); do \
		msgfmt --check-format --verbose -o /dev/null $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po; \
	done

i18n-stats:
	@echo "Translation statistics:"
	for lang in $(shell ls $(LOCALEDIR)); do \
		echo "$$lang:"; \
		msgfmt --statistics $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).po; \
	done


.PHONY: i18n-extract i18n-update i18n-compile i18n-clean test doc completion
