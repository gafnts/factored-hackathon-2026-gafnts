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

variable "tools_data_table" {
  type = string
}

variable "tools_data_table_arn" {
  type = string
}

variable "tools_data_attributes" {
  description = "Every attribute of the tools' data the read tools may name"
  type        = list(string)
}

variable "overlay_table" {
  description = "The sandbox's overlay, which the reads read and the block writes"
  type = object({
    name = string
    arn  = string
  })
}

variable "confirmations_table" {
  description = "The confirmations, which the block uses up"
  type = object({
    name = string
    arn  = string
  })
}

variable "tools_zip" {
  description = "The tools' zip, which both Lambdas run, written by make build"
  type        = string
}
