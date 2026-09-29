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
  # Named as infra/dataset names it; the exports live beside the snapshots.
  data_bucket = "${var.project_name}-data-${data.aws_caller_identity.current.account_id}-${var.aws_region}-an"
}

module "identity" {
  source = "./modules/identity"

  prefix                   = local.prefix
  permissions_boundary_arn = local.permissions_boundary_arn
  log_retention_days       = var.log_retention_days
  pre_token_zip            = "${local.build}/pre_token.zip"
}

module "tools_data" {
  source = "./modules/tools_data"

  prefix      = local.prefix
  export      = var.tools_data_export
  data_bucket = local.data_bucket
  contract    = "${path.root}/../src/banking_agent/contracts/tools-data.schema.json"
}

module "gateway" {
  source = "./modules/gateway"

  prefix                   = local.prefix
  permissions_boundary_arn = local.permissions_boundary_arn
  log_retention_days       = var.log_retention_days
  discovery_url            = module.identity.discovery_url
  allowed_clients          = [module.identity.customer_client_id]
  reads_zip                = "${local.build}/reads.zip"
  tools_data_table         = module.tools_data.table_name
  tools_data_table_arn     = module.tools_data.table_arn
  tools_data_attributes    = module.tools_data.readable_attributes
}

module "runtime" {
  source = "./modules/runtime"

  prefix                   = local.prefix
  permissions_boundary_arn = local.permissions_boundary_arn
  log_retention_days       = var.log_retention_days
  discovery_url            = module.identity.discovery_url
  allowed_clients          = [module.identity.customer_client_id]
  required_group           = "customer"
  gateway_url              = module.gateway.gateway_url
  runtime_zip              = "${local.build}/runtime.zip"
}
