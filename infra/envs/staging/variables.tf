variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "medapp"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "allowed_hosts" {
  type    = string
  default = "*.elb.amazonaws.com"
}

variable "cors_allowed_origins" {
  type    = string
  default = ""
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "desired_count" {
  type    = number
  default = 1
}
