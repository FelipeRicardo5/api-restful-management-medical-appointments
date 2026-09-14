aws_region           = "us-east-1"
project              = "medapp"
environment          = "production"
allowed_hosts        = "*.elb.amazonaws.com"
cors_allowed_origins = ""
db_instance_class    = "db.t3.small"
desired_count        = 2
