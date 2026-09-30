#!/usr/bin/env bash
set -euo pipefail

# Uploads web/dist to the site's bucket and invalidates its distribution (ADR-0007). config.json isn't the build's:
# Terraform writes it at every apply, so no step here touches it.

OUTPUTS="$1"
DIST="web/dist"

SITE=$(uv run python -c '
import json, sys
site = json.load(open(sys.argv[1])).get("site")
if not site:
    sys.exit(f"{sys.argv[1]} holds no site: run make plan and make apply first.")
print(site["value"]["bucket"], site["value"]["distribution_id"])
' "${OUTPUTS}")
read -r BUCKET DISTRIBUTION <<< "${SITE}"

# Vite names assets by their content, so they never change, and they go up before the index.html that names them.
aws s3 sync "${DIST}/assets" "s3://${BUCKET}/assets" \
  --cache-control "public, max-age=31536000, immutable" --only-show-errors
aws s3 sync "${DIST}" "s3://${BUCKET}" \
  --exclude "assets/*" --exclude "config.json" --cache-control "no-cache" --only-show-errors
aws s3 sync "${DIST}" "s3://${BUCKET}" --delete --exclude "config.json" --only-show-errors

echo "Invalidating the distribution's cache: $(aws cloudfront create-invalidation \
  --distribution-id "${DISTRIBUTION}" --paths "/*" --query Invalidation.Id --output text)"
