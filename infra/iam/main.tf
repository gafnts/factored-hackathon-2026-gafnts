data "aws_caller_identity" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  oidc_provider = "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  envs          = ["local", "demo"]
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

# Only jobs running in the `demo` GitHub Environment can assume the demo deploy
# role. Restricting that environment's deployment branches to `main` is what
# makes a merge to main the only path to a demo apply.
data "aws_iam_policy_document" "trust_demo" {
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
      values   = ["repo:${var.github_repo}:environment:demo"]
    }
  }
}

data "aws_iam_policy_document" "trust_demo_plan" {
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
      values   = ["repo:${var.github_repo}:pull_request"]
    }
  }
}

data "aws_iam_policy_document" "state_access" {
  for_each = toset(local.envs)

  statement {
    sid       = "ListOwnPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.state_bucket_name}"]
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
    resources = ["arn:aws:s3:::${var.state_bucket_name}/service/${each.key}/*"]
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

# PowerUserAccess excludes IAM, so each deploy role gets just enough to manage
# the execution roles its own stack creates (named <project>-<env>-*). The
# explicit deny keeps a deploy role from editing itself or its siblings, which
# would otherwise be a path to escalating its own permissions.
data "aws_iam_policy_document" "service_roles" {
  for_each = toset(local.envs)

  statement {
    sid    = "ManageOwnServiceRoles"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:PassRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:UntagRole",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project_name}-${each.key}-*"]
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
    "local" = data.aws_iam_policy_document.trust_local.json
    "demo"  = data.aws_iam_policy_document.trust_demo.json
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

# Read-only role for the demo plan posted on PRs into main. PR workflows never
# hold write credentials; only the apply job in the `demo` environment does.
resource "aws_iam_role" "demo_plan" {
  name               = "${var.project_name}-demo-plan"
  assume_role_policy = data.aws_iam_policy_document.trust_demo_plan.json

  tags = {
    Environment = "demo"
    Role        = "plan"
  }
}

resource "aws_iam_role_policy_attachment" "demo_plan_readonly" {
  role       = aws_iam_role.demo_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "demo_plan_state_access" {
  name   = "tfstate-access"
  role   = aws_iam_role.demo_plan.id
  policy = data.aws_iam_policy_document.state_access["demo"].json
}

resource "aws_iam_role_policy" "demo_plan_deny_other_envs" {
  name   = "deny-other-envs"
  role   = aws_iam_role.demo_plan.id
  policy = data.aws_iam_policy_document.deny_other_envs["demo"].json
}
