#!/usr/bin/env bash
set -euo pipefail

# Out-of-band teardown: the mirror image of bootstrap.sh.
#
# Deletes the shared, versioned state bucket, which lives OUTSIDE Terraform's
# lifecycle. This is the LAST step of a full teardown. Run it only after every
# Terraform stack is gone:
#
#   make destroy ENV=local
#   AWS_PROFILE=default make init ENV=demo
#   AWS_PROFILE=default make destroy ENV=demo I_KNOW=1
#   AWS_PROFILE=default make iam-destroy I_KNOW=1
#
# Deleting the state bucket orphans anything Terraform still tracks (the
# resources keep existing in AWS but Terraform can no longer see them), which is
# why the stacks come first.
#
# Run with ADMIN/DEFAULT credentials, not the scoped deploy role: the deploy
# roles can only touch their own state prefix and cannot delete the bucket. The
# repo's .envrc sets AWS_PROFILE=banking-agent-local, so override it, e.g.
#   AWS_PROFILE=default bash teardown.sh
#
# The state bucket deletion is irreversible.

AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="banking-agent"

SUFFIX=$(echo -n "${PROJECT}" | openssl dgst -sha256 | awk '{print $2}' | cut -c1-8)
BUCKET="${PROJECT}-tfstate-${SUFFIX}"

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

# Versioned bucket: an object isn't gone until every version and delete marker
# is removed. Loop in case there are more than one page (1000) of them.
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
