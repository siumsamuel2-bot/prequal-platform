# CloudWatch Alarms and Monitoring Configuration

## Overview

This document defines CloudWatch alarms for monitoring the Prequal Platform infrastructure on AWS.

## Alarm Categories

### 1. Application Availability

#### API Service Down

```yaml
Alarm Name: prequal-api-service-down
Metric: ECS Service Status
Threshold: < 1.0 (service not at desired capacity)
Period: 2 minutes
Evaluation Periods: 2
Actions:
  - SNS: prequal-alerts-critical
  - Lambda: auto-recovery-function

CloudFormation:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: prequal-api-service-down
    AlarmDescription: "Prequal API service is not at desired capacity"
    MetricName: RunningTasksCount
    Namespace: ECS
    Statistic: Average
    Period: 120
    EvaluationPeriods: 2
    Threshold: 1
    ComparisonOperator: LessThanThreshold
    Dimensions:
      - Name: ClusterName
        Value: prequal-cluster
      - Name: ServiceName
        Value: prequal-service
```

#### High Error Rate

```yaml
Alarm Name: prequal-high-error-rate
Metric: HTTP 5xx errors / Total requests
Threshold: > 5%
Period: 5 minutes
Evaluation Periods: 2

CloudWatch Logs Insight Query:
  fields @timestamp, @message
  | filter @message like "ERROR"
  | stats count() as error_count by bin(5m)
  | filter error_count > 100
```

### 2. Performance

#### High Latency (P95)

```yaml
Alarm Name: prequal-high-latency-p95
Metric: API Gateway P95 Latency
Threshold: > 2000ms
Period: 10 minutes
Evaluation Periods: 2
Actions:
  - SNS: prequal-alerts-warning
```

#### High CPU Usage

```yaml
Alarm Name: prequal-ecs-high-cpu
Metric: ECS CPU Utilization
Threshold: > 80%
Period: 5 minutes
Evaluation Periods: 3
Actions:
  - SNS: prequal-alerts-warning
  - Application Auto Scaling: scale-out

CloudFormation:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: prequal-ecs-high-cpu
    AlarmDescription: "ECS service CPU utilization is high"
    MetricName: CPUUtilization
    Namespace: AWS/ECS
    Statistic: Average
    Period: 300
    EvaluationPeriods: 3
    Threshold: 80
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: ClusterName
        Value: prequal-cluster
      - Name: ServiceName
        Value: prequal-service
```

#### High Memory Usage

```yaml
Alarm Name: prequal-ecs-high-memory
Metric: ECS Memory Utilization
Threshold: > 85%
Period: 5 minutes
Evaluation Periods: 3
Actions:
  - SNS: prequal-alerts-warning
```

### 3. Database (RDS PostgreSQL)

#### Database CPU Usage

```yaml
Alarm Name: prequal-rds-high-cpu
Metric: RDS CPU Utilization
Threshold: > 80%
Period: 5 minutes
Evaluation Periods: 3
Actions:
  - SNS: prequal-alerts-warning

CloudFormation:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: prequal-rds-high-cpu
    MetricName: CPUUtilization
    Namespace: AWS/RDS
    Statistic: Average
    Period: 300
    EvaluationPeriods: 3
    Threshold: 80
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: DBInstanceIdentifier
        Value: prequal-db
```

#### Database Free Storage

```yaml
Alarm Name: prequal-rds-low-storage
Metric: RDS Free Storage Space
Threshold: < 5GB
Period: 5 minutes
Evaluation Periods: 1
Actions:
  - SNS: prequal-alerts-critical

CloudFormation:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: prequal-rds-low-storage
    MetricName: FreeStorageSpace
    Namespace: AWS/RDS
    Statistic: Average
    Period: 300
    EvaluationPeriods: 1
    Threshold: 5368709120  # 5GB in bytes
    ComparisonOperator: LessThanThreshold
    Dimensions:
      - Name: DBInstanceIdentifier
        Value: prequal-db
```

#### Database Connections

```yaml
Alarm Name: prequal-rds-high-connections
Metric: RDS Database Connections
Threshold: > 100
Period: 5 minutes
Evaluation Periods: 2
Actions:
  - SNS: prequal-alerts-warning
```

### 4. Cache (ElastiCache Redis)

#### Redis CPU Usage

```yaml
Alarm Name: prequal-redis-high-cpu
Metric: ElastiCache CPU Utilization
Threshold: > 80%
Period: 5 minutes
Evaluation Periods: 3
Actions:
  - SNS: prequal-alerts-warning
```

#### Redis Memory Usage

```yaml
Alarm Name: prequal-redis-high-memory
Metric: ElastiCache Memory Usage
Threshold: > 85%
Period: 5 minutes
Evaluation Periods: 3
Actions:
  - SNS: prequal-alerts-critical
```

### 5. Load Balancer (ALB)

#### ALB 5xx Errors

