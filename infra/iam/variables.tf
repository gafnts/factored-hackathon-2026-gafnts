variable "project_name" {
  description = "Prefix for the deploy roles and for the service roles they are allowed to manage"
  type        = string
  default     = "banking-agent"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "github_repo" {
  description = "GitHub repo in owner/name form"
  type        = string
  default     = "gafnts/factored-hackathon-2026-gafnts"
}

variable "local_principal_arn" {
  description = "IAM user/role ARN allowed to assume the local-deploy role"
  type        = string
}

variable "state_bucket_name" {
  description = "Name of the S3 bucket holding Terraform state"
  type        = string
}
