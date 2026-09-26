#!/usr/bin/env bash
set -euo pipefail

# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/common.sh"

# Admin only, even if .envrc already points AWS_PROFILE at the local role.
export AWS_PROFILE="${ADMIN_PROFILE}"

IDENTITY=$(aws sts get-caller-identity --query '[Account,Arn]' --output text)
read -r ACCOUNT_ID PRINCIPAL_ARN <<< "${IDENTITY}"
assert_not_organizer "${ACCOUNT_ID}"
BUCKET=$(state_bucket_name "${ACCOUNT_ID}")

# The CI roles trust the GitHub OIDC tokens of the repository `origin` points
# at. Their subject carries the owner and repository IDs, so ask GitHub for it
# rather than build it from the name. Resolved before anything is created.
if [ -z "${GITHUB_OIDC_SUBJECT_PREFIX:-}" ]; then
  ORIGIN_URL=$(git remote get-url origin)
  ORIGIN_REPO="${ORIGIN_URL%.git}"
  ORIGIN_REPO="${ORIGIN_REPO#*github.com[:/]}"
  if [[ ! "${ORIGIN_REPO}" =~ ^[^/]+/[^/]+$ ]]; then
    echo "Refusing to continue: origin (${ORIGIN_URL}) is not a GitHub repository." >&2
    echo "Point origin at your fork, or set GITHUB_OIDC_SUBJECT_PREFIX yourself." >&2
    exit 1
  fi
  if ! GITHUB_OIDC_SUBJECT_PREFIX=$(gh api "repos/${ORIGIN_REPO}/actions/oidc/customization/sub" --jq .sub_claim_prefix); then
    echo "Could not read the OIDC subject prefix of ${ORIGIN_REPO} with the GitHub CLI." >&2
    echo "Sign in with 'gh auth login', or set GITHUB_OIDC_SUBJECT_PREFIX yourself." >&2
    exit 1
  fi
fi

echo ""
echo "Bootstrapping ${PROJECT} in account ${ACCOUNT_ID} (${AWS_REGION})"
echo "  as ${PRINCIPAL_ARN} (profile: ${AWS_PROFILE})"
echo "  CI roles will trust ${GITHUB_OIDC_SUBJECT_PREFIX}"

# 1. Create the state bucket (idempotent, shared across envs)
echo ""
echo "Creating S3 bucket: ${BUCKET}"
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "  bucket already exists, skipping"
else
  if [ "${AWS_REGION}" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "${BUCKET}" \
      --bucket-namespace account-regional \
      --region "${AWS_REGION}"
  else
    aws s3api create-bucket \
      --bucket "${BUCKET}" \
      --bucket-namespace account-regional \
      --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  fi
fi

# 2. Versioning
echo ""
echo "Enabling versioning"
aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

# 3. Block public access
echo ""
echo "Blocking public access"
aws s3api put-public-access-block \
  --bucket "${BUCKET}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 4. Default encryption
echo ""
echo "Enabling encryption"
aws s3api put-bucket-encryption \
  --bucket "${BUCKET}" \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# 5. Write backend files for all environments
echo ""
echo "Writing backend files"
bash "$(dirname "$0")/bootstrap-backend.sh" "${ACCOUNT_ID}"

# 6. Write iam.tfvars from caller identity and the GitHub repository (idempotent)
IAM_TFVARS="./infra/iam/iam.tfvars"
echo ""
if [ ! -f "${IAM_TFVARS}" ]; then
  echo "Writing ${IAM_TFVARS} (principal: ${PRINCIPAL_ARN})"
  cat > "${IAM_TFVARS}" <<EOT
local_principal_arn        = "${PRINCIPAL_ARN}"
state_bucket_name          = "${BUCKET}"
github_oidc_subject_prefix = "${GITHUB_OIDC_SUBJECT_PREFIX}"
EOT
elif ! grep -q '^github_oidc_subject_prefix' "${IAM_TFVARS}"; then
  echo "Adding github_oidc_subject_prefix to ${IAM_TFVARS}"
  echo "github_oidc_subject_prefix = \"${GITHUB_OIDC_SUBJECT_PREFIX}\"" >> "${IAM_TFVARS}"
else
  echo "  ${IAM_TFVARS} exists, skipping"
fi

# 7. Write .envrc for direnv (idempotent)
ENVRC="./.envrc"
echo ""
if [ -f "${ENVRC}" ]; then
  echo "  ${ENVRC} exists, skipping"
else
  echo "Writing ${ENVRC}"
  printf 'export AWS_PROFILE=%s-local\n' "${PROJECT}" > "${ENVRC}"
fi

echo ""
echo "Bootstrap complete."
echo ""
echo "Next (CONTRIBUTING.md, steps 3.3 to 3.6):"
echo "  make provision             # One-time: create IAM roles and init the local stack"
echo "  make iam-output            # Role ARNs for the banking-agent-local profile and GitHub"
echo "  direnv allow               # Only once the banking-agent-local profile exists"
echo "  make doctor                # Check every AWS profile the project uses"
echo "  make plan && make apply    # Apply local infra"
echo ""
echo "Prototype is initialized and applied by CI on merge to main."
