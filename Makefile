.DEFAULT_GOAL := help

ENV ?= local
TF      := terraform -chdir=infra
VARS    := -var-file=envs/$(ENV).tfvars
BACKEND := -backend-config=envs/$(ENV).backend.tfbackend

# The pinned AWS provider can't assume a role on top of an `aws login` sign-in, so Terraform
# gets the CLI's credentials for AWS_PROFILE; a failed export stops it before another profile can.
TF_AWS := $(if $(AWS_PROFILE),creds="$$(aws configure export-credentials --format env)" && eval "$$creds" && env -u AWS_PROFILE ,)$(TF)

# The IAM and dataset roots are admin-only, so they ignore the scoped AWS_PROFILE
# that .envrc sets (that profile can't exist until the IAM root has run).
AWS_ADMIN_PROFILE ?= default
IAM_TF      := AWS_PROFILE=$(AWS_ADMIN_PROFILE) terraform -chdir=infra/iam
IAM_VARS    := -var-file=iam.tfvars
IAM_BACKEND := -backend-config=backend.tfbackend
DATASET_TF      := AWS_PROFILE=$(AWS_ADMIN_PROFILE) terraform -chdir=infra/dataset
DATASET_BACKEND := -backend-config=backend.tfbackend

.PHONY: help install tflint-init \
	check lint format type tf-format \
	test integration \
	bootstrap backend doctor provision teardown \
	data snapshot analysis \
	iam-init iam-plan iam-apply iam-output iam-destroy \
	dataset-init dataset-plan dataset-apply dataset-destroy \
	init plan apply destroy lock \
	_check-backend

# Targets tagged `## ...` are listed under the nearest `##@ Section` header.
help:
	@if [ -t 1 ] && [ -z "$$NO_COLOR" ]; then t='\033[36m'; h='\033[1m'; r='\033[0m'; fi; \
	awk -v t="$$t" -v h="$$h" -v r="$$r" 'BEGIN {FS = ":.*## "} \
		NR == 1 {printf "Usage: make %s<target>%s [ENV=local]\n", t, r} \
		/^##@ / {printf "\n%s%s%s\n", h, substr($$0, 5), r} \
		/^[a-zA-Z_-]+:.*## / {printf "  %s%-15s%s %s\n", t, $$1, r, $$2}' $(MAKEFILE_LIST)


##@ Setup

install: ## Sync deps, install pre-commit hooks (both stages), install tflint plugins
	uv sync --all-groups --all-extras
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	tflint --init

tflint-init: ## Refresh tflint plugins after a .tflint.hcl version bump
	tflint --init


##@ Quality gates

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


##@ Testing

test: ## Run pytest with branch coverage
	uv run pytest --cov --cov-report=term-missing

integration: ## Run integration-marked tests (requires credentials and network access)
	uv run pytest -m integration -v


##@ Bootstrap

bootstrap: ## Create state bucket and write backend files for all environments (admin profile)
	@bash scripts/bootstrap.sh

provision: ## One-time: create IAM roles and the dataset bucket, and initialize Terraform for ENV=local
	$(MAKE) iam-init
	$(MAKE) iam-apply
	$(MAKE) dataset-init
	$(MAKE) dataset-apply
	$(MAKE) init ENV=local


doctor: ## Check that every AWS profile resolves to the right account (read-only)
	@bash scripts/doctor.sh

backend: ## Write backend files for all environments (used by CI; one STS call for the account ID)
	@bash scripts/bootstrap-backend.sh

teardown: ## Last step of a full teardown: delete the state bucket (admin profile; asks you to confirm)
	@bash scripts/teardown.sh

##@ Dataset snapshot

data: ## Download the pinned dataset snapshot into data/ and verify it (ADOPT=1 accepts a changed source)
	uv run python -m banking_agent.dataset download $(if $(filter 1,$(ADOPT)),--adopt)

snapshot: data ## Copy the pinned snapshot into this account's data bucket
	uv run python -m banking_agent.dataset upload

##@ Analysis

analysis: ## Profile the pinned snapshot, compute the workflow selection (ADR-0003), and analyze card support and traffic into docs/analysis/
	uv run python -m banking_agent.analysis all

##@ IAM module

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


##@ Dataset bucket

dataset-init: ## Initialize Terraform backend for the dataset bucket
	$(DATASET_TF) init -reconfigure $(DATASET_BACKEND)

dataset-plan: ## Preview changes to the dataset bucket
	$(DATASET_TF) plan

dataset-apply: ## Apply the dataset bucket (holds the pinned snapshots)
	$(DATASET_TF) apply

dataset-destroy: ## Destroy the dataset bucket and every snapshot in it (requires I_KNOW=1)
	@if [ "$(I_KNOW)" != "1" ]; then \
		echo "Refusing to delete every dataset snapshot. Re-run with I_KNOW=1."; exit 1; fi
	$(DATASET_TF) destroy


##@ Terraform (per ENV)

init: ## Initialize Terraform backend for ENV
	$(TF_AWS) init -reconfigure $(BACKEND)

plan: ## Preview infrastructure changes for ENV
	$(TF_AWS) plan $(VARS)

apply: _check-backend ## Apply infrastructure changes for ENV (refuses prototype unless I_KNOW=1)
	@if [ "$(ENV)" = "prototype" ] && [ "$(I_KNOW)" != "1" ]; then \
		echo "Refusing to apply prototype from local. CI owns prototype."; exit 1; fi
	$(TF_AWS) apply $(VARS)

destroy: _check-backend ## Destroy all infrastructure for ENV (requires explicit ENV; refuses prototype unless I_KNOW=1)
	@if [ "$(origin ENV)" != "command line" ] && [ "$(origin ENV)" != "environment" ]; then \
		echo "destroy requires explicit ENV (e.g. make destroy ENV=local). Refusing default."; exit 1; fi
	@if [ "$(ENV)" = "prototype" ] && [ "$(I_KNOW)" != "1" ]; then \
		echo "Refusing to destroy prototype. Re-run with I_KNOW=1."; exit 1; fi
	$(TF_AWS) destroy $(VARS)


##@ Maintenance

lock: ## Regenerate .terraform.lock.hcl for linux_amd64 + darwin (arm64/amd64) in all modules
	@find infra -name ".terraform.lock.hcl" -not -path "*/.terraform/*" -exec dirname {} \; | \
		xargs -I{} terraform -chdir={} providers lock \
		-platform=linux_amd64 -platform=darwin_amd64 -platform=darwin_arm64


# INTERNAL

# Verify the configured backend key matches ENV. Prevents the footgun where
# `make init ENV=prototype` followed by `make destroy` (defaulting to local)
# operates on the prototype state because the backend pointer persists in
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
