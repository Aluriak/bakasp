run:
	python poc.py examples/choose-your-character.json
run-making-teams:
	python poc.py examples/make-teams.json
run-failing-config:
	python poc.py examples/bad-config.json


t: test
test:
	python -m pytest -vv --doctest-modules *.py plugins
