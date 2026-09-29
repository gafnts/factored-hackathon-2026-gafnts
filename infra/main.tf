provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  prefix = "${var.project_name}-${var.environment}"
  # Required on every IAM role this stack creates (see infra/iam).
  permissions_boundary_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${local.prefix}-boundary"
  # Written by make build, which make plan runs first.
  build = "${path.root}/../build"
}

module "identity" {
  source = "./modules/identity"

  prefix                   = local.prefix
  permissions_boundary_arn = local.permissions_boundary_arn
  log_retention_days       = var.log_retention_days
  pre_token_zip            = "${local.build}/pre_token.zip"
}
