output "bucket_name" {
  value = aws_s3_bucket.data.bucket
}

output "import_log_group" {
  value = aws_cloudwatch_log_group.imports.name
}
