# The Gateway, its Cedar policies, and the read tools' Lambda (ADR-0004).

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
  # Policy engine and policy names allow only letters, digits, and underscores.
  policy_prefix = replace(var.prefix, "-", "_")
  reads_name    = "${var.prefix}-reads"
  target        = "reads"
  # Generated from the contract by make build, and committed so a PR shows what the Gateway declares.
  tools = jsondecode(file("${path.module}/tools.json"))
}

resource "aws_bedrockagentcore_policy_engine" "this" {
  name = "${local.policy_prefix}_engine"
}

data "aws_iam_policy_document" "gateway_trust" {
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
      values   = ["arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name                 = "${var.prefix}-gateway"
  assume_role_policy   = data.aws_iam_policy_document.gateway_trust.json
  permissions_boundary = var.permissions_boundary_arn
}

# Without the policy engine's actions, Cedar denies every call (spike S3).
data "aws_iam_policy_document" "gateway" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.reads.arn]
  }
  statement {
    actions   = ["bedrock-agentcore:GetPolicyEngine"]
    resources = [aws_bedrockagentcore_policy_engine.this.policy_engine_arn]
  }
  statement {
    actions = [
      "bedrock-agentcore:AuthorizeAction",
      "bedrock-agentcore:PartiallyAuthorizeActions",
    ]
    resources = [
      aws_bedrockagentcore_policy_engine.this.policy_engine_arn,
      "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:gateway/*",
    ]
  }
}

resource "aws_iam_role_policy" "gateway" {
  name   = "gateway"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.gateway.json
}

# exception_level stays unset: DEBUG would hand the caller the reason for a denial (decision 14).
resource "aws_bedrockagentcore_gateway" "this" {
  name            = var.prefix
  role_arn        = aws_iam_role.gateway.arn
  protocol_type   = "MCP"
  authorizer_type = "CUSTOM_JWT"

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = var.discovery_url
      allowed_clients = var.allowed_clients
    }
  }

  policy_engine_configuration {
    arn  = aws_bedrockagentcore_policy_engine.this.policy_engine_arn
    mode = "ENFORCE"
  }

  depends_on = [aws_iam_role_policy.gateway]
}

# Logs hold masked text only, and a KMS key would need a grant for every writer.
#trivy:ignore:AVD-AWS-0017
resource "aws_cloudwatch_log_group" "reads" {
  name              = "/aws/lambda/${local.reads_name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "reads" {
  name                 = local.reads_name
  assume_role_policy   = data.aws_iam_policy_document.lambda_trust.json
  permissions_boundary = var.permissions_boundary_arn
}

data "aws_iam_policy_document" "reads" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.reads.arn}:*"]
  }
}

resource "aws_iam_role_policy" "reads" {
  name   = "logs"
  role   = aws_iam_role.reads.id
  policy = data.aws_iam_policy_document.reads.json
}

# The execution record is the prototype's trace (ADR-0004, Operations).
#trivy:ignore:AVD-AWS-0066
resource "aws_lambda_function" "reads" {
  function_name    = local.reads_name
  role             = aws_iam_role.reads.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "banking_agent.tools.reads.handler"
  filename         = var.reads_zip
  source_code_hash = filebase64sha256(var.reads_zip)
  memory_size      = 256
  timeout          = 10

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.reads.name
  }

  depends_on = [aws_iam_role_policy.reads]
}

resource "aws_bedrockagentcore_gateway_target" "reads" {
  name               = local.target
  gateway_identifier = aws_bedrockagentcore_gateway.this.gateway_id

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.reads.arn
        tool_schema {
          dynamic "inline_payload" {
            for_each = local.tools
            content {
              name        = inline_payload.value.name
              description = inline_payload.value.description
              input_schema {
                type = inline_payload.value.inputSchema.type
                dynamic "property" {
                  for_each = inline_payload.value.inputSchema.properties
                  content {
                    name        = property.key
                    type        = property.value.type
                    description = try(property.value.description, null)
                    required    = contains(inline_payload.value.inputSchema.required, property.key) ? true : null
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition = alltrue(flatten([
        for tool in local.tools : [
          for property in values(tool.inputSchema.properties) : contains(["string", "integer", "number", "boolean"], property.type)
        ]
      ]))
      error_message = "A tool input has an object or array property, which this target doesn't declare yet."
    }
  }
}

# A policy names the Gateway and is validated against its targets, so it follows the target (spike S3).
resource "aws_bedrockagentcore_policy" "own_customer" {
  for_each = toset([for tool in local.tools : tool.name])

  name             = "${local.policy_prefix}_${each.key}"
  policy_engine_id = aws_bedrockagentcore_policy_engine.this.policy_engine_id

  definition {
    cedar {
      statement = <<-EOT
        permit (
          principal is AgentCore::OAuthUser,
          action == AgentCore::Action::"${local.target}___${each.key}",
          resource == AgentCore::Gateway::"${aws_bedrockagentcore_gateway.this.gateway_arn}"
        )
        when {
          principal.hasTag("customer_id") &&
          principal.getTag("customer_id") == context.input.customer_id
        };
      EOT
    }
  }

  depends_on = [aws_bedrockagentcore_gateway_target.reads]
}
