# Prequal Platform - AWS Infrastructure
# Terraform configuration for production deployment

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
  
  backend "s3" {
    bucket         = "prequal-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project    = "prequal-platform"
      Environment = "production"
      ManagedBy  = "terraform"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "domain_name" {
  description = "Production domain name"
  type        = string
  default     = "prequal.yourcompany.com"
}

variable "enable_monitoring" {
  description = "Enable CloudWatch monitoring and alerts"
  type        = bool
  default     = true
}

# Random password for database
resource "random_password" "database_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store database password in Secrets Manager
resource "aws_secretsmanager_secret" "database_password" {
  name        = "prequal/${var.environment}/database-password"
  description = "Production database password"
  
  tags = {
    Name = "prequal-database-password"
  }
}

resource "aws_secretsmanager_secret_version" "database_password" {
  secret_id = aws_secretsmanager_secret.database_password.id
  secret_string = jsonencode({
    password = random_password.database_password.result
  })
}

# VPC for isolation
resource "aws_vpc" "prequal" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "prequal-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "prequal" {
  vpc_id = aws_vpc.prequal.id
  
  tags = {
    Name = "prequal-igw"
  }
}

# Public subnets
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.prequal.id
  cidr_block              = cidrsubnet(aws_vpc.prequal.cidr_block, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "prequal-public-${count.index + 1}"
    Type = "public"
  }
}

# Private subnets for RDS and ElastiCache
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.prequal.id
  cidr_block        = cidrsubnet(aws_vpc.prequal.cidr_block, 8, count.index + 11)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {
    Name = "prequal-private-${count.index + 1}"
    Type = "private"
  }
}

# Route table for public subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.prequal.id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.prequal.id
  }
  
  tags = {
    Name = "prequal-public-rt"
  }
}

# Associate public route table with public subnets
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count].id
  route_table_id = aws_route_table.public.id
}

# NAT Gateway for private subnets
resource "aws_eip" "nat" {
  domain = "vpc"
  
  tags = {
    Name = "prequal-nat-eip"
  }
}

resource "aws_nat_gateway" "prequal" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  
  tags = {
    Name = "prequal-nat"
  }
}

# Route table for private subnets
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.prequal.id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.prequal.id
  }
  
  tags = {
    Name = "prequal-private-rt"
  }
}

# Associate private route table with private subnets
resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count].id
  route_table_id = aws_route_table.private.id
}

# Security group for ECS tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "prequal-ecs-tasks"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.prequal.id
  
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "Backend API from VPC"
  }
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "Frontend from VPC"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "prequal-ecs-tasks"
  }
}

# Security group for RDS
resource "aws_security_group" "rds" {
  name        = "prequal-rds"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.prequal.id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "PostgreSQL from ECS tasks"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "prequal-rds"
  }
}

# Security group for ElastiCache Redis
resource "aws_security_group" "redis" {
  name        = "prequal-redis"
  description = "Security group for Redis"
  vpc_id      = aws_vpc.prequal.id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "Redis from ECS tasks"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "prequal-redis"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier           = "prequal-db"
  engine               = "postgres"
  engine_version       = "15"
  instance_class       = "db.t3.medium"
  allocated_storage    = 100
  storage_type         = "gp3"
  storage_encrypted    = true
  
  db_name  = "prequal_prod"
  username = "prequal_admin"
  password = random_password.database_password.result
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.prequal.name
  
  multi_az               = true
  publicly_accessible    = false
  deletion_protection    = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "prequal-final-snapshot"
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"
  
  tags = {
    Name = "prequal-postgres"
  }
}

# DB Subnet Group
resource "aws_db_subnet_group" "prequal" {
  name       = "prequal-db-subnet"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "prequal-db-subnet"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "prequal-redis"
  engine               = "redis"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  
  security_group_ids = [aws_security_group.redis.id]
  subnet_group_name  = aws_elasticache_subnet_group.prequal.name
  
  tags = {
    Name = "prequal-redis"
  }
}

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "prequal" {
  name       = "prequal-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "prequal-redis-subnet"
  }
}

# ECR Repository for Backend
resource "aws_ecr_repository" "backend" {
  name                 = "prequal-platform/backend"
  image_tag_mutability = "IMMUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name = "prequal-backend"
  }
}

# ECR Repository for Frontend
resource "aws_ecr_repository" "frontend" {
  name                 = "prequal-platform/frontend"
  image_tag_mutability = "IMMUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name = "prequal-frontend"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "prequal" {
  name = "prequal-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = {
    Name = "prequal-cluster"
  }
}

# CloudWatch Log Group for Backend
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/prequal-backend"
  retention_in_days = 30
  
  tags = {
    Name = "prequal-backend-logs"
  }
}

# CloudWatch Log Group for Frontend
resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/prequal-frontend"
  retention_in_days = 30
  
  tags = {
    Name = "prequal-frontend-logs"
  }
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.prequal.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.prequal.name
}

output "backend_ecr_repository_url" {
  description = "ECR repository URL for backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_repository_url" {
  description = "ECR repository URL for frontend"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}"
}

output "database_secret_arn" {
  description = "Database password secret ARN"
  value       = aws_secretsmanager_secret.database_password.arn
}
