output "table_name" {
  value = aws_dynamodb_table.this.name
}

output "table_arn" {
  value = aws_dynamodb_table.this.arn
}

output "readable_attributes" {
  description = "Every attribute the read tools may name"
  value       = local.readable
}

output "stamp" {
  value = {
    snapshot         = local.manifest.snapshot
    pipeline_version = local.manifest.pipeline_version
  }
}

output "clock" {
  value = local.manifest.clock
}

output "items" {
  description = "How many items the export holds, by kind and in total"
  value       = local.manifest.items
}
