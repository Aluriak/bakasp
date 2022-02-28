run:
	python bakasp_frontend.py examples/choose-your-character.json
run-making-teams:
	python bakasp_frontend.py examples/make-teams.json
run-failing-config:
	python bakasp_frontend.py examples/bad-config.json


t: test
test:
	python -m pytest -vv --doctest-modules *.py plugins
