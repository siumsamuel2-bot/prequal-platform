terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "prequal_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "prequal-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "prequal_igw" {
  vpc_id = aws_vpc.prequal_vpc.id

  tags = {
    Name = "prequal-igw"
  }
}

# Public Subnets
resource "aws_subnet" "prequal_public_subnets" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.prequal_vpc.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "prequal-public-subnet-${count.index}"
  }
}

# Private Subnets
resource "aws_subnet" "prequal_private_subnets" {
  count                   = length(var.private_subnet_cidrs)
  vpc_id                  = aws_vpc.prequal_vpc.id
  cidr_block              = var.private_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "prequal-private-subnet-${count.index}"
  }
}

# Route Tables
resource "aws_route_table" "prequal_public_rt" {
  vpc_id = aws_vpc.prequal_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.prequal_igw.id
  }

  tags = {
    Name = "prequal-public-rt"
  }
}

# Associate public subnets with route table
resource "aws_route_table_association" "prequal_public_assoc" {
  count          = length(aws_subnet.prequal_public_subnets)
  subnet_id      = aws_subnet.prequal_public_subnets[count.index].id
  route_table_id = aws_route_table.prequal_public_rt.id
}

# Security Groups
resource "aws_security_group" "prequal_alb_sg" {
  name        = "prequal-alb-sg"
  description = "Allow HTTP/HTTPS inbound"
  vpc_id      = aws_vpc.prequal_vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prequal-alb-sg"
  }
}

resource "aws_security_group" "prequal_ecs_sg" {
  name        = "prequal-ecs-sg"
  description = "Allow inbound from ALB"
  vpc_id      = aws_vpc.prequal_vpc.id

  ingress {
    description = "HTTP from ALB"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    security_groups = [aws_security_group.prequal_alb_sg.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prequal-ecs-sg"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "prequal_cluster" {
  name = "prequal-cluster"

  tags = {
    Name = "prequal-cluster"
  }
}

# ECR Repository
resource "aws_ecr_repository" "prequal_repo" {
  name                 = "prequal-platform"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "prequal-platform"
  }
}

# Application Load Balancer
resource "aws_lb" "prequal_alb" {
  name               = "prequal-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.prequal_alb_sg.id]
  subnets            = aws_subnet.prequal_public_subnets[*].id

  tags = {
    Name = "prequal-alb"
  }
}

# Target Group
resource "aws_lb_target_group" "prequal_tg" {
  name     = "prequal-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.prequal_vpc.id

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200-299"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = {
    Name = "prequal-tg"
  }
}

# Listener - HTTP to HTTPS redirect
resource "aws_lb_listener" "prequal_http" {
  load_balancer_arn = aws_lb.prequal_alb.arn
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

# ACM Certificate for HTTPS
resource "aws_acm_certificate" "prequal_cert" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = {
    Name = "prequal-production-cert"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# HTTPS Listener with SSL certificate
resource "aws_lb_listener" "prequal_https" {
  load_balancer_arn = aws_lb.prequal_alb.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.prequal_cert.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prequal_tg.arn
  }
}

# SSM Parameter for DATABASE_URL
resource "aws_ssm_parameter" "database_url" {
  name  = "/prequal/database-url"
  type  = "SecureString"
  value = "postgresql://${aws_db_instance.prequal_db.username}:${var.db_password}@${aws_db_instance.prequal_db.address}:${aws_db_instance.prequal_db.port}/${aws_db_instance.prequal_db.name}"
  key_id = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "prequal-database-url"
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "prequal-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_ecr_policy" {
  name = "prequal-ecs-ecr-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = aws_ecr_repository.prequal_repo.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy for ECS Task to access Secrets Manager
resource "aws_iam_role_policy" "ecs_task_secrets_policy" {
  name = "prequal-ecs-secrets-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.stripe_secrets.arn,
          aws_secretsmanager_secret.api_secrets.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.rds_encryption.arn
      }
    ]
  })
}

# RDS Database
resource "aws_db_subnet_group" "prequal_db_subnet_group" {
  name       = "prequal-db-subnet-group"
  subnet_ids = aws_subnet.prequal_private_subnets[*].id

  tags = {
    Name = "prequal-db-subnet-group"
  }
}

