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

echo ""
echo "Bootstrapping ${PROJECT} in account ${ACCOUNT_ID} (${AWS_REGION})"
echo "  as ${PRINCIPAL_ARN} (profile: ${AWS_PROFILE})"

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

# 6. Write iam.tfvars from caller identity (idempotent)
IAM_TFVARS="./infra/iam/iam.tfvars"
echo ""
if [ -f "${IAM_TFVARS}" ]; then
  echo "  ${IAM_TFVARS} exists, skipping"
else
  echo "Writing ${IAM_TFVARS} (principal: ${PRINCIPAL_ARN})"
  cat > "${IAM_TFVARS}" <<EOT
local_principal_arn = "${PRINCIPAL_ARN}"
state_bucket_name   = "${BUCKET}"
EOT
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
echo "Demo is initialized and applied by CI on merge to main."
