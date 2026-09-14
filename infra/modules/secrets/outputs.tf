output "django_secret_key_arn" {
  value = aws_secretsmanager_secret.django_secret_key.arn
}

output "jwt_signing_key_arn" {
  value = aws_secretsmanager_secret.jwt_signing_key.arn
}

output "db_password_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}

output "db_password" {
  value     = var.db_password
  sensitive = true
}

output "ssm_parameter_arns" {
  value = { for k, v in aws_ssm_parameter.config : k => v.arn }
}
