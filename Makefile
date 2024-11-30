prep:
	python3 -m pip install --user --upgrade setuptools wheel twine readme_renderer

pack:
	python3 -m build

check: pack
	python3 -m twine check dist/*

dist: pack
	python3 -m twine upload dist/*

lint:
	flake8 whiskey
