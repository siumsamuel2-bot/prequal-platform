# Analytics Service Microservice Infrastructure (MID-591)
# Phase 1 extraction per MID-514/MID-588: independent CI/CD, deployment,
# and monitoring for the analytics-service (FastAPI, port 8006).

# =============================================================================
# Security Group
# =============================================================================
resource "aws_security_group" "analytics_service_sg" {
  name        = "analytics-service-sg"
  description = "Allow analytics service traffic from ALB; egress to DB/Redis"
  vpc_id      = aws_vpc.prequal_vpc.id

  ingress {
    description     = "Analytics service port from ALB"
    from_port       = 8006
    to_port         = 8006
    protocol        = "tcp"
    security_groups = [aws_security_group.prequal_alb_sg.id]
  }

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "analytics-service-sg"
  }
}

# =============================================================================
# Dedicated Database for Analytics Events
# =============================================================================
resource "aws_db_subnet_group" "analytics_db_subnet_group" {
  name       = "analytics-db-subnet-group"
  subnet_ids = aws_subnet.prequal_private_subnets[*].id

  tags = {
    Name = "analytics-db-subnet-group"
  }
}

resource "aws_db_instance" "analytics_db" {
  identifier             = "prequal-analytics-db"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_encrypted      = true
  kms_key_id             = aws_kms_key.rds_encryption.arn
  db_name                = "analytics_service"
  username               = "analytics_user"
  password               = var.analytics_db_password
  db_subnet_group_name   = aws_db_subnet_group.analytics_db_subnet_group.name
  vpc_security_group_ids = [aws_security_group.prequal_ecs_sg.id]
  skip_final_snapshot    = false
  final_snapshot_identifier = "prequal-analytics-db-final"
  multi_az               = false
  backup_retention_period = 7

  tags = {
    Name = "prequal-analytics-db"
  }
}

# SSM Parameter for the analytics service DATABASE_URL
resource "aws_ssm_parameter" "analytics_database_url" {
  name   = "/prequal/analytics/database-url"
  type   = "SecureString"
  value  = "postgresql://${aws_db_instance.analytics_db.username}:${var.analytics_db_password}@${aws_db_instance.analytics_db.address}:${aws_db_instance.analytics_db.port}/${aws_db_instance.analytics_db.name}"
  key_id = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "analytics-database-url"
  }
}

# =============================================================================
# Secrets: service-to-service authentication
# =============================================================================
resource "aws_secretsmanager_secret" "analytics_service_auth" {
  name        = "prequal/analytics/service-auth"
  description = "Service-to-service API key for the analytics service"
  kms_key_id  = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "analytics-service-auth"
  }
}

resource "aws_secretsmanager_secret_version" "analytics_service_auth" {
  secret_id = aws_secretsmanager_secret.analytics_service_auth.id
  secret_string = jsonencode({
    SERVICE_API_KEY = "REPLACE_WITH_SERVICE_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# IAM
# =============================================================================
resource "aws_iam_role" "analytics_task_execution_role" {
  name = "analytics-service-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "analytics-service-task-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "analytics_task_execution_policy" {
  role       = aws_iam_role.analytics_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "analytics_task_secrets_policy" {
  name = "analytics-service-secrets-policy"
  role = aws_iam_role.analytics_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "ssm:GetParameters"
        ]
        Resource = [
          aws_secretsmanager_secret.analytics_service_auth.arn,
          aws_ssm_parameter.analytics_database_url.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [
          aws_kms_key.rds_encryption.arn
        ]
      }
    ]
  })
}

# =============================================================================
# ECS Task Definition: API (8006) + ingestion worker
# =============================================================================
resource "aws_cloudwatch_log_group" "analytics_service" {
  name              = "/ecs/analytics-service"
  retention_in_days = 30

  tags = {
    Name = "analytics-service-logs"
  }
}

resource "aws_ecs_task_definition" "analytics_service_task" {
  family                   = "analytics-service-task"
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
        { name = "ENVIRONMENT", value = "production" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379/0" },
        { name = "ANALYTICS_EVENTS_STREAM", value = "analytics:events" },
        { name = "ANALYTICS_CONSUMER_GROUP", value = "analytics-ingestors" }
      ]
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_ssm_parameter.analytics_database_url.arn
        },
        {
          name      = "SERVICE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.analytics_service_auth.arn}:SERVICE_API_KEY::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.analytics_service.name
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
        { name = "ENVIRONMENT", value = "production" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379/0" },
        { name = "ANALYTICS_EVENTS_STREAM", value = "analytics:events" },
        { name = "ANALYTICS_CONSUMER_GROUP", value = "analytics-ingestors" }
      ]
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_ssm_parameter.analytics_database_url.arn
        },
        {
          name      = "SERVICE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.analytics_service_auth.arn}:SERVICE_API_KEY::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.analytics_service.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

# =============================================================================
# ALB routing: path-based rule to the analytics target group
# =============================================================================
resource "aws_lb_target_group" "analytics_tg" {
  name        = "analytics-tg"
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
    Name = "analytics-tg"
  }
}

resource "aws_lb_listener_rule" "analytics_https_rule" {
  listener_arn = aws_lb_listener.prequal_https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.analytics_tg.arn
  }

  condition {
    path_pattern {
      values = ["/analytics/*", "/api/v1/analytics*"]
    }
  }
}

# =============================================================================
# ECS Service (zero-downtime rolling deploys)
# =============================================================================
resource "aws_ecs_service" "analytics_service" {
  name            = "analytics-service"
  cluster         = aws_ecs_cluster.prequal_cluster.id
  task_definition = aws_ecs_task_definition.analytics_service_task.arn
  desired_count   = 2
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
    subnets         = aws_subnet.prequal_private_subnets[*].id
    security_groups = [aws_security_group.analytics_service_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.analytics_tg.arn
    container_name   = "analytics-service"
    container_port   = 8006
  }

  depends_on = [aws_lb_listener_rule.analytics_https_rule]

  tags = {
    Name = "analytics-service"
  }
}

# =============================================================================
# Monitoring & Alerting
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "analytics_high_error_rate" {
  alarm_name          = "analytics-service-high-error-rate"
  alarm_description   = "Analytics service error rate above 5%"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 10
  evaluation_periods  = 2
  period              = 300
  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.analytics_tg.arn_suffix
  }
  alarm_actions = [aws_sns_topic.prequal_alerts.arn]
  treat_missing_data = "notBreaching"

  tags = {
    Name = "analytics-high-error-rate"
  }
}

resource "aws_cloudwatch_metric_alarm" "analytics_high_latency" {
  alarm_name          = "analytics-service-high-latency"
  alarm_description   = "Analytics service p95 latency above 2s"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 2
  evaluation_periods  = 3
  period              = 300
  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.analytics_tg.arn_suffix
  }
  alarm_actions = [aws_sns_topic.prequal_alerts.arn]
  treat_missing_data = "notBreaching"

  tags = {
    Name = "analytics-high-latency"
  }
}

resource "aws_cloudwatch_metric_alarm" "analytics_unhealthy_hosts" {
  alarm_name          = "analytics-service-unhealthy-hosts"
  alarm_description   = "Analytics service has unhealthy hosts"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 3
  period              = 300
  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.analytics_tg.arn_suffix
  }
  alarm_actions = [aws_sns_topic.prequal_alerts.arn]
  treat_missing_data = "notBreaching"

  tags = {
    Name = "analytics-unhealthy-hosts"
  }
}
