gh-package:
	mkdir -p dist
	rm -f dist/font-nexus.zip
	zip -9 -r dist/font-nexus.zip -- build.py font-nexus README.md
