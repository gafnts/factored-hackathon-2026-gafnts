output "runtime_arn" {
  value = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "invoke_url" {
  value = "https://bedrock-agentcore.${local.region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
}

output "model_key_secret" {
  description = "The secret make model-key stores the Anthropic API key in"
  value       = data.aws_secretsmanager_secret.model_key.name
}

output "runtime_log_group" {
  value = aws_cloudwatch_log_group.runtime.name
}
