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

# owner/repo of the GitHub repository `origin` points at. The CI roles trust
# that repository, so it should be yours: this one, or your fork of it.
origin_github_repo() {
  local url repo
  url=$(git remote get-url origin 2>/dev/null) || return 1
  repo="${url%.git}"
  repo="${repo#*github.com[:/]}"
  [[ "${repo}" =~ ^[^/]+/[^/]+$ ]] || return 1
  echo "${repo}"
}

# Start of the sub claim in a repository's GitHub OIDC tokens. It carries the
# owner and repository IDs, so it has to come from GitHub, not from the name.
oidc_subject_prefix() {
  local repo="$1"
  gh api "repos/${repo}/actions/oidc/customization/sub" --jq .sub_claim_prefix
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
