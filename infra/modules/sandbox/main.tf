# The sign-in's sandbox and the confirmations (ADR-0004, Stores): what the customer's actions write, never the tools'
# data (POL-33). Both expire after 24 hours; nothing in them is restored.

#trivy:ignore:AVD-AWS-0024
#trivy:ignore:AVD-AWS-0025
resource "aws_dynamodb_table" "overlay" {
  name         = "${var.prefix}-sandbox-overlay"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "sign_in"
  range_key    = "item"

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
