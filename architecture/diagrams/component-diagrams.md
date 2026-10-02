# Prequal Microservice Architecture - Component Diagrams

## 1. System Context Diagram

```mermaid
graph TB
    subgraph "External Systems"
        TX["Texas TDLR API"]
        OSHA["OSHA Data API"]
        SILTRA["SILTRA API"]
    end

    subgraph "Prequal Platform"
        GW["API Gateway<br/>(Kong/FastAPI)"]
        
        subgraph "Core Services"
            ID["identity-service<br/>:8001"]
            ORG["organization-service<br/>:8002"]
            SUBC["subcontractor-service<br/>:8003"]
            COMP["compliance-service<br/>:8004"]
            INT["integration-service<br/>:8005"]
            ANAL["analytics-service<br/>:8006"]
            NOTIF["notification-service<br/>:8007"]
            FEED["feedback-service<br/>:8008"]
        end

        subgraph "Data Layer"
            DB_ID[("identity-db<br/>PostgreSQL")]
            DB_ORG[("organization-db<br/>PostgreSQL")]
            DB_SUBC[("subcontractor-db<br/>PostgreSQL")]
            DB_COMP[("compliance-db<br/>PostgreSQL")]
            DB_INT[("integration-db<br/>PostgreSQL")]
            DB_ANAL[("analytics-db<br/>PostgreSQL")]
            DB_NOTIF[("notification-db<br/>PostgreSQL")]
            DB_FEED[("feedback-db<br/>PostgreSQL")]
            REDIS[("Redis<br/>Sessions/Cache")]
            S3["S3<br/>Documents"]
        end

        subgraph "Message Broker"
            MQ["RabbitMQ"]
        end
    end

    subgraph "Clients"
        WEB["React Frontend"]
        MOBILE["Mobile App"]
    end

    WEB --> GW
    MOBILE --> GW
    GW --> ID
    GW --> ORG
    GW --> SUBC
    GW --> COMP
    GW --> FEED

    ID <--> DB_ID
    ORG <--> DB_ORG
    SUBC <--> DB_SUBC
    COMP <--> DB_COMP
    INT <--> DB_INT
    ANAL <--> DB_ANAL
    NOTIF <--> DB_NOTIF
    FEED <--> DB_FEED

    INT <--> MQ
    ANAL <--> MQ
    NOTIF <--> MQ
    COMP <--> MQ

    ID --> REDIS
    SUBC --> S3

    INT --> TX
    INT --> OSHA
    INT --> SILTRA
```

## 2. Service Interaction Diagram (Async Events)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant GW as API Gateway
    participant SUBC as Subcontractor Service
    participant COMP as Compliance Service
    participant INT as Integration Service
    participant MQ as RabbitMQ
    participant ANAL as Analytics Service
    participant NOTIF as Notification Service

    Note over FE,INT: Certification Upload Flow

    FE->>GW: POST /subcontractors/{id}/certifications
    GW->>SUBC: Create certification
    SUBC->>DB_SUBC: Save certification
    SUBC-->>GW: 201 Created
    GW-->>FE: 201 Created

    SUBC->>MQ: Publish CertificationUploaded event
    MQ->>COMP: Deliver CertificationUploaded
    COMP->>COMP: Queue verification check
    MQ->>ANAL: Deliver CertificationUploaded
    ANAL->>DB_ANAL: Store event
    MQ->>NOTIF: Deliver CertificationUploaded
    NOTIF->>NOTIF: Check expiration (90-day rule)

    Note over FE,INT: Credential Sync Flow

    INT->>TX: Poll TDLR API
    INT->>INT: Parse & validate
    INT->>MQ: Publish CredentialsSynced event
    MQ->>COMP: Deliver CredentialsSynced
    COMP->>DB_COMP: Upsert state_credential_records
    COMP->>MQ: Publish ComplianceStatusChanged
    MQ->>NOTIF: Deliver ComplianceStatusChanged
    NOTIF->>NOTIF: Alert if non-compliant
