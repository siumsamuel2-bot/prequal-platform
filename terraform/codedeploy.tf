# CodeDeploy Configuration for Zero-Downtime Deployments

# CodeDeploy Application for ECS
resource "aws_codedeploy_app" "prequal_production" {
  name             = "prequal-production"
  compute_platform = "ECS"

  tags = {
    Name = "prequal-production"
  }
}

resource "aws_codedeploy_app" "prequal_staging" {
  name             = "prequal-staging"
  compute_platform = "ECS"

  tags = {
    Name = "prequal-staging"
  }
}

# Deployment Group for Production
resource "aws_codedeploy_deployment_group" "production" {
  app_name               = aws_codedeploy_app.prequal_production.name
  deployment_group_name  = "production-deployment-group"
  service_role_arn       = aws_iam_role.codedeploy_role.arn
  deployment_config_name = "CodeDeployDefault.ECSAllAtOnce"

  deployment_style {
    deployment_option = "WITH_TRAFFIC_CONTROL"
    deployment_type   = "BLUE_GREEN"
  }

  blue_green_deployment_config {
    deployment_ready_option {
      action_on_timeout    = "CONTINUE_DEPLOYMENT"
      wait_time_in_minutes = 5
    }

    green_fleet_provisioning_option {
      action = "DISCOVER_EXISTING"
    }

    terminate_blue_instances_on_deployment_success {
      action                           = "TERMINATE"
      termination_wait_time_in_minutes = 5
    }
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }

  load_balancer_info {
    target_group_pair_info {
      prod_traffic_route {
        listener_arns = [aws_lb_listener.prequal_https.arn]
      }

      target_group {
        name = aws_lb_target_group.prequal_tg_blue.name
      }

      target_group {
        name = aws_lb_target_group.prequal_tg_green.name
      }
    }
  }

  ecs_service {
    cluster_name = aws_ecs_cluster.prequal_cluster.name
    service_name = aws_ecs_service.prequal_service.name
  }

  tags = {
    Environment = "Production"
  }
}

# Deployment Group for Staging
resource "aws_codedeploy_deployment_group" "staging" {
  app_name               = aws_codedeploy_app.prequal_staging.name
  deployment_group_name  = "staging-deployment-group"
  service_role_arn       = aws_iam_role.codedeploy_role.arn
  deployment_config_name = "CodeDeployDefault.ECSAllAtOnce"

  deployment_style {
    deployment_option = "WITH_TRAFFIC_CONTROL"
    deployment_type   = "BLUE_GREEN"
  }

  blue_green_deployment_config {
    deployment_ready_option {
      action_on_timeout    = "CONTINUE_DEPLOYMENT"
      wait_time_in_minutes = 3
    }

    green_fleet_provisioning_option {
      action = "DISCOVER_EXISTING"
    }

    terminate_blue_instances_on_deployment_success {
      action                           = "TERMINATE"
      termination_wait_time_in_minutes = 3
    }
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE"]
  }

  load_balancer_info {
    target_group_pair_info {
      prod_traffic_route {
        listener_arns = [aws_lb_listener.staging_https.arn]
      }

      target_group {
        name = aws_lb_target_group.prequal_tg_staging_blue.name
      }

      target_group {
        name = aws_lb_target_group.prequal_tg_staging_green.name
      }
    }
  }

  ecs_service {
    cluster_name = aws_ecs_cluster.prequal_cluster_staging.name
    service_name = aws_ecs_service.prequal_service_staging.name
  }

  tags = {
    Environment = "Staging"
  }
}

# IAM Role for CodeDeploy
resource "aws_iam_role" "codedeploy_role" {
  name = "prequal-codedeploy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "codedeploy.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "codedeploy_role_policy" {
  role       = aws_iam_role.codedeploy_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSCodeDeployRoleForECS"
}

resource "aws_iam_role_policy_attachment" "codedeploy_ecs_policy" {
  role       = aws_iam_role.codedeploy_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonECS_FullAccess"
}

# Additional target groups for blue-green deployments
resource "aws_lb_target_group" "prequal_tg_blue" {
  name     = "prequal-tg-blue"
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
    Name = "prequal-tg-blue"
  }
}

resource "aws_lb_target_group" "prequal_tg_green" {
  name     = "prequal-tg-green"
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
    Name = "prequal-tg-green"
  }
}

resource "aws_lb_target_group" "prequal_tg_staging_blue" {
  name     = "prequal-staging-tg-blue"
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
    Name = "prequal-staging-tg-blue"
  }
}

resource "aws_lb_target_group" "prequal_tg_staging_green" {
  name     = "prequal-staging-tg-green"
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
    Name = "prequal-staging-tg-green"
  }
}

# Lambda functions for deployment hooks
resource "aws_lambda_function" "after_allow_test_traffic" {
  filename         = "codedeploy-hooks/after_allow_test_traffic.zip"
  function_name    = "prequal-after-allow-test-traffic"
  role             = aws_iam_role.lambda_hook_role.arn
  handler          = "after_allow_test_traffic.lambda_handler"
  source_code_hash = filebase64sha256("codedeploy-hooks/after_allow_test_traffic.zip")
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT = "production"
      LOG_LEVEL   = "INFO"
    }
  }

  tags = {
    Name = "prequal-deployment-hook"
  }
}

resource "aws_lambda_function" "before_allow_traffic" {
  filename         = "codedeploy-hooks/before_allow_traffic.zip"
  function_name    = "prequal-before-allow-traffic"
  role             = aws_iam_role.lambda_hook_role.arn
  handler          = "before_allow_traffic.lambda_handler"
  source_code_hash = filebase64sha256("codedeploy-hooks/before_allow_traffic.zip")
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 128

  environment {
    variables = {
      ENVIRONMENT = "production"
      LOG_LEVEL   = "INFO"
    }
  }

  tags = {
    Name = "prequal-deployment-hook"
  }
}

# IAM Role for Lambda hooks
resource "aws_iam_role" "lambda_hook_role" {
  name = "prequal-lambda-hook-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_hook_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_hook_permissions" {
  name = "prequal-lambda-hook-permissions"
  role = aws_iam_role.lambda_hook_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeServices",
          "ecs:DescribeTasks",
          "cloudwatch:GetMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch alarms for automatic rollback
resource "aws_cloudwatch_metric_alarm" "deployment_error_rate" {
  alarm_name          = "prequal-deployment-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 50
  alarm_description   = "Alarm for high error rate during deployment - triggers rollback"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
  }

  tags = {
    Name = "prequal-deployment-rollback-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "deployment_latency" {
  alarm_name          = "prequal-deployment-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "p95"
  threshold           = 5
  alarm_description   = "Alarm for high latency during deployment - triggers rollback"
  alarm_actions       = [aws_sns_topic.prequal_alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.prequal_alb.arn_suffix
  }

  tags = {
    Name = "prequal-deployment-latency-alarm"
  }
}