# claude-code-queue dev Makefile
.PHONY: test install uninstall clean

test:
	python3 -m pytest tests -q

install:
	./scripts/install.sh

uninstall:
	./scripts/uninstall.sh

clean:
	rm -rf __pycache__ .pytest_cache tests/__pycache__
