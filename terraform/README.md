# Terraform Infrastructure for Prequal Platform

This directory contains Terraform configuration for deploying the Prequal compliance tracking platform on AWS.

## Architecture

The infrastructure includes:
- **VPC** with public and private subnets across multiple availability zones
- **ECS Fargate** cluster for containerized application deployment
- **Application Load Balancer** for traffic distribution
- **ECR Repository** for Docker image storage
- **RDS PostgreSQL** for persistent data storage
- **ElastiCache Redis** for caching
- **CloudWatch Logs** for application logging

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- AWS account with ECS, ECR, RDS, and ElastiCache permissions

## Setup

1. Copy the example variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` with your AWS account ID and secure password

3. Initialize Terraform:
   ```bash
   terraform init
   ```

4. Plan the deployment:
   ```bash
   terraform plan
   ```

5. Apply the configuration:
   ```bash
   terraform apply
   ```

## CI/CD Integration

The infrastructure is designed to work with the GitHub Actions CI/CD pipeline defined in `.github/workflows/ci-cd.yml`.

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID` - AWS access key for deployments
- `AWS_SECRET_ACCESS_KEY` - AWS secret key for deployments

## Outputs

After deployment, the following outputs are available:
- `alb_dns_name` - DNS name of the Application Load Balancer
- `db_endpoint` - RDS PostgreSQL endpoint
- `redis_endpoint` - ElastiCache Redis endpoint
- `ecr_repository_url` - ECR repository URL for Docker images

## Security Notes

- Never commit `terraform.tfvars` with real passwords to version control
- Use AWS Secrets Manager or Parameter Store for production credentials
- Enable encryption at rest for RDS and ElastiCache
- Review and restrict security group rules for production
