# CI/CD Pipeline Setup

This document describes the CI/CD pipeline implementation for the Prequal compliance tracking platform.

## Overview

The CI/CD pipeline is implemented using GitHub Actions and deploys the application to AWS ECS Fargate.

## Pipeline Stages

### 1. Test Stage
- Runs on every push and pull request to `main` and `develop` branches
- Sets up Node.js 18 environment
- Installs dependencies using `npm ci`
- Runs unit tests with `npm test`
- Performs linting with `npm run lint`
- Runs TypeScript type checking with `npm run typecheck`

### 2. Build Stage
- Depends on successful test completion
- Builds the application with `npm run build`
- Builds Docker image tagged with the Git commit SHA
- Pushes Docker image to Amazon ECR repository

### 3. Deploy Stage
- Runs only on `main` branch
- Depends on successful build completion
- Updates ECS task definition with new image
- Deploys to ECS service with zero-downtime rolling update
- Waits for service stability before completing
- Optionally runs database migrations

## Required GitHub Secrets

The following secrets must be configured in the GitHub repository:

| Secret Name | Description |
|-------------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM user access key ID |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM user secret access key |

## Required AWS Resources

- ECR Repository: `prequal-platform`
- ECS Cluster: `prequal-cluster`
- ECS Service: `prequal-service`
- ECS Task Definition: `prequal-task`
- IAM Role: `prequal-ecs-task-execution-role`

## Environment Variables

The following environment variables are configured in the workflow:

| Variable | Value |
|----------|-------|
| `AWS_REGION` | `us-east-1` |
| `ECR_REPOSITORY` | `prequal-platform` |
| `ECS_CLUSTER` | `prequal-cluster` |
| `ECS_SERVICE` | `prequal-service` |
| `ECS_TASK_DEFINITION` | `prequal-task` |
| `CONTAINER_NAME` | `prequal-app` |

## Deployment Flow

```
Push to main
    │
    ▼
┌─────────────────┐
│  Test Stage     │
│  - npm ci       │
│  - npm test     │
│  - npm lint     │
│  - typecheck    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build Stage    │
│  - npm build    │
│  - Docker build │
│  - Push to ECR  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deploy Stage    │
│  - Update task  │
│  - Deploy to ECS│
│  - Wait stable  │
└─────────────────┘
```

## Troubleshooting

### Deployment Fails

1. Check AWS credentials are valid
2. Verify ECS service and cluster exist
3. Ensure IAM role has ECR and ECS permissions
4. Review CloudWatch logs for the ECS task

### Image Not Updating

1. Verify ECR repository name matches
2. Check the image tag in the task definition
3. Ensure the IAM role can pull from ECR

### Service Unstable

1. Check application health check endpoint (`/health`)
2. Review application logs in CloudWatch
3. Verify environment variables are correct
4. Check security group allows traffic from ALB

## Security Best Practices

- Use short-lived AWS credentials via OIDC if possible
- Enable ECR image scanning
- Use private subnets for ECS tasks
- Enable encryption at rest for all data stores
- Regularly rotate AWS credentials
- Use IAM roles with least privilege principle

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS ECS Deploy Action](https://github.com/aws-actions/amazon-ecs-deploy-task-definition)
- [AWS ECR Login Action](https://github.com/aws-actions/amazon-ecr-login)
