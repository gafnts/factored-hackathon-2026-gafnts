variable "prefix" {
  description = "Prefix of every name in the environment, such as banking-agent-local"
  type        = string
}

variable "permissions_boundary_arn" {
  type = string
}

variable "user_pool_id" {
  description = "The pool the harness creates its test users in, signs them in, and deletes them from"
  type        = string
}

variable "overlay_table" {
  description = "The sandbox's overlay, where the harness writes a case's fixtures and fault plans"
  type = object({
    name = string
    arn  = string
  })
}

variable "confirmations_table" {
  type = object({
    name = string
    arn  = string
  })
}

variable "execution_records_table" {
  type = object({
    name = string
    arn  = string
  })
}

variable "cases_table" {
  description = "The handoff cases"
  type = object({
    name = string
    arn  = string
  })
}

variable "file_handoff_function" {
  description = "file_handoff, which the access cases call directly with another customer's payload or token"
  type = object({
    name = string
    arn  = string
  })
}

variable "retention_days" {
  description = "How long the bucket keeps each case's results (ADR-0004, Data retention)"
  type        = number
  default     = 90
}
