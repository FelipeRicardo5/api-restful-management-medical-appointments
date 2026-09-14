terraform {
  backend "s3" {
    bucket         = "medical-appointments-api-tfstate"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
