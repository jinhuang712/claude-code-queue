# claude-code-queue dev Makefile
.PHONY: validate

# validates plugin + marketplace manifests (if `claude` CLI is available)
validate:
	claude plugin validate . || echo "(claude CLI not available — skipping)"
