variable "prefix" {
  description = "Prefix of every name in the environment, such as banking-agent-local"
  type        = string
}

variable "config" {
  description = "What the app reads from config.json at load (ADR-0007): public IDs and URLs only, never a customer's"
  type        = map(string)
}

variable "connect_src" {
  description = "Origins the page may call besides the site itself: Cognito's API and the Runtime"
  type        = list(string)
}
