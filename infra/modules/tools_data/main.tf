# The tools' data, created from a gold export (ADR-0006, decision 1): a new table per export, written only by its import
# (POL-33), and read one customer's partition at a time (ADR-0004).

data "aws_default_tags" "current" {}

locals {
  prefix   = "gold/${var.export.snapshot}/${var.export.pipeline_version}/"
  manifest = jsondecode(data.aws_s3_object.manifest.body)
  contract = jsondecode(file(var.contract))
  kinds    = ["metadata_item", "customer_item", "card_item", "transaction_item"]
  attributes = sort(distinct(flatten([
    for kind in local.kinds : keys(local.contract["$defs"][kind].properties)
  ])))
  # The read tools may name every attribute but is_fraud (ADR-0004's amendment of 2026-09-29).
  readable = [for name in local.attributes : name if name != "is_fraud"]
  by_card = sort([
    for name in keys(local.contract["$defs"].transaction_item.properties) : name
    if !contains(["pk", "sk", "card_key", "listed_at", "is_fraud"], name)
  ])
}

# The export writes its manifest last, so a plan fails on an export that isn't complete.
data "aws_s3_object" "manifest" {
  bucket = var.data_bucket
  key    = "${local.prefix}manifest.json"
}

# Recreated from its export, never restored, and the data is synthetic.
#trivy:ignore:AVD-AWS-0024
#trivy:ignore:AVD-AWS-0025
resource "aws_dynamodb_table" "this" {
  name         = "${var.prefix}-tools-data-${var.export.snapshot}-${var.export.pipeline_version}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "card_key"
    type = "S"
  }

  attribute {
    name = "listed_at"
    type = "S"
  }

  global_secondary_index {
    name               = "by_card"
    projection_type    = "INCLUDE"
    non_key_attributes = local.by_card

    key_schema {
      attribute_name = "card_key"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "listed_at"
      key_type       = "RANGE"
    }
  }

  import_table {
    input_format           = "DYNAMODB_JSON"
    input_compression_type = "GZIP"

    s3_bucket_source {
      bucket     = var.data_bucket
      key_prefix = "${local.prefix}items/"
    }
  }

  lifecycle {
    create_before_destroy = true

    precondition {
      condition     = local.manifest.snapshot == var.export.snapshot && local.manifest.pipeline_version == var.export.pipeline_version
      error_message = "The export's manifest names another snapshot or pipeline version."
    }

    precondition {
      condition     = contains(local.attributes, "is_fraud")
      error_message = "The contract has no is_fraud, so the read tools' allowlist can't leave it out."
    }
  }
}

# ImportTable takes no tags, and the provider adds none on create (ADR-0006's amendment of 2026-09-29).
resource "aws_dynamodb_tag" "this" {
  for_each = data.aws_default_tags.current.tags

  resource_arn = aws_dynamodb_table.this.arn
  key          = each.key
  value        = each.value
}
