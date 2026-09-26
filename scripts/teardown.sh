#!/usr/bin/env bash
set -euo pipefail

# Deletes the state bucket, undoing bootstrap.sh. Run it last, once every stack
# is destroyed, or whatever Terraform still tracks is orphaned:
#
#   make destroy ENV=local
#   AWS_PROFILE=default make init ENV=prototype
#   AWS_PROFILE=default make destroy ENV=prototype I_KNOW=1
#   make iam-destroy I_KNOW=1
#
# Uses the admin profile; the deploy roles can't delete the bucket.

# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/common.sh"

export AWS_PROFILE="${ADMIN_PROFILE}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
assert_not_organizer "${ACCOUNT_ID}"
BUCKET=$(state_bucket_name "${ACCOUNT_ID}")

echo ""
echo "This permanently deletes the state bucket for ${PROJECT} (and ALL"
echo "Terraform state it holds):"
echo ""
echo "    ${BUCKET}"
echo ""
echo "Run this ONLY after every Terraform stack is destroyed (destroy for each"
echo "env, then iam-destroy). Deleting the bucket orphans anything Terraform"
echo "still tracks."
echo ""

read -r -p "Type the bucket name to confirm: " CONFIRM
if [ "${CONFIRM}" != "${BUCKET}" ]; then
  echo "Confirmation did not match. Aborting; nothing was deleted."
  exit 1
fi

echo ""
if ! aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "Bucket ${BUCKET} not found, skipping"
  echo ""
  echo "Teardown complete."
  exit 0
fi

# Versioned bucket: remove every version and delete marker, a page at a time.
purge_versions() {
  local query="$1"
  while :; do
    local lines
    lines=$(aws s3api list-object-versions --bucket "${BUCKET}" --max-keys 1000 \
      --region "${AWS_REGION}" --query "${query}" --output text 2>/dev/null || true)
    [ -z "${lines}" ] && break
    printf '%s\n' "${lines}" | while IFS=$'\t' read -r KEY VERSION; do
      [ -z "${KEY}" ] && continue
      aws s3api delete-object --bucket "${BUCKET}" --region "${AWS_REGION}" \
        --key "${KEY}" --version-id "${VERSION}" >/dev/null
    done
  done
}

echo "Emptying ${BUCKET} (all object versions and delete markers)"
purge_versions 'Versions[].[Key,VersionId]'
purge_versions 'DeleteMarkers[].[Key,VersionId]'

echo "Deleting bucket ${BUCKET}"
aws s3api delete-bucket --bucket "${BUCKET}" --region "${AWS_REGION}"

echo ""
echo "Teardown complete."
