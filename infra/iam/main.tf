data "aws_caller_identity" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  oidc_provider = "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  envs          = ["local", "prototype"]

  state_bucket_arn = "arn:aws:s3:::${var.state_bucket_name}"
  state_prefixes   = concat(local.envs, ["iam"])
}

data "aws_iam_policy_document" "trust_local" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.local_principal_arn]
    }
  }
}

# The `prototype` GitHub Environment only allows main, so only main can deploy.
data "aws_iam_policy_document" "trust_prototype" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_oidc_subject_prefix}:environment:prototype"]
    }
  }
}

data "aws_iam_policy_document" "trust_prototype_plan" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_oidc_subject_prefix}:pull_request"]
    }
  }
}

# PowerUserAccess and ReadOnlyAccess reach every bucket; these denies do the scoping.
data "aws_iam_policy_document" "state_isolation" {
  for_each = toset(local.envs)

  statement {
    sid       = "DenyOtherStatePrefixes"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [for prefix in setsubtract(local.state_prefixes, [each.key]) : "${local.state_bucket_arn}/service/${prefix}/*"]
  }

  statement {
    sid         = "DenyStateBucketChanges"
    effect      = "Deny"
    not_actions = ["s3:GetBucket*", "s3:ListBucket"]
    resources   = [local.state_bucket_arn]
  }
}

data "aws_iam_policy_document" "state_access" {
  for_each = toset(local.envs)

  source_policy_documents = [data.aws_iam_policy_document.state_isolation[each.key].json]

  statement {
    sid       = "ListOwnPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["service/${each.key}/*"]
    }
  }

  statement {
    sid    = "ReadWriteOwnState"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObjectAttributes",
    ]
    resources = ["${local.state_bucket_arn}/service/${each.key}/*"]
  }
}

data "aws_iam_policy_document" "deny_other_envs" {
  for_each = toset(local.envs)

  statement {
    sid       = "DenyTouchingOtherEnvs"
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [each.key]
    }
    condition {
      test     = "Null"
      variable = "aws:ResourceTag/Environment"
      values   = ["false"]
    }
  }
}

# Caps the roles a deploy role creates, so it can't escalate through them.
data "aws_iam_policy_document" "boundary" {
  for_each = toset(local.envs)

  source_policy_documents = [data.aws_iam_policy_document.deny_other_envs[each.key].json]

  statement {
    sid         = "AllowAllButIdentityManagement"
    effect      = "Allow"
    not_actions = ["iam:*", "organizations:*", "account:*"]
    resources   = ["*"]
  }
}

resource "aws_iam_policy" "boundary" {
  for_each = toset(local.envs)

  name        = "${var.project_name}-${each.key}-boundary"
  description = "Permissions boundary for the service roles the ${each.key} deploy role creates"
  policy      = data.aws_iam_policy_document.boundary[each.key].json

  tags = {
    Environment = each.key
  }
}

# PowerUserAccess excludes IAM; this adds what the stack's own service roles need.
data "aws_iam_policy_document" "service_roles" {
  for_each = toset(local.envs)

  statement {
    sid    = "ManageOwnServiceRoles"
    effect = "Allow"
    actions = [
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
      "iam:PassRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project_name}-${each.key}-*"]
  }

  statement {
    sid    = "GrantOnlyWithinBoundary"
    effect = "Allow"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreateRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePermissionsBoundary",
      "iam:PutRolePolicy",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project_name}-${each.key}-*"]
    condition {
      test     = "ArnEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.boundary[each.key].arn]
    }
  }

  statement {
    sid       = "KeepBoundaries"
    effect    = "Deny"
    actions   = ["iam:DeleteRolePermissionsBoundary"]
    resources = ["*"]
  }

  statement {
    sid     = "ProtectBootstrapRoles"
    effect  = "Deny"
    actions = ["iam:*"]
    resources = [
      "arn:aws:iam::${local.account_id}:role/${var.project_name}-*-deploy",
      "arn:aws:iam::${local.account_id}:role/${var.project_name}-*-plan",
    ]
  }
}

resource "aws_iam_role" "deploy" {
  for_each = toset(local.envs)

  name = "${var.project_name}-${each.key}-deploy"
  assume_role_policy = {
    "local"     = data.aws_iam_policy_document.trust_local.json
    "prototype" = data.aws_iam_policy_document.trust_prototype.json
  }[each.key]

  tags = {
    Environment = each.key
    Role        = "deploy"
  }
}

resource "aws_iam_role_policy_attachment" "power_user" {
  for_each = toset(local.envs)

  role       = aws_iam_role.deploy[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy" "state_access" {
  for_each = toset(local.envs)

  name   = "tfstate-access"
  role   = aws_iam_role.deploy[each.key].id
  policy = data.aws_iam_policy_document.state_access[each.key].json
}

resource "aws_iam_role_policy" "deny_other_envs" {
  for_each = toset(local.envs)

  name   = "deny-other-envs"
  role   = aws_iam_role.deploy[each.key].id
  policy = data.aws_iam_policy_document.deny_other_envs[each.key].json
}

resource "aws_iam_role_policy" "service_roles" {
  for_each = toset(local.envs)

  name   = "service-roles"
  role   = aws_iam_role.deploy[each.key].id
  policy = data.aws_iam_policy_document.service_roles[each.key].json
}

# Read-only role for the plan on PRs into main.
resource "aws_iam_role" "prototype_plan" {
  name               = "${var.project_name}-prototype-plan"
  assume_role_policy = data.aws_iam_policy_document.trust_prototype_plan.json

  tags = {
    Environment = "prototype"
    Role        = "plan"
  }
}

resource "aws_iam_role_policy_attachment" "prototype_plan_readonly" {
  role       = aws_iam_role.prototype_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Reads come from ReadOnlyAccess, and plans run with -lock=false.
resource "aws_iam_role_policy" "prototype_plan_state_access" {
  name   = "tfstate-access"
  role   = aws_iam_role.prototype_plan.id
  policy = data.aws_iam_policy_document.state_isolation["prototype"].json
}

resource "aws_iam_role_policy" "prototype_plan_deny_other_envs" {
  name   = "deny-other-envs"
  role   = aws_iam_role.prototype_plan.id
  policy = data.aws_iam_policy_document.deny_other_envs["prototype"].json
}
