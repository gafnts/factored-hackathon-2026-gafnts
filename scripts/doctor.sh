#!/usr/bin/env bash
set -uo pipefail

# No -e: keep checking after a failure.

# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/common.sh"

DATASET_PROFILE="${DATASET_SOURCE_PROFILE:-factored-hackathon}"
DATASET_BUCKET="factored-datathon-2026-s3-${ORGANIZER_ACCOUNT_ID}-us-east-2-an"
DATASET_REGION="us-east-2"
LOCAL_PROFILE="${PROJECT}-local"
BACKEND_FILES=(
  infra/envs/local.backend.tfbackend
  infra/envs/prototype.backend.tfbackend
  infra/iam/backend.tfbackend
  infra/dataset/backend.tfbackend
)

# The profile .envrc sets may not exist yet, so every call passes --profile.
ACTIVE_PROFILE="${AWS_PROFILE:-}"
unset AWS_PROFILE

FAILED=0
OWN_ACCOUNT_ID=""
ok() { echo "  ok    $*"; }
todo() { echo "  todo  $*"; }
fail() {
  echo "  FAIL  $*"
  FAILED=1
}

has_profile() {
  aws configure list-profiles | grep -qx "$1"
}

# "<account-id> <arn>", or the CLI's error.
identity() {
  aws sts get-caller-identity --profile "$1" --query '[Account,Arn]' --output text 2>&1
}

echo ""
echo "Admin profile: ${ADMIN_PROFILE} (bootstrap, IAM roles, teardown)"
if ! has_profile "${ADMIN_PROFILE}"; then
  fail "profile not found; run 'aws login' or set AWS_ADMIN_PROFILE"
elif ! out=$(identity "${ADMIN_PROFILE}"); then
  fail "cannot authenticate: ${out}"
else
  read -r ACCOUNT_ID ARN <<< "${out}"
  if [ "${ACCOUNT_ID}" = "${ORGANIZER_ACCOUNT_ID}" ]; then
    fail "${ARN} is the organizers' dataset reader, not your account"
  else
    ok "${ARN}"
    OWN_ACCOUNT_ID="${ACCOUNT_ID}"
    BUCKET=$(state_bucket_name "${ACCOUNT_ID}")
    if aws s3api head-bucket --bucket "${BUCKET}" --profile "${ADMIN_PROFILE}" >/dev/null 2>&1; then
      ok "state bucket ${BUCKET} exists"
    else
      todo "state bucket ${BUCKET} not found; run 'make bootstrap'"
    fi
    for file in "${BACKEND_FILES[@]}"; do
      if grep -q "\"${BUCKET}\"" "${file}"; then
        ok "${file} points at it"
      else
        fail "${file} points at another bucket; run 'make backend'"
      fi
    done
  fi
fi

# Only step 3 needs GitHub, so a missing CLI or sign-in is a todo.
echo ""
ORIGIN_REPO=$(origin_github_repo)
echo "GitHub repository: ${ORIGIN_REPO:-<origin is not on GitHub>} (CI runs here; the CI roles trust it)"
PREFIX=""
if [ -z "${ORIGIN_REPO}" ]; then
  fail "origin is not a GitHub repository; point it at your fork"
elif ! command -v gh >/dev/null 2>&1; then
  todo "GitHub CLI not installed; see CONTRIBUTING.md, step 1"
elif ! gh auth status >/dev/null 2>&1; then
  todo "GitHub CLI not signed in; run 'gh auth login'"
elif ! PREFIX=$(oidc_subject_prefix "${ORIGIN_REPO}" 2>&1); then
  fail "cannot read its OIDC subject: ${PREFIX}"
  PREFIX=""
else
  ok "OIDC subject ${PREFIX}"
fi
IAM_TFVARS=infra/iam/iam.tfvars
if [ -f "${IAM_TFVARS}" ]; then
  TRUSTED=$(sed -n 's/^github_oidc_subject_prefix *= *"\(.*\)"$/\1/p' "${IAM_TFVARS}")
  if [ -z "${TRUSTED}" ]; then
    todo "${IAM_TFVARS} doesn't set github_oidc_subject_prefix; run 'make bootstrap'"
  elif [ -z "${PREFIX}" ]; then
    ok "${IAM_TFVARS} trusts ${TRUSTED} (not compared with GitHub)"
  elif [ "${TRUSTED}" = "${PREFIX}" ]; then
    ok "${IAM_TFVARS} trusts it"
  else
    fail "${IAM_TFVARS} trusts ${TRUSTED}; fix it, then run 'make iam-apply'"
  fi