resource "aws_db_instance" "prequal_db" {
  identifier = "prequal-db"
  engine = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  db_name = "prequal"
  username = "postgres"
  password = var.db_password
  skip_final_snapshot = false
  final_snapshot_identifier = "prequal-db-final-snapshot"
  backup_retention_period = 7
  backup_window = "03:00-04:00"
  maintenance_window = "Mon:04:00-Mon:05:00"
  delete_automated_backups = false
  copy_tags_to_snapshot = true
  vpc_security_group_ids = [aws_security_group.prequal_ecs_sg.id]
  db_subnet_group_name = aws_db_subnet_group.prequal_db_subnet_group.name
  storage_encrypted = true
  kms_key_id = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "prequal-db"
  }
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "prequal_redis_subnet_group" {
  name       = "prequal-redis-subnet-group"
  subnet_ids = aws_subnet.prequal_private_subnets[*].id

  tags = {
    Name = "prequal-redis-subnet-group"
  }
}

resource "aws_elasticache_replication_group" "prequal_redis" {
  replication_group_id = "prequal-redis"
  description = "Redis cluster for Prequal platform"
  engine = "redis"
  node_type = "cache.t3.micro"
  num_cache_clusters = 1
  automatic_failover_enabled = false
  subnet_group_name = aws_elasticache_subnet_group.prequal_redis_subnet_group.name
  security_group_ids = [aws_security_group.prequal_ecs_sg.id]
  maintenance_window = "sun:05:00-sun:06:00"
  snapshot_retention_limit = 1
  snapshot_window = "05:00-06:00"

  tags = {
    Name = "prequal-redis"
  }
}

# KMS Key for RDS Encryption
resource "aws_kms_key" "rds_encryption" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "prequal-rds-encryption-key"
  }
}

resource "aws_kms_alias" "rds_encryption" {
  name          = "alias/prequal-rds-encryption"
  target_key_id = aws_kms_key.rds_encryption.key_id
}

