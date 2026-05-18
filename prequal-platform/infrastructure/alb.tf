# ALB (Application Load Balancer)

resource "aws_lb" "prequal" {
  name               = "prequal-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  
  enable_deletion_protection = true
  
  tags = {
    Name = "prequal-alb"
  }
}

# Security group for ALB
resource "aws_security_group" "alb" {
  name        = "prequal-alb"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.prequal.id
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from anywhere"
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from anywhere"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "prequal-alb"
  }
}

# Target group for backend
resource "aws_lb_target_group" "backend" {
  name        = "prequal-backend"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.prequal.id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 3
  }
}

# Target group for frontend
resource "aws_lb_target_group" "frontend" {
  name        = "prequal-frontend"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.prequal.id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 3
  }
}

# Listener for HTTP (port 80)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.prequal.arn
  port              = 80
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

# Listener for HTTPS (port 443)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.prequal.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.prequal.arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# Route /api/* to backend
resource "aws_lb_listener_rule" "backend_api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
  
  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# ACM Certificate for HTTPS
resource "aws_acm_certificate" "prequal" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  
  tags = {
    Name = "prequal-certificate"
  }
}

# Certificate validation
resource "aws_acm_certificate_validation" "prequal" {
  certificate_arn = aws_acm_certificate.prequal.arn
  
  validation_record_fqdns = [
    aws_route53_record.certificate_validation.fqdn
  ]
}

# Route53 Record for certificate validation
resource "aws_route53_record" "certificate_validation" {
  allow_overwrite = true
  name            = tolist(aws_acm_certificate.prequal.domain_validation_options)[0].resource_record_name
  type            = tolist(aws_acm_certificate.prequal.domain_validation_options)[0].resource_record_type
  zone_id         = data.aws_route53_zone.main.zone_id
  records         = [tolist(aws_acm_certificate.prequal.domain_validation_options)[0].resource_record_value]
  ttl             = 60
}

# Route53 Zone (domain)
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

# Route53 Record for ALB
resource "aws_route53_record" "alb" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  
  alias {
    name                   = aws_lb.prequal.dns_name
    zone_id                = aws_lb.prequal.zone_id
    evaluate_target_health = true
  }
}

# ECS Service for Backend
resource "aws_ecs_service" "backend" {
  name                 = "prequal-backend-service"
  cluster              = aws_ecs_cluster.prequal.id
  task_definition      = aws_ecs_task_definition.backend.arn
  desired_count        = 2
  launch_type          = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }
  
  depends_on = [
    aws_lb_listener.https,
    aws_iam_role_policy_attachment.ecs_execution
  ]
}

# ECS Service for Frontend
resource "aws_ecs_service" "frontend" {
  name                 = "prequal-frontend-service"
  cluster              = aws_ecs_cluster.prequal.id
  task_definition      = aws_ecs_task_definition.frontend.arn
  desired_count        = 2
  launch_type          = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }
  
  depends_on = [
    aws_lb_listener.https,
    aws_iam_role_policy_attachment.ecs_execution
  ]
}
