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

variable "tools_zip" {
  description = "The tools' zip, which every tool Lambda runs, written by make build"
  type        = string
}

variable "tools_data_table" {
  type = object({
    name = string
    arn  = string
  })
}

variable "tools_data_attributes" {
  description = "Every attribute of the tools' data, is_fraud included"
  type        = list(string)
}

variable "execution_records_table" {
  description = "The execution records, whose turns a case's evidence must be found in"
  type = object({
    name = string
    arn  = string
  })
}

variable "customer_client_id" {
  description = "The customers' app client, the only one whose tokens file_handoff accepts"
  type        = string
}

variable "overlay_table" {
  description = "The sandbox's overlay, where a fixture transaction's is_fraud is read"
  type = object({
    name = string
    arn  = string
  })
}
