data "aws_caller_identity" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  oidc_provider = "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  envs          = ["local", "prototype"]

  state_bucket_arn = "arn:aws:s3:::${var.state_bucket_name}"
  # Every state prefix in the bucket: one per env, plus this module's own.
  state_prefixes = concat(local.envs, ["iam"])
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

# Only jobs running in the `prototype` GitHub Environment can assume the prototype deploy
# role. Restricting that environment's deployment branches to `main` is what
# makes a merge to main the only path to a prototype apply.
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

# PowerUserAccess and ReadOnlyAccess both reach every object in the account, so
# these denies are what confine a role to its own environment's state and keep
# it from reconfiguring or deleting the bucket.
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

# The ceiling for every role a deploy role creates: no IAM, and nothing tagged
# for another environment. Without it, a deploy role could create a role with
# AdministratorAccess, let itself assume it, and escape both limits.
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

# PowerUserAccess excludes IAM, so each deploy role gets just enough to manage
# the execution roles its own stack creates (named <project>-<env>-*), and only
# while they carry the environment's boundary. The explicit deny keeps a deploy
# role from editing itself or its siblings.
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

# Read-only role for the prototype plan posted on PRs into main. PR workflows never
# hold write credentials; only the apply job in the `prototype` environment does.
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

# ReadOnlyAccess already reads the bucket; this confines it to prototype state.
# PR plans run with -lock=false, so the role never writes a lock file.
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
