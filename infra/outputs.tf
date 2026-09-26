output "aws_account_id" {
  description = "Account the stack is deployed into. Doubles as a canary that the deploy role and backend are wired correctly."
  value       = data.aws_caller_identity.current.account_id
}

output "environment" {
  value = var.environment
}
