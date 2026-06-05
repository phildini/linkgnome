.PHONY: web-dev web-build web-install

web-install:
	cd web && uv sync && npm install && uv run build-css

web-dev:
	cd web && uv run devserver

web-css:
	cd web && uv run watch-css

web-build-css:
	cd web && uv run build-css
