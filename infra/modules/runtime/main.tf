# The AgentCore Runtime, its code, the model key, and the checkpoints (ADR-0004).

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  region       = data.aws_region.current.region
  agentcore    = "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}"
  runtime_name = "${replace(var.prefix, "-", "_")}_agent"
  # The Runtime's ID is its name and a suffix, so its workload identity and log group match this before it exists.
  runtime_ids = "${local.runtime_name}-*"
  workload_identities = [
    "${local.agentcore}:workload-identity-directory/default",
    "${local.agentcore}:workload-identity-directory/default/workload-identity/${local.runtime_ids}",
  ]
}

# Access logs need a second bucket, and every object here is rebuilt from the repository.
#trivy:ignore:AVD-AWS-0089
resource "aws_s3_bucket" "artifacts" {
  bucket           = "${var.prefix}-artifacts-${local.account_id}-${local.region}-an"
  bucket_namespace = "account-regional"
  force_destroy    = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# The zips are built from public code.
#trivy:ignore:AVD-AWS-0132
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "artifacts" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
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
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = data.aws_iam_policy_document.artifacts.json

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}

resource "aws_s3_object" "runtime" {
  bucket      = aws_s3_bucket.artifacts.id
  key         = "runtime/${filesha256(var.runtime_zip)}.zip"
  source      = var.runtime_zip
  source_hash = filemd5(var.runtime_zip)

  depends_on = [aws_s3_bucket_server_side_encryption_configuration.artifacts]
}

# Created by infra/iam and filled by make model-key before the first apply, so the key never reaches state, a plan, or
# CI (CONTRIBUTING.md, step 3.6).
data "aws_secretsmanager_secret" "model_key" {
  name = "${var.prefix}-anthropic-api-key"
}

resource "aws_bedrockagentcore_api_key_credential_provider" "model" {
  name                  = "${var.prefix}-anthropic"
  api_key_secret_source = "EXTERNAL"

  api_key_secret_config {
    secret_id = data.aws_secretsmanager_secret.model_key.arn
    json_key  = "api_key"
  }
}

# Checkpoints expire after 7 days (ADR-0004, Stores) and are never restored.
#trivy:ignore:AVD-AWS-0024
#trivy:ignore:AVD-AWS-0025
resource "aws_dynamodb_table" "checkpoints" {
  name         = "${var.prefix}-checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

data "aws_iam_policy_document" "runtime_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.agentcore}:*"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name                 = "${var.prefix}-runtime"
  assume_role_policy   = data.aws_iam_policy_document.runtime_trust.json
  permissions_boundary = var.permissions_boundary_arn
}

# No logs:CreateLogGroup: a group the Runtime creates has no retention and survives a destroy (spike S4).
data "aws_iam_policy_document" "runtime" {
  statement {
    actions   = ["logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/${local.runtime_ids}"]
  }
  statement {
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }
  statement {
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
  statement {
    actions   = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT"]
    resources = local.workload_identities
  }
  # A customer's JWT is always present, so a token for a bare user ID is never needed (ADR-0004, Operations).
  statement {
    effect    = "Deny"
    actions   = ["bedrock-agentcore:GetWorkloadAccessTokenForUserId", "bedrock-agentcore:InvokeAgentRuntimeForUser"]
    resources = ["*"]
  }
  statement {
    actions = ["bedrock-agentcore:GetResourceApiKey"]
    resources = concat(local.workload_identities, [
      "${local.agentcore}:token-vault/default",
      aws_bedrockagentcore_api_key_credential_provider.model.credential_provider_arn,
    ])
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [data.aws_secretsmanager_secret.model_key.arn]
  }
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [aws_dynamodb_table.checkpoints.arn]
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "runtime"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime.json
}

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = local.runtime_name
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact {
    code_configuration {
      entry_point = ["main.py"]
      runtime     = "PYTHON_3_13"
      code {
        s3 {
          bucket = aws_s3_bucket.artifacts.id
          prefix = aws_s3_object.runtime.key
        }
      }
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "AGUI"
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = var.discovery_url
      allowed_clients = var.allowed_clients

      custom_claim {
        inbound_token_claim_name       = "cognito:groups"
        inbound_token_claim_value_type = "STRING_ARRAY"
        authorizing_claim_match_value {
          claim_match_operator = "CONTAINS"
          claim_match_value {
            match_value_string = var.required_group
          }
        }
      }
    }
  }

  request_header_configuration {
    request_header_allowlist = ["Authorization"]
  }

  lifecycle_configuration = [{
    idle_runtime_session_timeout = 900
    max_lifetime                 = 28800
  }]

  environment_variables = {
    GATEWAY_URL        = var.gateway_url
    CHECKPOINTS_TABLE  = aws_dynamodb_table.checkpoints.name
    MODEL_KEY_PROVIDER = aws_bedrockagentcore_api_key_credential_provider.model.name
    # The SDK then fails without a workload token instead of making a local workload identity (spike S4).
    DOCKER_CONTAINER = "1"
  }

  depends_on = [aws_iam_role_policy.runtime]
}

# Logs hold masked text only, and a KMS key would need a grant for every writer.
#trivy:ignore:AVD-AWS-0017
resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.this.agent_runtime_id}-DEFAULT"
  retention_in_days = var.log_retention_days
}
