terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
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

# Listener
resource "aws_lb_listener" "prequal_http" {
  load_balancer_arn = aws_lb.prequal_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prequal_tg.arn
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

# RDS Database
resource "aws_db_subnet_group" "prequal_db_subnet_group" {
  name       = "prequal-db-subnet-group"
  subnet_ids = aws_subnet.prequal_private_subnets[*].id

  tags = {
    Name = "prequal-db-subnet-group"
  }
}

resource "aws_db_instance" "prequal_db" {
  identifier         = "prequal-db"
  engine             = "postgres"
  engine_version     = "15.4"
  instance_class     = "db.t3.micro"
  allocated_storage  = 20
  name               = "prequal"
  username           = "postgres"
  password           = var.db_password
  skip_final_snapshot = true
  vpc_security_group_ids = [aws_security_group.prequal_ecs_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.prequal_db_subnet_group.name

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
  replication_group_id          = "prequal-redis"
  description                   = "Redis cluster for Prequal platform"
  engine                        = "redis"
  node_type                     = "cache.t3.micro"
  number_cache_clusters         = 1
  automatic_failover_enabled    = false
  subnet_group_name             = aws_elasticache_subnet_group.prequal_redis_subnet_group.name
  security_group_ids            = [aws_security_group.prequal_ecs_sg.id]
  maintenance_window            = "sun:05:00-sun:06:00"
  snapshot_retention_limit      = 1
  snapshot_window               = "05:00-06:00"

  tags = {
    Name = "prequal-redis"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "prequal_task" {
  family                   = "prequal-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name      = "prequal-app"
    image     = "${aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/prequal-platform:latest"
    portMappings = [{
      containerPort = 3000
      hostPort      = 3000
      protocol      = "tcp"
    }]
    environment = [
      { name = "NODE_ENV", value = "production" },
      { name = "DATABASE_URL", value = "postgresql://${aws_db_instance.prequal_db.username}:${var.db_password}@${aws_db_instance.prequal_db.address}:${aws_db_instance.prequal_db.port}/${aws_db_instance.prequal_db.name}" },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.prequal_redis.primary_end_point_address}:6379" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/prequal-app"
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
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
    aws_lb_listener.prequal_http
  ]
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