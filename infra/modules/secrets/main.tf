# Sensitive values (Django SECRET_KEY, DB password, JWT signing key) live in
# Secrets Manager and are injected into the ECS task via the task
# definition's `secrets` block (never as plain env vars). Non-sensitive
# config lives in SSM Parameter Store so it's still centrally managed and
# auditable without Secrets Manager's per-secret cost.

resource "random_password" "django_secret_key" {
  length  = 50
  special = false
}

resource "random_password" "jwt_signing_key" {
  length  = 50
  special = false
}

resource "aws_secretsmanager_secret" "django_secret_key" {
  name = "${var.project}/${var.environment}/django-secret-key"
}

resource "aws_secretsmanager_secret_version" "django_secret_key" {
  secret_id     = aws_secretsmanager_secret.django_secret_key.id
  secret_string = random_password.django_secret_key.result
}

resource "aws_secretsmanager_secret" "jwt_signing_key" {
  name = "${var.project}/${var.environment}/jwt-signing-key"
}

resource "aws_secretsmanager_secret_version" "jwt_signing_key" {
  secret_id     = aws_secretsmanager_secret.jwt_signing_key.id
  secret_string = random_password.jwt_signing_key.result
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.project}/${var.environment}/db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

resource "aws_ssm_parameter" "config" {
  for_each = var.plain_config

  name  = "/${var.project}/${var.environment}/${each.key}"
  type  = "String"
  value = each.value
}