```yaml
Alarm Name: prequal-alb-5xx-errors
Metric: ALB HTTP 5xx Errors
Threshold: > 10 errors
Period: 5 minutes
Evaluation Periods: 2
Actions:
  - SNS: prequal-alerts-critical

CloudFormation:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: prequal-alb-5xx-errors
    MetricName: HTTPCode_Target_5XX_Count
    Namespace: AWS/ApplicationELB
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 2
    Threshold: 10
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: LoadBalancer
        Value: app/prequal-alb/xxxxx
```

#### ALB Target Response Time

```yaml
Alarm Name: prequal-alb-high-response-time
Metric: ALB Target Response Time
Threshold: > 2 seconds
Period: 5 minutes
Evaluation Periods: 3
Actions:
  - SNS: prequal-alerts-warning
```

### 6. Security

#### Unusual Network Activity

```yaml
Alarm Name: prequal-unusual-network-traffic
Metric: VPC Flow Logs - Unusual traffic pattern
Threshold: Anomaly detected
Period: 1 hour
Evaluation Periods: 1
Actions:
  - SNS: prequal-alerts-security
  - Lambda: security-automation-function
```

#### Failed Authentication Attempts

```yaml
Alarm Name: prequal-high-auth-failures
Metric: Cognito/Custom - Failed logins
Threshold: > 50 failures in 5 minutes
Period: 5 minutes
Evaluation Periods: 1
Actions:
  - SNS: prequal-alerts-security
```

## SNS Topics

### Topic Configuration

```yaml
# Critical Alerts (immediate notification)
Topic: prequal-alerts-critical
Subscriptions:
  - Protocol: email
    Endpoint: devops@company.com
  - Protocol: sms
    Endpoint: "+1-XXX-XXX-XXXX"
  - Protocol: lambda
    Endpoint: pagerduty-integration

# Warning Alerts (batched notifications)
Topic: prequal-alerts-warning
Subscriptions:
  - Protocol: email
    Endpoint: devops@company.com
  - Protocol: slack
    Endpoint: "#alerts-warning"

# Security Alerts
Topic: prequal-alerts-security
Subscriptions:
  - Protocol: email
    Endpoint: security@company.com
  - Protocol: sms
    Endpoint: "+1-XXX-XXX-XXXX"
```

## Dashboard Configuration

### Prequal Platform Dashboard

```json
{
  "dashboardName": "Prequal-Platform",
  "widgets": [
    {
      "type": "metric",
      "title": "API Service Status",
      "metrics": [
        ["ECS", "RunningTasksCount", "ClusterName", "prequal-cluster", "ServiceName", "prequal-service"]
      ],
      "period": 60,
      "stat": "Average"
    },
    {
      "type": "metric",
      "title": "Database CPU",
      "metrics": [
        ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "prequal-db"]
      ],
      "period": 60,
      "stat": "Average"
    },
    {
      "type": "metric",
      "title": "ALB Request Count",
      "metrics": [
        ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", "prequal-alb"]
      ],
      "period": 60,
      "stat": "Sum"
    },
    {
      "type": "metric",
      "title": "Error Rate",
      "metrics": [
        ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", "prequal-alb"]
      ],
      "period": 300,
      "stat": "Sum"
    }
  ]
}
```

## Terraform Configuration

```hcl
# alarms.tf

# API Service Down Alarm
resource "aws_cloudwatch_metric_alarm" "api_service_down" {
  alarm_name          = "prequal-api-service-down"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTasksCount"
  namespace           = "ECS"
  period              = 120
  statistic           = "AVERAGE"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.critical.arn]
  
  dimensions = {
    ClusterName = "prequal-cluster"
    ServiceName = "prequal-service"
  }
}

# RDS CPU High Alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "prequal-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "AVERAGE"
  threshold           = 80
  alarm_actions       = [aws_sns_topic.warning.arn]
  
  dimensions = {
    DBInstanceIdentifier = "prequal-db"
  }
}

# ECS CPU High Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "prequal-ecs-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "AVERAGE"
  threshold           = 80
  alarm_actions       = [aws_sns_topic.warning.arn]
  
  dimensions = {
    ClusterName = "prequal-cluster"
    ServiceName = "prequal-service"
  }
}
```

## Alert Response Runbook

### Critical Alerts Response

1. **Acknowledge alert** within 5 minutes
2. **Check dashboard**: https://console.aws.amazon.com/cloudwatch
3. **Check application logs**: https://console.aws.amazon.com/cloudwatch/logs
4. **Check Sentry**: https://sentry.io/
5. **Follow escalation** if not resolved in 15 minutes

### Warning Alerts Response

1. **Review** within 1 hour
2. **Investigate trend** - is this increasing?
3. **Plan capacity** if resource-related
4. **Document** if recurring

---

**Last Updated**: 2026-05-25
**Maintained By**: DevOps Engineer
