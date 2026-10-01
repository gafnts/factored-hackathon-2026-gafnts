output "overlay" {
  value = {
    name = aws_dynamodb_table.overlay.name
    arn  = aws_dynamodb_table.overlay.arn
  }
}

output "confirmations" {
  value = {
    name = aws_dynamodb_table.confirmations.name
    arn  = aws_dynamodb_table.confirmations.arn
  }
}

output "readable_attributes" {
  description = "Every attribute of the overlay's items but is_fraud, which the tools may read"
  value       = local.readable
}

output "counted_attributes" {
  description = "A fault plan's key and count, which are all the tools may change"
  value       = local.counted
}
