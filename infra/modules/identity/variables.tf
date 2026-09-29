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

variable "pre_token_zip" {
  description = "The pre-token trigger's zip, written by make build"
  type        = string
}
