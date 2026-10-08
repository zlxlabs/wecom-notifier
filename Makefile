test:
	python3 -m venv .venv
	.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt pytest
	.venv/bin/python -m pytest tests -q
