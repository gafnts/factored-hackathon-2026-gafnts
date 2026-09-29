output "gateway_url" {
  value = aws_bedrockagentcore_gateway.this.gateway_url
}

output "target" {
  description = "The read tools' target; a tool's action is named <target>___<tool>"
  value       = local.target
}
