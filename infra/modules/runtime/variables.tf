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

variable "required_group" {
  description = "Cognito group a token's cognito:groups claim must contain"
  type        = string
}

variable "gateway_url" {
  type = string
}

variable "runtime_zip" {
  description = "The Runtime's zip, written by make build"
  type        = string
}