else
  todo "${IAM_TFVARS} not found; run 'make bootstrap'"
fi

echo ""
echo "Dataset profile: ${DATASET_PROFILE} (organizers' read-only keys)"
if ! has_profile "${DATASET_PROFILE}"; then
  todo "profile not found; see CONTRIBUTING.md, step 2 (Connect to the dataset)"
elif ! out=$(identity "${DATASET_PROFILE}"); then
  fail "cannot authenticate: ${out}"
else
  read -r ACCOUNT_ID ARN <<< "${out}"
  if [ "${ACCOUNT_ID}" != "${ORGANIZER_ACCOUNT_ID}" ]; then
    fail "${ARN} is not in the organizers' account (${ORGANIZER_ACCOUNT_ID})"
  elif aws s3api list-objects-v2 --bucket "${DATASET_BUCKET}" --prefix data/ --max-keys 1 \
    --profile "${DATASET_PROFILE}" --region "${DATASET_REGION}" >/dev/null 2>&1; then
    ok "${ARN} can read s3://${DATASET_BUCKET}/data/"
  else
    fail "${ARN} cannot list s3://${DATASET_BUCKET}/data/"
  fi
fi

echo ""
echo "Local deploy profile: ${LOCAL_PROFILE} (make plan/apply)"
if ! has_profile "${LOCAL_PROFILE}"; then
  todo "profile not found; see CONTRIBUTING.md, steps 3.3 and 3.4"
elif ! out=$(identity "${LOCAL_PROFILE}"); then
  fail "cannot assume the role: ${out}"
else
  read -r _ ARN <<< "${out}"
  if [[ "${ARN}" == *":assumed-role/${LOCAL_PROFILE}-deploy/"* ]]; then
    ok "${ARN}"
  else
    fail "resolves to ${ARN}, expected the ${LOCAL_PROFILE}-deploy role"
  fi
fi

LOCK=dataset.lock
echo ""
echo "Dataset snapshot: ${LOCK} (make data, make snapshot)"
if [ ! -f "${LOCK}" ]; then
  todo "${LOCK} not found; run 'make data'"
else
  SNAPSHOT=$(sed -n 's/^# snapshot: //p' "${LOCK}")
  FILES=$(grep -vc '^#' "${LOCK}")
  ok "${LOCK} pins snapshot ${SNAPSHOT} (${FILES} files)"
  LOCAL_DIR="data/snapshots/${SNAPSHOT}"
  if [ -d "${LOCAL_DIR}" ] && [ "$(find "${LOCAL_DIR}" -type f | wc -l | tr -d ' ')" = "${FILES}" ]; then
    ok "${LOCAL_DIR} holds every file (make data re-verifies them)"
  else
    todo "${LOCAL_DIR} is incomplete; run 'make data'"
  fi
  if [ -z "${OWN_ACCOUNT_ID}" ] || ! has_profile "${LOCAL_PROFILE}"; then
    todo "the data bucket can't be checked until the admin and local deploy profiles work"
  else
    SNAPSHOT_BUCKET=$(data_bucket_name "${OWN_ACCOUNT_ID}")
    if ! aws s3api head-bucket --bucket "${SNAPSHOT_BUCKET}" \
      --profile "${LOCAL_PROFILE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
      todo "data bucket ${SNAPSHOT_BUCKET} not found; run 'make dataset-apply'"
    elif aws s3api head-object --bucket "${SNAPSHOT_BUCKET}" --key "snapshots/${SNAPSHOT}/dataset.lock" \
      --profile "${LOCAL_PROFILE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
      ok "s3://${SNAPSHOT_BUCKET}/snapshots/${SNAPSHOT}/ is complete"
    else
      todo "s3://${SNAPSHOT_BUCKET}/snapshots/${SNAPSHOT}/ is missing or incomplete; run 'make snapshot'"
    fi
  fi
fi

echo ""
echo "AWS_PROFILE in this shell: ${ACTIVE_PROFILE:-<unset>}"
echo ""
if [ "${FAILED}" -ne 0 ]; then
  echo "Some checks failed."
  exit 1
fi
echo "No failures."
