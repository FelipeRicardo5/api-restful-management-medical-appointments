# Single shared repository referenced by both environments; images are
# distinguished by tag prefix (staging-<sha> / production-<sha>), set by
# .github/workflows/cd.yml. Only create this in one environment's state
# (staging) and pass its name as a data lookup from the other (production).

resource "aws_ecr_repository" "this" {
  count                = var.create ? 1 : 0
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  count      = var.create ? 1 : 0
  repository = aws_ecr_repository.this[0].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 10 images per environment prefix"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["staging", "production"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

data "aws_ecr_repository" "existing" {
  count = var.create ? 0 : 1
  name  = var.repository_name
}
