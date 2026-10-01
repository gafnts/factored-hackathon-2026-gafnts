# The evaluation harness's role, and the bucket that keeps each case's results (ADR-0004, Operations, and its amendment
# of 2026-10-01; ADR-0005). The harness reaches the Runtime and the Gateway only with its test users' tokens, so no
# statement here invokes either.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
  user_pool  = "arn:aws:cognito-idp:${local.region}:${local.account_id}:userpool/${var.user_pool_id}"
}

# Access logs need a second bucket.
#trivy:ignore:AVD-AWS-0089
resource "aws_s3_bucket" "evaluation" {
  bucket           = "${var.prefix}-evaluation-${local.account_id}-${local.region}-an"
  bucket_namespace = "account-regional"
  force_destroy    = true
}

resource "aws_s3_bucket_versioning" "evaluation" {
  bucket = aws_s3_bucket.evaluation.id
  versioning_configuration {
    status = "Enabled"
  }
}

# The cases' customers are synthetic or ours, and a KMS key would need a grant in every reader's role.
#trivy:ignore:AVD-AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "evaluation" {
  bucket = aws_s3_bucket.evaluation.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evaluation" {
  bucket                  = aws_s3_bucket.evaluation.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versions an expiry leaves behind go a day later, so nothing outlives the retention by more than that.
resource "aws_s3_bucket_lifecycle_configuration" "evaluation" {
  bucket = aws_s3_bucket.evaluation.id

  rule {
    id     = "retention"
    status = "Enabled"
    filter {}
    expiration {
      days = var.retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = 1
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "delete-markers"
    status = "Enabled"
    filter {}
    expiration {
      expired_object_delete_marker = true
    }
  }

  depends_on = [aws_s3_bucket_versioning.evaluation]
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.evaluation.arn, "${aws_s3_bucket.evaluation.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # A run's evidence is written once, so what the grader reads is what the run recorded.
  statement {
    sid       = "DenyUnconditionalWrites"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.evaluation.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Null"
      variable = "s3:if-none-match"
      values   = ["true"]
    }
    condition {
      test     = "Bool"
      variable = "s3:ObjectCreationOperation"
      values   = ["true"]
    }
  }
}

resource "aws_s3_bucket_policy" "evaluation" {
  bucket = aws_s3_bucket.evaluation.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [aws_s3_bucket_public_access_block.evaluation]
}

# The account's administrators and this environment's deploy role assume it; the other environment's deploy role is
# refused by its tag guard, and no service role of the stack may assume roles.
data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }
}

resource "aws_iam_role" "harness" {
  name                 = "${var.prefix}-evaluation-harness"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  permissions_boundary = var.permissions_boundary_arn
}

data "aws_iam_policy_document" "harness" {
  # IAM scopes these to the pool, not to a group, so the harness's code deletes only its own users in the evaluation
  # group. A test user needs a permanent password to sign in.
  statement {
    sid = "TestUsers"
    actions = [
      "cognito-idp:AdminAddUserToGroup",
      "cognito-idp:AdminCreateUser",
      "cognito-idp:AdminDeleteUser",
      "cognito-idp:AdminGetUser",
      "cognito-idp:AdminInitiateAuth",
      "cognito-idp:AdminListGroupsForUser",
      "cognito-idp:AdminSetUserPassword",
      "cognito-idp:AdminUserGlobalSignOut",
      "cognito-idp:ListUsersInGroup",
    ]
    resources = [local.user_pool]
  }

  # Fixtures and fault plans, which tools honor only in the sign-in they were written for; the overlay's TTL clears
  # them.
  statement {
    sid       = "Overlay"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"]
    resources = [var.overlay_table.arn]
  }

  statement {
    sid       = "ExecutionRecords"
    actions   = ["dynamodb:GetItem", "dynamodb:Query"]
    resources = [var.execution_records_table.arn]
  }

  statement {
    sid       = "ConfirmationsAndCases"
    actions   = ["dynamodb:GetItem"]
    resources = [var.confirmations_table.arn, var.cases_table.arn]
  }

  statement {
    sid       = "FileHandoff"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.file_handoff_function.arn]
  }

  statement {
    sid       = "ListResults"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.evaluation.arn]
  }

  statement {
    sid       = "ReadWriteResults"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.evaluation.arn}/*"]
  }
}

resource "aws_iam_role_policy" "harness" {
  name   = "evaluation-harness"
  role   = aws_iam_role.harness.id
  policy = data.aws_iam_policy_document.harness.json
}
