# Bootstrap the state bucket + lock table once, by hand, before first
# `terraform init` (see README.md > "Deploy flow" for the exact commands):
#   aws s3api create-bucket --bucket <TF_STATE_BUCKET> ...
#   aws dynamodb create-table --table-name terraform-locks ...

terraform {
  backend "s3" {
    bucket         = "medical-appointments-api-tfstate" # override with -backend-config if your bucket name differs
    key            = "staging/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