```

## 3. Service Dependency Graph

```mermaid
graph LR
    GW["API Gateway"] --> ID["identity-service"]
    GW["API Gateway"] --> ORG["organization-service"]
    GW["API Gateway"] --> SUBC["subcontractor-service"]
    GW["API Gateway"] --> COMP["compliance-service"]
    GW["API Gateway"] --> FEED["feedback-service"]

    ID --> DB_ID[("PostgreSQL")]
    ORG --> DB_ORG[("PostgreSQL")]
    SUBC --> DB_SUBC[("PostgreSQL")]
    SUBC --> S3[(S3)]
    COMP --> DB_COMP[("PostgreSQL")]
    FEED --> DB_FEED[("PostgreSQL")]

    COMP --> SUBC
    NOTIF --> SUBC
    NOTIF --> COMP
    NOTIF --> ORG

    INT["integration-service"] --> MQ["RabbitMQ"]
    ANAL["analytics-service"] --> MQ
    NOTIF["notification-service"] --> MQ

    INT --> COMP
    ANAL --> ORG

    subgraph "Infrastructure"
        MQ
        REDIS["Redis"]
    end

    ID --> REDIS
    GW --> REDIS
```

## 4. Deployment Topology

```mermaid
graph TB
    subgraph "Kubernetes Cluster (EKS)"
        subgraph "Namespaces"
            subgraph "ingress-nginx"
                ING["Ingress Controller"]
            end
            subgraph "services"
                ID_POD["identity-service<br/>Deployment: 2 pods"]
                ORG_POD["organization-service<br/>Deployment: 2 pods"]
                SUBC_POD["subcontractor-service<br/>Deployment: 3 pods"]
                COMP_POD["compliance-service<br/>Deployment: 2 pods"]
                INT_POD["integration-service<br/>Deployment: 1 pod"]
                ANAL_POD["analytics-service<br/>Deployment: 2 pods"]
                NOTIF_POD["notification-service<br/>Deployment: 1 pod"]
                FEED_POD["feedback-service<br/>Deployment: 1 pod"]
            end
            subgraph "data"
                PG["PostgreSQL<br/>RDS (Multi-AZ)"]
                REDIS_POD["Redis<br/>ElastiCache"]
                MQ_POD["RabbitMQ<br/>Cluster"]
                S3_BUCKET["S3 Bucket"]
            end
        end
    end

    ING --> SUBC_POD
    ING --> ID_POD
    ING --> ORG_POD
    ING --> COMP_POD
    ING --> FEED_POD

    ID_POD --> PG
    SUBC_POD --> PG
    SUBC_POD --> S3_BUCKET
    COMP_POD --> PG
    NOTIF_POD --> REDIS_POD
    ANAL_POD --> MQ_POD
    INT_POD --> MQ_POD
```

## 5. Database Schema Ownership

```mermaid
erDiagram
    ORGANIZATION ||--o{ USER : "has"
    ORGANIZATION ||--o{ SUBCONTRACTOR : "manages"
    ORGANIZATION ||--o{ CERTIFICATION : "owns"
    ORGANIZATION ||--o{ FEEDBACK : "receives"
    ORGANIZATION ||--o{ ANALYTICS_EVENT : "generates"

    USER ||--o{ USER_SESSION : "has"
    USER ||--o{ FEEDBACK : "submits"

    SUBCONTRACTOR ||--o{ CERTIFICATION : "holds"
    SUBCONTRACTOR ||--o{ STATE_CREDENTIAL : "verified_by"

    CERTIFICATION {
        int id PK
        int subcontractor_id FK
        int organization_id FK
        string cert_type
        string cert_number
        datetime issued_date
        datetime expiration_date
        string status
        string file_path
    }

    STATE_CREDENTIAL {
        int id PK
        string state_code
        string credential_number
        string credential_type
        string status
        int subcontractor_id FK
        datetime last_synced_at
    }

    SYNC_RUN_LOG {
        int id PK
        string job_name
        string status
        datetime started_at
        int records_processed
    }
```

## Legend

| Symbol | Meaning |
|--------|---------|
| → | Synchronous REST call |
| ⇒ | Async message (MQ) |
| -- | Database relationship |
| subgraph | Grouped components |
| POD | Kubernetes Deployment |