output "alb_dns_name" {
  value = module.ecs_service.alb_dns_name
}

output "db_endpoint" {
  value = module.rds.endpoint
}
