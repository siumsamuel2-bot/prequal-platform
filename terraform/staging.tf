# Staging Environment Infrastructure (MID-625)
# Provisions the staging ECS environment used for QA load testing of the
# Analytics Dashboard (MID-592) and Analytics Service (MID-588).
# Satisfies the resource references in codedeploy.tf (staging deployment group)
# and the deploy-staging jobs in ci-cd.yml / analytics-service.yml.

# =============================================================================
# ECS Cluster (staging)
# =============================================================================
resource "aws_ecs_cluster" "prequal_cluster_staging" {
  name = "prequal-cluster-staging"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "prequal-cluster-staging"
    Environment = "staging"
  }
}

# =============================================================================
# Staging SSM parameters (placeholder values follow the prod REPLACE_WITH_*
# pattern; real values are managed out-of-band, hence ignore_changes)
# =============================================================================
resource "aws_ssm_parameter" "staging_database_url" {
  name   = "/prequal/staging/database-url"
  type   = "SecureString"
  value  = "REPLACE_WITH_STAGING_DATABASE_URL"
  key_id = aws_kms_key.rds_encryption.arn

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name        = "prequal-staging-database-url"
    Environment = "staging"
  }
}

resource "aws_ssm_parameter" "staging_analytics_database_url" {
  name   = "/prequal/staging/analytics/database-url"
  type   = "SecureString"
  value  = "REPLACE_WITH_STAGING_ANALYTICS_DATABASE_URL"
  key_id = aws_kms_key.rds_encryption.arn

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name        = "prequal-staging-analytics-database-url"
    Environment = "staging"
  }
}

# Grant the platform task execution role read access to the staging params
resource "aws_iam_role_policy" "ecs_task_staging_ssm_policy" {
  name = "prequal-ecs-staging-ssm-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ssm:GetParameters"]
      Resource = [
        aws_ssm_parameter.staging_database_url.arn,
        aws_ssm_parameter.staging_analytics_database_url.arn
      ]
    }]
  })
}

# Grant the analytics task execution role read access to its staging param
resource "aws_iam_role_policy" "analytics_task_staging_ssm_policy" {
  name = "analytics-service-staging-ssm-policy"
  role = aws_iam_role.analytics_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameters"]
      Resource = [aws_ssm_parameter.staging_analytics_database_url.arn]
    }]
  })
}

# =============================================================================
# Staging ALB + listeners (dedicated LB so load tests never touch production)
# =============================================================================
resource "aws_lb" "prequal_alb_staging" {
  name               = "prequal-alb-staging"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.prequal_alb_sg.id]
  subnets            = aws_subnet.prequal_public_subnets[*].id

  tags = {
    Name        = "prequal-alb-staging"
    Environment = "staging"
  }
}

resource "aws_acm_certificate" "prequal_staging_cert" {
  domain_name       = var.staging_domain_name
  validation_method = "DNS"

  tags = {
    Name        = "prequal-staging-cert"
    Environment = "staging"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "staging_http" {
  load_balancer_arn = aws_lb.prequal_alb_staging.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "staging_https" {
  load_balancer_arn = aws_lb.prequal_alb_staging.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.prequal_staging_cert.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prequal_tg_staging_blue.arn
  }
}

# =============================================================================
# Platform task definition + service (staging)
# =============================================================================
resource "aws_cloudwatch_log_group" "ecs_prequal_staging" {
  name              = "/ecs/prequal-app-staging"
  retention_in_days = 14

  tags = {
    Name        = "prequal-staging-ecs-logs"
    Environment = "staging"
  }
}

resource "aws_ecs_task_definition" "prequal_task_staging" {
  family                   = "prequal-task-staging"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name  = "prequal-app"
    image = "${aws_ecr_repository.prequal_repo.repository_url}:latest"
    portMappings = [{
      containerPort = 3000
      hostPort      = 3000
      protocol      = "tcp"
    }]
    environment = [
      { name = "NODE_ENV", value = "staging" },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379/1" }
    ]
    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = aws_ssm_parameter.staging_database_url.arn
      },
      {
        name      = "SECRET_KEY"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:SECRET_KEY::"
      },
      {
        name      = "ENCRYPTION_KEY"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:ENCRYPTION_KEY::"
      },
      {
        name      = "OSHA_API_KEY"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:OSHA_API_KEY::"
      },
      {
        name      = "SMTP_HOST"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:SMTP_HOST::"
      },
      {
        name      = "SMTP_PORT"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:SMTP_PORT::"
      },
      {
        name      = "SMTP_USER"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:SMTP_USER::"
      },
      {
        name      = "SMTP_PASSWORD"
        valueFrom = "${aws_secretsmanager_secret.api_secrets.arn}:SMTP_PASSWORD::"
      },
      {
        name      = "STRIPE_SECRET_KEY"
        valueFrom = "${aws_secretsmanager_secret.stripe_secrets.arn}:STRIPE_SECRET_KEY::"
      },
      {
        name      = "STRIPE_PUBLISHABLE_KEY"
        valueFrom = "${aws_secretsmanager_secret.stripe_secrets.arn}:STRIPE_PUBLISHABLE_KEY::"
      },
      {
        name      = "STRIPE_WEBHOOK_SECRET"
        valueFrom = "${aws_secretsmanager_secret.stripe_secrets.arn}:STRIPE_WEBHOOK_SECRET::"
      }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs_prequal_staging.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])

  tags = {
    Name        = "prequal-task-staging"
    Environment = "staging"
  }
}

