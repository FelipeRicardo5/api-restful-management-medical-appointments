output "alb_dns_name" {
  value = module.ecs_service.alb_dns_name
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "db_endpoint" {
  value = module.rds.endpoint
}
