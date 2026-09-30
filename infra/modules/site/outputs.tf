output "url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "bucket" {
  value = aws_s3_bucket.site.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "config" {
  description = "What config.json holds, for the development server"
  value       = var.config
}
