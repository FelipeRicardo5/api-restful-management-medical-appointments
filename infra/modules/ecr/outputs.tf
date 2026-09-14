output "repository_url" {
  value = var.create ? aws_ecr_repository.this[0].repository_url : data.aws_ecr_repository.existing[0].repository_url
}

output "repository_name" {
  value = var.repository_name
}
