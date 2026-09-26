output "local_role_arn" {
  value = aws_iam_role.deploy["local"].arn
}

output "demo_role_arn" {
  value = aws_iam_role.deploy["demo"].arn
}

output "demo_plan_role_arn" {
  value = aws_iam_role.demo_plan.arn
}
