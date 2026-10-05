# Business Continuity & Disaster Recovery Plan

## 1. Purpose
To ensure that critical business functions can continue during a disaster and that data can be recovered in a timely manner.

## 2. Critical Systems
- Primary Application Infrastructure (AWS/Azure/GCP)
- Database (Production)
- Internal Communication (Slack/Email)

## 3. Backup Strategy
- Database backups are performed daily and stored in a geographically separate region.
- Configuration as Code (Terraform/K8s) is stored in Git for rapid reconstruction.

## 4. Recovery Objectives
- Recovery Time Objective (RTO): 4 hours for critical systems.
- Recovery Point Objective (RPO): 24 hours (last daily backup).

## 5. Recovery Procedures
1. Provision new infrastructure using IaC.
2. Restore latest database backup.
3. Verify connectivity and application health.
4. Update DNS records to point to the new environment.

## 6. Testing
- The DR plan is tested annually through a simulated failure exercise.
