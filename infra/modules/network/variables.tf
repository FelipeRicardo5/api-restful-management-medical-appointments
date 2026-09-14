variable "project" {
  type        = string
  description = "Project name prefix used in resource names/tags."
}

variable "environment" {
  type        = string
  description = "Environment name, e.g. staging or production."
}
