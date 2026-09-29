variable "prefix" {
  description = "Prefix of every name in the environment, such as banking-agent-local"
  type        = string
}

variable "export" {
  description = "The gold export the table is created from"
  type = object({
    snapshot         = string
    pipeline_version = string
  })
}

variable "data_bucket" {
  description = "The bucket that holds the snapshots and their exports"
  type        = string
}

variable "contract" {
  description = "Path to tools-data.schema.json"
  type        = string
}
