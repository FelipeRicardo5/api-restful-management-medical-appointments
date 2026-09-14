variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "plain_config" {
  type        = map(string)
  description = "Non-sensitive config values (DEBUG, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, ...) stored in SSM Parameter Store."
  default     = {}
}