resource "aws_ecs_service" "prequal_service_staging" {
  name            = "prequal-service-staging"
  cluster         = aws_ecs_cluster.prequal_cluster_staging.id
  task_definition = aws_ecs_task_definition.prequal_task_staging.arn
  desired_count   = var.staging_desired_count
  launch_type     = "FARGATE"

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.prequal_private_subnets[*].id
    security_groups  = [aws_security_group.prequal_ecs_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.prequal_tg_staging_blue.arn
    container_name   = "prequal-app"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.staging_https]

  tags = {
    Name        = "prequal-service-staging"
    Environment = "staging"
  }
}

# =============================================================================
# Analytics service staging (load testing target for MID-588 / MID-592)
# =============================================================================
resource "aws_cloudwatch_log_group" "analytics_service_staging" {
  name              = "/ecs/analytics-service-staging"
  retention_in_days = 14

  tags = {
    Name        = "analytics-service-staging-logs"
    Environment = "staging"
  }
}

resource "aws_ecs_task_definition" "analytics_service_task_staging" {
  family                   = "analytics-service-task-staging"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.analytics_task_execution_role.arn
  task_role_arn            = aws_iam_role.analytics_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "analytics-service"
      image     = "${aws_ecr_repository.prequal_repo.repository_url}:latest"
      essential = true
      portMappings = [{
        containerPort = 8006
        hostPort      = 8006
        protocol      = "tcp"
      }]
      environment = [
        { name = "ENVIRONMENT", value = "staging" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379/2" },
        { name = "ANALYTICS_EVENTS_STREAM", value = "analytics:events:staging" },
        { name = "ANALYTICS_CONSUMER_GROUP", value = "analytics-ingestors:staging" }
      ]
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_ssm_parameter.staging_analytics_database_url.arn
        },
        {
          name      = "SERVICE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.analytics_service_auth.arn}:SERVICE_API_KEY::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.analytics_service_staging.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    },
    {
      name      = "analytics-worker"
      image     = "${aws_ecr_repository.prequal_repo.repository_url}:latest"
      essential = true
      command   = ["python", "-m", "app.worker"]
      environment = [
        { name = "ENVIRONMENT", value = "staging" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379/2" },
        { name = "ANALYTICS_EVENTS_STREAM", value = "analytics:events:staging" },
        { name = "ANALYTICS_CONSUMER_GROUP", value = "analytics-ingestors:staging" }
      ]
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_ssm_parameter.staging_analytics_database_url.arn
        },
        {
          name      = "SERVICE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.analytics_service_auth.arn}:SERVICE_API_KEY::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.analytics_service_staging.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])

  tags = {
    Name        = "analytics-service-task-staging"
    Environment = "staging"
  }
}

resource "aws_lb_target_group" "analytics_tg_staging" {
  name        = "analytics-tg-staging"
  port        = 8006
  protocol    = "HTTP"
  vpc_id      = aws_vpc.prequal_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name        = "analytics-tg-staging"
    Environment = "staging"
  }
}

resource "aws_lb_listener_rule" "analytics_staging_https_rule" {
  listener_arn = aws_lb_listener.staging_https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.analytics_tg_staging.arn
  }

  condition {
    path_pattern {
      values = ["/analytics/*", "/api/v1/analytics*"]
    }
  }
}

resource "aws_ecs_service" "analytics_service_staging" {
  name            = "analytics-service-staging"
  cluster         = aws_ecs_cluster.prequal_cluster_staging.id
  task_definition = aws_ecs_task_definition.analytics_service_task_staging.arn
  desired_count   = var.staging_desired_count
  launch_type     = "FARGATE"

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.prequal_private_subnets[*].id
    security_groups  = [aws_security_group.analytics_service_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.analytics_tg_staging.arn
    container_name   = "analytics-service"
    container_port   = 8006
  }

  depends_on = [aws_lb_listener_rule.analytics_staging_https_rule]

  tags = {
    Name        = "analytics-service-staging"
    Environment = "staging"
  }
}

# =============================================================================
# Outputs
# =============================================================================
output "staging_alb_dns_name" {
  description = "DNS name of the staging Application Load Balancer"
  value       = aws_lb.prequal_alb_staging.dns_name
}

output "staging_ecs_cluster_name" {
  description = "Name of the staging ECS cluster"
  value       = aws_ecs_cluster.prequal_cluster_staging.name
}
