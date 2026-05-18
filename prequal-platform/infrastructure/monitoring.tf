# CloudWatch Alarms and Monitoring

# Alarm for high error rate on backend
resource "aws_cloudwatch_metric_alarm" "backend_errors" {
  alarm_name          = "prequal-backend-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Backend error rate is too high"
  
  dimensions = {
    TargetGroupArn = aws_lb_target_group.backend.arn
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Alarm for high latency
resource "aws_cloudwatch_metric_alarm" "backend_latency" {
  alarm_name          = "prequal-backend-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 5
  alarm_description   = "Backend latency is too high"
  
  dimensions = {
    TargetGroupArn = aws_lb_target_group.backend.arn
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Alarm for ECS task health
resource "aws_cloudwatch_metric_alarm" "ecs_tasks_unhealthy" {
  alarm_name          = "prequal-ecs-tasks-unhealthy"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "ECS tasks are unhealthy"
  
  dimensions = {
    TargetGroupArn = aws_lb_target_group.backend.arn
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Alarm for RDS CPU usage
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "prequal-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU usage is too high"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.identifier
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Alarm for RDS storage
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "prequal-rds-low-storage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 10000000000 # 10GB in bytes
  alarm_description   = "RDS storage is running low"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.identifier
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "prequal-alerts"
  
  tags = {
    Name = "prequal-alerts"
  }
}

# SNS Topic Subscription (email)
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Dashboard for Prequal Platform
resource "aws_cloudwatch_dashboard" "prequal" {
  dashboard_name = "prequal-platform"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        
        properties = {
          title  = "Backend Response Time"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "TargetGroupArn", aws_lb_target_group.backend.arn]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        
        properties = {
          title  = "Backend Error Rate"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "5XXError", "TargetGroupArn", aws_lb_target_group.backend.arn]
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        
        properties = {
          title  = "RDS CPU Utilization"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.postgres.identifier]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        
        properties = {
          title  = "ECS Service Running Tasks"
          region = var.aws_region
          metrics = [
            ["AWS/ECS", "RunningTasks", "ClusterName", aws_ecs_cluster.prequal.name, "ServiceName", aws_ecs_service.backend.name]
          ]
          period = 300
          stat   = "Average"
        }
      }
    ]
  })
}

# Variable for alert email
variable "alert_email" {
  description = "Email address for sending alerts"
  type        = string
  default     = "devops@yourcompany.com"
}
