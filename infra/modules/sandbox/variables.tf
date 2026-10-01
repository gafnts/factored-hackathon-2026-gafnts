variable "prefix" {
  description = "Prefix of every name in the environment, such as banking-agent-local"
  type        = string
}

variable "contract" {
  description = "Path to the overlay's contract, whose attributes the tools may read and change"
  type        = string
}
