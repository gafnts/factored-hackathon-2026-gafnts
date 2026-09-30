output "gateway_url" {
  value = aws_bedrockagentcore_gateway.this.gateway_url
}

output "targets" {
  description = "Each tool's target; a tool's action is named <target>___<tool>"
  value       = local.tool_targets
}
