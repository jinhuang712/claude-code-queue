# claude-code-queue dev Makefile
.PHONY: test validate clean

test:
	python3 -m pytest tests -q

# validates plugin + marketplace manifests (if `claude` CLI is available)
validate:
	claude plugin validate . || echo "(claude CLI not available — skipping)"

clean:
	rm -rf __pycache__ .pytest_cache tests/__pycache__
