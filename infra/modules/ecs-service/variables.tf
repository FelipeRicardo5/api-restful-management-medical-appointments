variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "ecs_security_group_id" {
  type = string
}

variable "container_image" {
  type        = string
  description = "Initial image URI (e.g. <repo>:staging-bootstrap). CD deploys replace this via a new task-definition revision."
}

variable "plain_environment" {
  type    = map(string)
  default = {}
}

variable "secret_environment" {
  type        = map(string)
  description = "Map of container env var name -> Secrets Manager ARN."
  default     = {}
}

variable "secret_arns" {
  type        = list(string)
  description = "All secret ARNs the execution role needs read access to."
  default     = []
}

variable "task_cpu" {
  type    = number
  default = 256
}

variable "task_memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 1
}
