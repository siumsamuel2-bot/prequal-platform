# Automated secret rotation (MID-594)
#
# Attaches a generic rotation Lambda to the self-contained application secret
# so the JWT signing key is regenerated automatically with a 90-day maximum
# lifetime. Provider-managed credentials (Stripe, OSHA, SMTP, analytics service
# key) are rotated through their runbooks in docs/SECRET_MANAGEMENT.md and
# docs/SECRET_ROTATION_RUNBOOK.md.

data "archive_file" "secret_rotation" {
  type        = "zip"
  source_file = "${path.module}/secret_rotation/index.py"
  output_path = "${path.module}/.build/secret_rotation.zip"
}

resource "aws_iam_role" "secret_rotation_role" {
  name = "prequal-secret-rotation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "secret_rotation_policy" {
  name = "prequal-secret-rotation-policy"
  role = aws_iam_role.secret_rotation_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage"
        ]
        Resource = [
          aws_secretsmanager_secret.api_secrets.arn,
          aws_secretsmanager_secret.stripe_secrets.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.rds_encryption.arn
      },
      {
        Effect   = "Allow"
        Action   = ["ecs:UpdateService", "ecs:DescribeServices"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "secret_rotation" {
  name              = "/aws/lambda/prequal-secret-rotation"
  retention_in_days = 30
}

resource "aws_lambda_function" "secret_rotation" {
  function_name    = "prequal-secret-rotation"
  description      = "Rotates self-contained Prequal application secrets"
  role             = aws_iam_role.secret_rotation_role.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.11"
  timeout          = 60
  filename         = data.archive_file.secret_rotation.output_path
  source_code_hash = data.archive_file.secret_rotation.output_base64sha256

  environment {
    variables = {
      ECS_CLUSTER = aws_ecs_cluster.prequal_cluster.name
      ECS_SERVICE = aws_ecs_service.prequal_service.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.secret_rotation]
}

resource "aws_lambda_permission" "secret_rotation" {
  statement_id  = "AllowSecretsManagerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secret_rotation.function_name
  principal     = "secretsmanager.amazonaws.com"
}

# 90-day maximum lifetime for the JWT signing key. The ECS service is forced to
# redeploy after each rotation so running tasks pick up the new value.
resource "aws_secretsmanager_secret_rotation" "api_secrets" {
  secret_id           = aws_secretsmanager_secret.api_secrets.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation.arn

  rotation_rules {
    automatically_after_days = 90
  }
}