# AWS Secrets Manager for Stripe and API secrets
resource "aws_secretsmanager_secret" "stripe_secrets" {
  name        = "prequal/stripe-secrets"
  description = "Stripe API keys and webhook secrets for production"
  kms_key_id  = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "prequal-stripe-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "stripe_secrets" {
  secret_id = aws_secretsmanager_secret.stripe_secrets.id
  secret_string = jsonencode({
    STRIPE_SECRET_KEY     = "REPLACE_WITH_PRODUCTION_SECRET_KEY"
    STRIPE_PUBLISHABLE_KEY = "REPLACE_WITH_PRODUCTION_PUBLISHABLE_KEY"
    STRIPE_WEBHOOK_SECRET  = "REPLACE_WITH_WEBHOOK_SECRET"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "api_secrets" {
  name        = "prequal/api-secrets"
  description = "General API keys and secrets for production"
  kms_key_id  = aws_kms_key.rds_encryption.arn

  tags = {
    Name = "prequal-api-secrets"
    # Comma-separated JSON keys the rotation Lambda regenerates on schedule.
    # Only self-contained, app-generated values belong here. Provider-managed
    # credentials (OSHA_API_KEY, SMTP_*, ENCRYPTION_KEY) are rotated manually
    # because they must be updated with the provider / re-encrypt data first.
    RotationKeys = "SECRET_KEY"
  }
}

resource "aws_secretsmanager_secret_version" "api_secrets" {
  secret_id = aws_secretsmanager_secret.api_secrets.id
  secret_string = jsonencode({
    SECRET_KEY            = "REPLACE_WITH_PRODUCTION_SECRET_KEY"
    OSHA_API_KEY          = "REPLACE_WITH_OSHA_API_KEY"
    SMTP_HOST             = "REPLACE_WITH_SMTP_HOST"
    SMTP_PORT             = "587"
    SMTP_USER             = "REPLACE_WITH_SMTP_USER"
    SMTP_PASSWORD         = "REPLACE_WITH_SMTP_PASSWORD"
    ENCRYPTION_KEY        = "REPLACE_WITH_ENCRYPTION_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# AWS WAF Web ACL for DDoS and rate limiting
resource "aws_wafv2_web_acl" "prequal_waf" {
  name        = "prequal-waf"
  description = "WAF for DDoS protection and rate limiting"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rate-based rule for DDoS protection
  rule {
    name     = "rate-limit-rule"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "prequal-rate-limit-rule"
      sampled_requests_enabled  = true
    }
  }

  # AWS Managed Rules for common attacks
  rule {
    name     = "aws-managed-common-rule-set"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        rule_action_override {
          name = "SizeRestrictions_QUERYSTRING"
          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "prequal-aws-managed-common-rule-set"
      sampled_requests_enabled  = true
    }
  }

  # AWS Managed Rules for SQL injection
  rule {
    name     = "aws-managed-sql-injection"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "prequal-aws-managed-sqli-rule-set"
      sampled_requests_enabled  = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name               = "prequal-waf"
    sampled_requests_enabled  = true
  }

  tags = {
    Name = "prequal-waf"
  }
}

# Associate WAF with ALB
resource "aws_wafv2_web_acl_association" "prequal_alb_waf" {
  resource_arn = aws_lb.prequal_alb.arn
  web_acl_arn  = aws_wafv2_web_acl.prequal_waf.arn
}

# ECS Task Definition
resource "aws_ecs_task_definition" "prequal_task" {
  family = "prequal-task"
  network_mode = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu = "256"
  memory = "512"
  execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name = "prequal-app"
    image = "${aws_ecr_repository.prequal_repo.repository_url}:latest"
    portMappings = [{
      containerPort = 3000
      hostPort = 3000
      protocol = "tcp"
    }]
    environment = [
      { name = "NODE_ENV", value = "production" },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379" }
    ]
    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/prequal/database-url"
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
        awslogs-group = "/ecs/prequal-app"
        awslogs-region = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

# CloudWatch Log Group for ECS logs
resource "aws_cloudwatch_log_group" "ecs_prequal" {
  name = "/ecs/prequal-app"
  retention_in_days = 30

  tags = {
    Name = "prequal-ecs-logs"
  }
}

# ECS Service
resource "aws_ecs_service" "prequal_service" {
  name            = "prequal-service"
  cluster         = aws_ecs_cluster.prequal_cluster.id
  task_definition = aws_ecs_task_definition.prequal_task.arn
  launch_type     = "FARGATE"
  desired_count   = 2

  network_configuration {
    subnets         = aws_subnet.prequal_private_subnets[*].id
    security_groups = [aws_security_group.prequal_ecs_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.prequal_tg.arn
    container_name   = "prequal-app"
    container_port   = 3000
  }

  depends_on = [
    aws_lb_listener.prequal_https
  ]
}

# SNS Topic for Alerts
resource "aws_sns_topic" "prequal_alerts" {
  name = "prequal-production-alerts"

  tags = {
    Name = "prequal-alerts"
  }
}

# SNS Topic Policy for CloudWatch Alarms
resource "aws_sns_topic_policy" "prequal_alerts_policy" {
  arn = aws_sns_topic.prequal_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = "SNS:Publish"
      Resource  = aws_sns_topic.prequal_alerts.arn
      Condition = {
        ArnLike = {
          "aws:SourceArn" = "arn:aws:cloudwatch:${var.aws_region}:${var.aws_account_id}:alarm:*"
        }
      }
    }]
  })
}

# SNS Email Subscription for Alerts
resource "aws_sns_topic_subscription" "prequal_alerts_email" {
  topic_arn = aws_sns_topic.prequal_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email

  lifecycle {
    ignore_changes = [endpoint]
  }
}

# CloudWatch Alarm - High Error Rate (5xx)
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "prequal-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when 5xx errors exceed threshold"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
  }

  tags = {
    Name = "prequal-high-error-rate-alarm"
  }
}

# CloudWatch Alarm - High Latency (p95)
resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "prequal-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "p95"
  threshold           = 2
  alarm_description   = "Alert when p95 latency exceeds 2 seconds"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
  }

  tags = {
    Name = "prequal-high-latency-alarm"
  }
}

