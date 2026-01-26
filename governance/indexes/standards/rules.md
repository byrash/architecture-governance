# Architectural Standards

> Source: Confluence - Architectural Standards
> Last Updated: 2026-01-24

---

## Documentation Standards

### 1. API Versioning

**Severity**: High | **Required**: Yes

All APIs must include version information in the path or header.

```mermaid
flowchart LR
    Client --> |/api/v1/users| API
    Client --> |/api/v2/users| API
```

**Expected Format**:
- URL Path: `/api/v1/resource`
- Header: `Accept-Version: v1`

**Keywords**: `v1`, `v2`, `version`, `API version`, `/api/v`

---

### 2. Architecture Overview

**Severity**: Medium | **Required**: Yes

Documents must include an architecture overview section with:
- System context diagram
- Component descriptions
- Data flow

```mermaid
flowchart TB
    User[User] --> System[Our System]
    System --> ExtAPI[External API]
    System --> DB[(Database)]
```

**Keywords**: `overview`, `diagram`, `description`, `purpose`, `scope`, `context`

---

### 3. Error Handling Strategy

**Severity**: High | **Required**: Yes

Error handling approach must be documented including:
- Error response format
- Error codes
- Retry strategies
- Fallback behavior

```mermaid
flowchart TD
    Request --> Validate{Valid?}
    Validate --> |Yes| Process
    Validate --> |No| Error400[400 Bad Request]
    Process --> Success{Success?}
    Success --> |Yes| Response200[200 OK]
    Success --> |No| Error500[500 Server Error]
```

**Keywords**: `error`, `exception`, `handling`, `retry`, `fallback`, `error code`

---

## Naming Conventions

### 4. Component Naming

**Severity**: Medium | **Required**: Yes

Components should follow standard naming suffixes:

| Type | Suffix | Example |
|------|--------|---------|
| Services | `*Service` | `UserService` |
| Controllers | `*Controller` | `UserController` |
| Repositories | `*Repository` | `UserRepository` |
| Handlers | `*Handler` | `EventHandler` |

**Keywords**: `Service`, `Controller`, `Repository`, `Handler`, `Manager`

---

### 5. Health Check Endpoints

**Severity**: Medium | **Required**: Yes

All services must expose health check endpoints.

```mermaid
flowchart LR
    LB[Load Balancer] --> |/health| Service
    K8s[Kubernetes] --> |/healthz| Service
```

**Expected**: `/health`, `/healthz`, liveness probe, readiness probe

**Keywords**: `health`, `health check`, `liveness`, `readiness`, `status`

---

## Configuration Standards

### 6. Externalized Configuration

**Severity**: Medium | **Required**: Yes

Configuration must be externalized, not hardcoded.

```mermaid
flowchart LR
    App[Application] --> Config[Config Service]
    Config --> Env[Environment Vars]
    Config --> Vault[Secrets Vault]
```

**Keywords**: `configuration`, `config`, `environment`, `settings`, `env var`

---

### 7. Logging Standards

**Severity**: Medium | **Required**: Yes

Logging approach must be documented.

```mermaid
flowchart LR
    App[App Logs] --> Collector[Log Collector]
    Collector --> Dashboard[Monitoring]
```

**Keywords**: `logging`, `log`, `audit`, `trace`, `monitoring`, `observability`

---

### 8. Database Schema Documentation

**Severity**: Low | **Required**: No

Database schema or ERD should be included.

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
```

**Keywords**: `schema`, `database`, `table`, `entity`, `ERD`, `data model`

---

## Structured Rules

```json
{
  "category": "architectural-standards",
  "rules": [
    {"id": "STD-001", "name": "API Versioning", "severity": "high", "required": true, "keywords": ["v1", "v2", "version", "API version"]},
    {"id": "STD-002", "name": "Architecture Overview", "severity": "medium", "required": true, "keywords": ["overview", "diagram", "description", "context"]},
    {"id": "STD-003", "name": "Error Handling", "severity": "high", "required": true, "keywords": ["error", "exception", "handling", "retry", "fallback"]},
    {"id": "STD-004", "name": "Component Naming", "severity": "medium", "required": true, "keywords": ["Service", "Controller", "Repository", "Handler"]},
    {"id": "STD-005", "name": "Health Check Endpoints", "severity": "medium", "required": true, "keywords": ["health", "liveness", "readiness"]},
    {"id": "STD-006", "name": "Externalized Configuration", "severity": "medium", "required": true, "keywords": ["configuration", "config", "environment"]},
    {"id": "STD-007", "name": "Logging Standards", "severity": "medium", "required": true, "keywords": ["logging", "log", "monitoring", "observability"]},
    {"id": "STD-008", "name": "Database Schema", "severity": "low", "required": false, "keywords": ["schema", "database", "ERD", "data model"]}
  ]
}
```
