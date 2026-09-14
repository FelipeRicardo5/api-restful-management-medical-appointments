variable "repository_name" {
  type        = string
  description = "ECR repository name, shared across environments."
}

variable "create" {
  type        = bool
  description = "Whether this call creates the repository (true in staging) or just looks it up (false in production)."
  default     = true
}
