PROSPEKT ?= ../prospekt

.PHONY: build test check bodies serve

build:
	python3 gen/build.py

test:
	python3 -m unittest discover -s gen/tests -t .

# The built site is committed (GitHub Pages serves this repo as is),
# so CI rebuilds and fails if anything differs from what was committed.
check: build test
	git add -N . && git diff --exit-code --stat

bodies:
	python3 scripts/export_bodies.py $(PROSPEKT)/Prospekt/Models/CameraBody.swift

serve:
	python3 -m http.server 8000
