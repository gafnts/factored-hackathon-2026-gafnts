variable "project_name" {
  type    = string
  default = "banking-agent"
}

variable "environment" {
  description = "Tagged on every resource; each deploy role can only touch its own environment's."
  type        = string
  validation {
    condition     = contains(["local", "prototype"], var.environment)
    error_message = "environment must be one of: local, prototype."
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "log_retention_days" {
  description = "Retention of every log group the stack creates (ADR-0004, Data retention)"
  type        = number
  default     = 30
}
