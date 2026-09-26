variable "project_name" {
  description = "Prefix for the deploy roles and for the service roles they are allowed to manage"
  type        = string
  default     = "banking-agent"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# No default: a copy of the project must trust its own repository, never this
# one. make bootstrap reads the value from GitHub and writes it to iam.tfvars.
variable "github_oidc_subject_prefix" {
  description = "Start of the sub claim in the GitHub OIDC tokens of the repository CI runs in. Repositories created after 2026-07-15 use the immutable form repo:<owner>@<owner-id>/<repo>@<repo-id>; print it with: gh api repos/<owner>/<repo>/actions/oidc/customization/sub --jq .sub_claim_prefix"
  type        = string

  validation {
    condition     = startswith(var.github_oidc_subject_prefix, "repo:")
    error_message = "github_oidc_subject_prefix must start with \"repo:\"; re-run make bootstrap, or copy it from the gh api command in the description."
  }
}

variable "local_principal_arn" {
  description = "IAM user/role ARN allowed to assume the local-deploy role"
  type        = string
}

variable "state_bucket_name" {
  description = "Name of the S3 bucket holding Terraform state"
  type        = string
}
