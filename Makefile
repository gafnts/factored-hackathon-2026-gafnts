.DEFAULT_GOAL := help

ENV ?= local
TF      := terraform -chdir=infra
VARS    := -var-file=envs/$(ENV).tfvars
BACKEND := -backend-config=envs/$(ENV).backend.tfbackend

# The IAM bootstrap module is admin-only, so it ignores the scoped AWS_PROFILE
# that .envrc sets (that profile can't exist until this module has run).
AWS_ADMIN_PROFILE ?= default
IAM_TF      := AWS_PROFILE=$(AWS_ADMIN_PROFILE) terraform -chdir=infra/iam
IAM_VARS    := -var-file=iam.tfvars
IAM_BACKEND := -backend-config=backend.tfbackend

.PHONY: help install tflint-init \
	check lint format type tf-format \
	test integration \
	bootstrap backend doctor provision teardown \
	iam-init iam-plan iam-apply iam-output iam-destroy \
	init plan apply destroy lock \
	_check-backend

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'


# LOCAL DEVELOPMENT SETUP

install: ## Sync deps, install pre-commit hooks (both stages), install tflint plugins
	uv sync --all-groups --all-extras
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	tflint --init

tflint-init: ## Refresh tflint plugins after a .tflint.hcl version bump
	tflint --init


# QUALITY GATES

check: ## Run every pre-commit hook against every file (both stages)
	uv run pre-commit run --all-files --hook-stage pre-commit
	uv run pre-commit run --all-files --hook-stage pre-push

lint: ## Run ruff check on src and tests
	uv run ruff check src tests

format: ## Apply ruff lint fixes and formatting to src and tests
	uv run ruff check src tests --fix
	uv run ruff format src tests

type: ## Run mypy on src and tests
	uv run mypy src tests

tf-format: ## Format all Terraform files
	$(TF) fmt -recursive


# TESTING

test: ## Run pytest with branch coverage
	uv run pytest --cov --cov-report=term-missing

integration: ## Run integration-marked tests (requires credentials and network access)
	uv run pytest -m integration -v


# BOOTSTRAP & PROVISIONING

bootstrap: ## Create state bucket and write backend files for all environments (admin profile)
	@bash scripts/bootstrap.sh

backend: ## Write backend files for all environments (used by CI; one STS call for the account ID)
	@bash scripts/bootstrap-backend.sh

doctor: ## Check that every AWS profile resolves to the right account (read-only)
	@bash scripts/doctor.sh

teardown: ## Last step of a full teardown: delete the state bucket (admin profile; asks you to confirm)
	@bash scripts/teardown.sh

provision: ## One-time: create IAM roles and initialize Terraform for ENV=local
	$(MAKE) iam-init
	$(MAKE) iam-apply
	$(MAKE) init ENV=local


# IAM BOOTSTRAP MODULE

iam-init: ## Initialize Terraform backend for the IAM bootstrap module
	$(IAM_TF) init -reconfigure $(IAM_BACKEND)

iam-plan: ## Preview changes to the IAM bootstrap module
	$(IAM_TF) plan $(IAM_VARS)

iam-apply: ## Apply the IAM bootstrap module (creates deploy roles)
	$(IAM_TF) apply $(IAM_VARS)

iam-output: ## Print the deploy role ARNs (for your AWS profile and the GitHub variables)
	$(IAM_TF) output

iam-destroy: ## Destroy the IAM bootstrap module (removes every deploy role; requires I_KNOW=1)
	@if [ "$(I_KNOW)" != "1" ]; then \
		echo "Refusing to destroy the deploy roles for every env. Re-run with I_KNOW=1."; exit 1; fi
	$(IAM_TF) destroy $(IAM_VARS)


# TERRAFORM LIFECYCLE

init: ## Initialize Terraform backend for ENV
	$(TF) init -reconfigure $(BACKEND)

plan: ## Preview infrastructure changes for ENV
	$(TF) plan $(VARS)

apply: _check-backend ## Apply infrastructure changes for ENV (refuses demo unless I_KNOW=1)
	@if [ "$(ENV)" = "demo" ] && [ "$(I_KNOW)" != "1" ]; then \
		echo "Refusing to apply demo from local. CI owns demo."; exit 1; fi
	$(TF) apply $(VARS)

destroy: _check-backend ## Destroy all infrastructure for ENV (requires explicit ENV; refuses demo unless I_KNOW=1)
	@if [ "$(origin ENV)" != "command line" ] && [ "$(origin ENV)" != "environment" ]; then \
		echo "destroy requires explicit ENV (e.g. make destroy ENV=local). Refusing default."; exit 1; fi
	@if [ "$(ENV)" = "demo" ] && [ "$(I_KNOW)" != "1" ]; then \
		echo "Refusing to destroy demo. Re-run with I_KNOW=1."; exit 1; fi
	$(TF) destroy $(VARS)


# MAINTENANCE

lock: ## Regenerate .terraform.lock.hcl for linux_amd64 + darwin (arm64/amd64) in all modules
	@find infra -name ".terraform.lock.hcl" -not -path "*/.terraform/*" -exec dirname {} \; | \
		xargs -I{} terraform -chdir={} providers lock \
		-platform=linux_amd64 -platform=darwin_amd64 -platform=darwin_arm64


# INTERNAL

# Verify the configured backend key matches ENV. Prevents the footgun where
# `make init ENV=demo` followed by `make destroy` (defaulting to local)
# operates on the demo state because the backend pointer persists in
# infra/.terraform/terraform.tfstate across runs.
_check-backend:
	@if [ ! -f infra/.terraform/terraform.tfstate ]; then \
		echo "Terraform not initialized. Run 'make init ENV=$(ENV)' first."; exit 1; fi
	@current=$$(grep -o '"key": *"[^"]*"' infra/.terraform/terraform.tfstate | head -1 | sed 's/.*"\([^"]*\)"$$/\1/'); \
	expected="service/$(ENV)/terraform.tfstate"; \
	if [ "$$current" != "$$expected" ]; then \
		echo "Backend mismatch: configured key is '$$current' but ENV=$(ENV) expects '$$expected'."; \
		echo "Run 'make init ENV=<env>' to reconfigure the backend before continuing."; \
		exit 1; \
	fi
