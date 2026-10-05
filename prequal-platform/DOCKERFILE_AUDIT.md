# Dockerfile Layer Optimization Audit

**Issue:** MID-247  
**Date:** 2026-06-22  
**Audited by:** DevOps Engineer

## Executive Summary

Audited 6 Dockerfiles for layer optimization opportunities. Found several areas for improvement:

- **Critical:** 2 Dockerfiles have separate RUN commands for apt-get that should be combined
- **High:** 3 Dockerfiles can reduce layers by combining cleanup with installation
- **Medium:** 1 Dockerfile missing `.dockerignore` optimization
- **Good:** Multi-stage builds already implemented across all files

---

## Detailed Findings

### 1. `Dockerfile` (Node.js Main) - **GOOD** ✅

**Current layers:** ~11 layers  
**Status:** Well optimized

**Strengths:**
- Proper multi-stage build
- Good layer caching (package*.json copied first)
- Non-root user implemented
- Clean separation of build and production stages

**No changes needed.**

---

### 2. `Dockerfile.api` (FastAPI) - **NEEDS OPTIMIZATION** ⚠️

**Current layers:** ~14 layers  
**Issues:**

1. **Separate RUN commands for apt-get install and cleanup** (lines 10-13, 25-28)
   - Each creates a separate layer
   - Cleanup in separate layer doesn't reduce image size

**Recommended fix:**
```dockerfile
# Combine into single RUN command
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Estimated savings:** ~50-100MB per stage

---

### 3. `Dockerfile.backend` - **NEEDS OPTIMIZATION** ⚠️

**Current layers:** ~16 layers  
**Issues:**

1. **Separate RUN commands for apt-get** (lines 10-13, 31-34)
   - Same issue as Dockerfile.api

2. **Multiple pip commands that could be combined** (lines 19-23)
   - `RUN python -m venv /opt/venv`
   - `ENV PATH="/opt/venv/bin:$PATH"`
   - `RUN pip install --no-cache-dir --upgrade pip && \`
   - Could combine venv creation with pip installs

**Recommended fix:**
```dockerfile
# Combine apt-get commands
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Keep venv creation separate but combine pip commands (already done)
```

---

### 4. `Dockerfile.frontend` - **GOOD** ✅

**Current layers:** ~12 layers  
**Status:** Well optimized

**Strengths:**
- Proper multi-stage build
- Good layer caching
- Security updates applied
- Non-root user (nginx) implemented
- Health check present

**No changes needed.**

---

### 5. `Dockerfile.backend.prod` - **NEEDS OPTIMIZATION** ⚠️

**Current layers:** ~17 layers  
**Issues:**

1. **Apt-get cleanup on separate line** (lines 13-14, 37-38)
   - `&& rm -rf /var/lib/apt/lists/* \`
   - `&& apt-get clean`
   - Should be on same logical command but whitespace creates confusion

2. **COPY commands not grouped** (lines 45-49)
   - 5 separate COPY commands with same `--chown` flag
   - Could be combined for fewer layers

**Recommended fix:**
```dockerfile
# Group COPY commands
COPY --chown=appuser:appgroup \
    requirements.txt \
    alembic.ini \
    ./
COPY --chown=appuser:appgroup \
    app/ ./app/
COPY --chown=appuser:appgroup \
    api/ ./api/
COPY --chown=appuser:appgroup \
    alembic/ ./alembic/
```

---

### 6. `Dockerfile.frontend.prod` - **GOOD** ✅

**Current layers:** ~12 layers  
**Status:** Well optimized

**Strengths:**
- Proper multi-stage build
- Good layer caching
- Security updates with cleanup
- Non-root user implemented
- Health check present

**No changes needed.**

---

## Optimization Priority Matrix

| Dockerfile | Priority | Estimated Savings | Risk |
|------------|----------|-------------------|------|
| Dockerfile.api | High | 50-100MB | Low |
| Dockerfile.backend | High | 50-100MB | Low |
| Dockerfile.backend.prod | Medium | 30-50MB | Low |
| Dockerfile | None | - | - |
| Dockerfile.frontend | None | - | - |
| Dockerfile.frontend.prod | None | - | - |

---

## Recommended Actions

### Immediate (High Priority)

1. **Fix `Dockerfile.api`** - Combine apt-get RUN commands
2. **Fix `Dockerfile.backend`** - Combine apt-get RUN commands

### Follow-up (Medium Priority)

3. **Optimize `Dockerfile.backend.prod`** - Group COPY commands
4. **Add `.dockerignore`** - Ensure all Dockerfiles have proper ignore files

### Best Practices Already Implemented ✅

- Multi-stage builds on all Dockerfiles
- Non-root users where applicable
- Health checks on production images
- Proper layer caching (package files first)
- `--no-cache-dir` for pip and npm
- `--no-install-recommends` for apt-get

---

## Layer Count Summary

| Dockerfile | Current Layers | Optimized Target |
|------------|---------------|------------------|
| Dockerfile | 11 | 11 ✅ |
| Dockerfile.api | 14 | 12 |
| Dockerfile.backend | 16 | 14 |
| Dockerfile.frontend | 12 | 12 ✅ |
| Dockerfile.backend.prod | 17 | 15 |
| Dockerfile.frontend.prod | 12 | 12 ✅ |

**Total potential reduction:** 6 layers across all Dockerfiles  
**Estimated total size savings:** 130-250MB

---

## Next Steps

1. Create optimized versions of the 3 flagged Dockerfiles
2. Test builds to ensure functionality unchanged
3. Measure actual size reduction
4. Update CI/CD pipeline if needed