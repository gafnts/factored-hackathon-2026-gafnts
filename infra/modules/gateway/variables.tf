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
  description = "App clients whose access tokens the Gateway accepts"
  type        = list(string)
}

variable "reads_zip" {
  description = "The read tools' zip, written by make build"
  type        = string
}
