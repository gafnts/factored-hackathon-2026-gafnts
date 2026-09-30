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
