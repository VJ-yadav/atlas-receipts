PY ?= .venv/bin/python
ifeq ($(wildcard $(PY)),)
PY := ../.venv/bin/python
endif

.PHONY: all check run pages test

# The full pipeline from the cache: receipts, probes, evidence, both pages, the planted test, the goals.
all: run test pages check

run:
	$(PY) -m receipts check --all --model   # model readings come from the cache: no cost unless pages changed
	$(PY) -m receipts probe > after/probes.txt

pages:
	$(PY) -m receipts metrics
	$(PY) -m receipts evidence
	$(PY) -m receipts review
	$(PY) -m receipts public

test:
	$(PY) -m receipts test

# The mechanical self-check: every goal in GOALS.md, plus the Atlas validator on the branch.
check:
	$(PY) -m receipts goals
	@if [ -d atlas-branch ]; then cd atlas-branch && node scripts/validate.js | tail -1; fi
