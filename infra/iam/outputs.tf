output "local_role_arn" {
  value = aws_iam_role.deploy["local"].arn
}

output "prototype_role_arn" {
  value = aws_iam_role.deploy["prototype"].arn
}

output "prototype_plan_role_arn" {
  value = aws_iam_role.prototype_plan.arn
}
