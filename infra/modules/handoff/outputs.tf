output "cases_table" {
  value = {
    name = aws_dynamodb_table.cases.name
    arn  = aws_dynamodb_table.cases.arn
  }
}

output "function" {
  value = {
    name = aws_lambda_function.file_handoff.function_name
    arn  = aws_lambda_function.file_handoff.arn
  }
}
