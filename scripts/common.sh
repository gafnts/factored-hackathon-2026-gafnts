# shellcheck shell=bash disable=SC2034
# Shared settings for the scripts in this directory. Sourced, not run.

PROJECT="banking-agent"
AWS_REGION="${AWS_REGION:-us-east-1}"
ADMIN_PROFILE="${AWS_ADMIN_PROFILE:-default}"

# Organizers' read-only dataset account: never bootstrap or deploy with it.
ORGANIZER_ACCOUNT_ID="157725502942"

# Account regional namespace, so the name is unique to each account.
state_bucket_name() {
  local account_id="$1"
  echo "${PROJECT}-tfstate-${account_id}-${AWS_REGION}-an"
}

assert_not_organizer() {
  local account_id="$1"
  if [ "${account_id}" = "${ORGANIZER_ACCOUNT_ID}" ]; then
    echo "Refusing to continue: these credentials belong to the organizers' dataset" >&2
    echo "account (${ORGANIZER_ACCOUNT_ID}), not the account this project deploys to." >&2
    echo "Point AWS_ADMIN_PROFILE (default: 'default') at your own account." >&2
    exit 1
  fi
}
