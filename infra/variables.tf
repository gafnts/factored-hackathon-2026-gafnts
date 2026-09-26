variable "project_name" {
  type    = string
  default = "banking-agent"
}

variable "environment" {
  description = "One of: local (your laptop) or demo (the hosted prototype, deployed by CI). Tagged on every resource; the deploy roles can only touch resources tagged with their own environment."
  type        = string
  validation {
    condition     = contains(["local", "demo"], var.environment)
    error_message = "environment must be one of: local, demo."
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}
