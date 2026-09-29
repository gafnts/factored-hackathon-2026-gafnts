variable "project_name" {
  type    = string
  default = "banking-agent"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "log_retention_days" {
  description = "Retention of the DynamoDB import log group (ADR-0004, Data retention)"
  type        = number
  default     = 30
}
