output "aws_account_id" {
  description = "Account the stack is deployed into. Doubles as a canary that the deploy role and backend are wired correctly."
  value       = data.aws_caller_identity.current.account_id
}

output "environment" {
  value = var.environment
}

output "prefix" {
  description = "Prefix of every name in the environment"
  value       = local.prefix
}

output "permissions_boundary_arn" {
  description = "Boundary every IAM role in this stack must carry"
  value       = local.permissions_boundary_arn
}

output "user_pool_id" {
  value = module.identity.user_pool_id
}

output "customer_client_id" {
  value = module.identity.customer_client_id
}

output "staff_client_id" {
  value = module.identity.staff_client_id
}
