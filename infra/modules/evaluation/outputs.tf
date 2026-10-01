output "role_arn" {
  value = aws_iam_role.harness.arn
}

output "bucket" {
  value = aws_s3_bucket.evaluation.id
}
