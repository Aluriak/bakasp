
aas:
	python aas.py examples/empty.json

run:
	python bakasp.py examples/choose-your-character.json
run-making-teams:
	python bakasp.py examples/make-teams.json
run-failing-config:
	python bakasp.py examples/bad-config.json


t: test
test:
	python -m pytest -vv --doctest-modules *.py plugins


clean:
	- rm states/*
