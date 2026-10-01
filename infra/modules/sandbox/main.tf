# The sign-in's sandbox and the confirmations (ADR-0004, Stores): what the customer's actions write, never the tools'
# data (POL-33), and the evaluation's fixtures and fault plans. Both expire after 24 hours; nothing in them is restored.

locals {
  contract = jsondecode(file(var.contract))
  attributes = sort(distinct(flatten([
    for item in ["card_status", "fixture_card", "fixture_transaction", "fault_plan"] :
    keys(local.contract["$defs"][item].properties)
  ])))
  # Only file_handoff reads a fixture's is_fraud (POL-40).
  readable = [for name in local.attributes : name if name != "is_fraud"]
  # A fault plan's count is all the tools may change.
  counted = ["sign_in", "item", "customer_id", "failures"]
}

#trivy:ignore:AVD-AWS-0024
#trivy:ignore:AVD-AWS-0025
resource "aws_dynamodb_table" "overlay" {
  name         = "${var.prefix}-sandbox-overlay"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "sign_in"
  range_key    = "item"

  lifecycle {
    precondition {
      condition     = contains(local.attributes, "is_fraud") && length(setsubtract(local.counted, local.attributes)) == 0
      error_message = "The overlay's contract has no is_fraud for the reads' allowlist to leave out, or lacks a fault plan's attributes."
    }
  }

  attribute {
    name = "sign_in"
    type = "S"
  }

  attribute {
    name = "item"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

#trivy:ignore:AVD-AWS-0024
#trivy:ignore:AVD-AWS-0025
resource "aws_dynamodb_table" "confirmations" {
  name         = "${var.prefix}-confirmations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "confirmation_id"

  attribute {
    name = "confirmation_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}
