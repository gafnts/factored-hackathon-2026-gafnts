variable "prefix" {
  description = "Prefix of every name in the environment, such as banking-agent-local"
  type        = string
}

variable "permissions_boundary_arn" {
  type = string
}

variable "log_retention_days" {
  type = number
}

variable "discovery_url" {
  description = "The user pool's OpenID configuration"
  type        = string
}

variable "allowed_clients" {
  description = "App clients whose access tokens the Runtime accepts"
  type        = list(string)
}

variable "customer_client_id" {
  description = "The customers' app client, which the entrypoint checks tokens against"
  type        = string
}

variable "required_group" {
  description = "Cognito group a token's cognito:groups claim must contain"
  type        = string
}

variable "gateway_url" {
  type = string
}

variable "gateway_target" {
  description = "The read tools' target, which names each tool as <target>___<tool>"
  type        = string
}

variable "tools_data" {
  description = "The stamp and the clock of the export the tools read, which every turn's record carries"
  type = object({
    stamp = object({ snapshot = string, pipeline_version = string })
    clock = object({ business_date = string, as_of = string })
  })
}

variable "runtime_zip" {
  description = "The Runtime's zip, written by make build"
  type        = string
}
