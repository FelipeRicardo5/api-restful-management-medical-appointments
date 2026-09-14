resource "random_password" "db_password" {
  length  = 32
  special = false
}

module "network" {
  source      = "../../modules/network"
  project     = var.project
  environment = var.environment
}

module "ecr" {
  source          = "../../modules/ecr"
  repository_name = "${var.project}-api"
  create          = false # the shared repository is created by envs/staging
}

module "secrets" {
  source      = "../../modules/secrets"
  project     = var.project
  environment = var.environment
  db_password = random_password.db_password.result

  plain_config = {
    DEBUG                = "False"
    ALLOWED_HOSTS        = var.allowed_hosts
    CORS_ALLOWED_ORIGINS = var.cors_allowed_origins
    DJANGO_LOG_LEVEL     = "INFO"
  }
}

module "rds" {
  source            = "../../modules/rds"
  project           = var.project
  environment       = var.environment
  subnet_ids        = module.network.subnet_ids
  security_group_id = module.network.rds_security_group_id
  db_password       = random_password.db_password.result
  instance_class    = var.db_instance_class
  multi_az          = true
}

resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.project}/${var.environment}/database-url"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgres://postgres:${random_password.db_password.result}@${module.rds.endpoint}/${module.rds.db_name}"
}

module "ecs_service" {
  source                = "../../modules/ecs-service"
  project               = var.project
  environment           = var.environment
  vpc_id                = module.network.vpc_id
  subnet_ids            = module.network.subnet_ids
  alb_security_group_id = module.network.alb_security_group_id
  ecs_security_group_id = module.network.ecs_security_group_id
  desired_count         = var.desired_count
  task_cpu              = 512
  task_memory           = 1024

  container_image = "public.ecr.aws/docker/library/nginx:latest"

  plain_environment = {
    DEBUG                = "False"
    ALLOWED_HOSTS        = var.allowed_hosts
    CORS_ALLOWED_ORIGINS = var.cors_allowed_origins
    DJANGO_LOG_LEVEL     = "INFO"
  }

  secret_environment = {
    SECRET_KEY      = module.secrets.django_secret_key_arn
    JWT_SIGNING_KEY = module.secrets.jwt_signing_key_arn
    DATABASE_URL    = aws_secretsmanager_secret.database_url.arn
  }

  secret_arns = [
    module.secrets.django_secret_key_arn,
    module.secrets.jwt_signing_key_arn,
    aws_secretsmanager_secret.database_url.arn,
  ]
}