# CloudWatch Alarm - ECS Service CPU Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_utilization" {
  alarm_name          = "prequal-ecs-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alert when ECS CPU utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    ClusterName = aws_ecs_cluster.prequal_cluster.name
    ServiceName = aws_ecs_service.prequal_service.name
  }

  tags = {
    Name = "prequal-ecs-cpu-alarm"
  }
}

# CloudWatch Alarm - ECS Service Memory Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_memory_utilization" {
  alarm_name          = "prequal-ecs-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alert when ECS memory utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    ClusterName = aws_ecs_cluster.prequal_cluster.name
    ServiceName = aws_ecs_service.prequal_service.name
  }

  tags = {
    Name = "prequal-ecs-memory-alarm"
  }
}

# CloudWatch Alarm - RDS CPU Utilization
resource "aws_cloudwatch_metric_alarm" "rds_cpu_utilization" {
  alarm_name          = "prequal-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alert when RDS CPU utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.prequal_db.id
  }

  tags = {
    Name = "prequal-rds-cpu-alarm"
  }
}

# CloudWatch Alarm - RDS Free Storage Space
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "prequal-rds-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120
  alarm_description   = "Alert when RDS free storage is below 5GB"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.prequal_db.id
  }

  tags = {
    Name = "prequal-rds-storage-alarm"
  }
}

# CloudWatch Alarm - RDS Database Connections
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "prequal-rds-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 100
  alarm_description   = "Alert when RDS connections exceed 100"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.prequal_db.id
  }

  tags = {
    Name = "prequal-rds-connections-alarm"
  }
}

# CloudWatch Alarm - ALB Unhealthy Host Count
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  alarm_name          = "prequal-unhealthy-hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "Alert when there are unhealthy targets"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.prequal_tg.arn_suffix
  }

  tags = {
    Name = "prequal-unhealthy-hosts-alarm"
  }
}

# CloudWatch Alarm - Stripe Webhook Failures (Custom Metric)
resource "aws_cloudwatch_metric_alarm" "stripe_webhook_failures" {
  alarm_name          = "prequal-stripe-webhook-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StripeWebhookFailures"
  namespace           = "Prequal/Application"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Stripe webhook failures exceed threshold"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]
  ok_actions          = [aws_sns_topic.prequal_alerts.arn]

  tags = {
    Name = "prequal-stripe-webhook-alarm"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "prequal_dashboard" {
  dashboard_name = "prequal-production"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.prequal_alb.arn_suffix],
            ["AWS/ApplicationELB", "5XXError", "LoadBalancer", aws_lb.prequal_alb.arn_suffix]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "ALB Request Count & Errors"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.prequal_alb.arn_suffix, { stat = "p95" }],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.prequal_alb.arn_suffix, { stat = "p50" }]
          ]
          period = 300
          region = var.aws_region
          title  = "ALB Response Time (p50, p95)"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.prequal_cluster.name, "ServiceName", aws_ecs_service.prequal_service.name],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", aws_ecs_cluster.prequal_cluster.name, "ServiceName", aws_ecs_service.prequal_service.name]
          ]
          period = 300
          region = var.aws_region
          title  = "ECS Service Resource Utilization"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.prequal_db.id],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_db_instance.prequal_db.id]
          ]
          period = 300
          region = var.aws_region
          title  = "RDS PostgreSQL Metrics"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_db_instance.prequal_db.id]
          ]
          period = 300
          region = var.aws_region
          title  = "RDS Free Storage"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", aws_elasticache_replication_group.prequal_redis.replication_group_id],
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "CacheClusterId", aws_elasticache_replication_group.prequal_redis.replication_group_id]
          ]
          period = 300
          region = var.aws_region
          title  = "ElastiCache Redis Metrics"
        }
      }
    ]
  })
}

# Outputs
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.prequal_alb.dns_name
}

output "db_endpoint" {
  description = "Endpoint of the RDS PostgreSQL instance"
  value       = aws_db_instance.prequal_db.address
}

output "redis_endpoint" {
  description = "Endpoint of the Redis ElastiCache cluster"
  value       = aws_elasticache_replication_group.prequal_redis.primary_end_point_address
}