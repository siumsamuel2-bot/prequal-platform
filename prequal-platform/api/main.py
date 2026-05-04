from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import jwt
import datetime
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(title="Prequal Compliance Platform API", version="1.0.0")
app.state.limiter = limiter

# Add CORS middleware

# Rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)

# Pydantic models for request/response validation
class Subcontractor(BaseModel):
    id: Optional[str] = None
    company_name: str
    contact_name: str
    email: str
    phone: str
    address: str

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "54EC409A2CC6B37C639C332264284D9A89CC5546B2022CA3A910178A3A202C53")
ALGORITHM = "HS256"

# Authentication endpoints
@app.post("/api/auth/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, login_request: LoginRequest):
    # In production, verify credentials against database
    # This is a placeholder implementation
    if login_request.username == "admin" and login_request.password == "password":
        access_token = create_access_token(data={"sub": login_request.username})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Subcontractor endpoints
@app.get("/api/subcontractors")
async def get_subcontractors():
    # Placeholder implementation - in production, query database
    return [
        {"id": "1", "company_name": "ABC Construction", "contact_name": "John Doe", "email": "john@abc.com", "phone": "555-1234", "address": "123 Main St"},
        {"id": "2", "company_name": "XYZ Contractors", "contact_name": "Jane Smith", "email": "jane@xyz.com", "phone": "555-5678", "address": "456 Oak Ave"}
    ]

@app.get("/api/subcontractors/{subcontractor_id}")
async def get_subcontractor(subcontractor_id: str):
    # Placeholder implementation - in production, query database
    if subcontractor_id == "1":
        return {"id": "1", "company_name": "ABC Construction", "contact_name": "John Doe", "email": "john@abc.com", "phone": "555-1234", "address": "123 Main St"}
    else:
        raise HTTPException(status_code=404, detail="Subcontractor not found")

@app.post("/api/subcontractors")
async def create_subcontractor(subcontractor: Subcontractor):
    # Placeholder implementation - in production, save to database
    return {"id": "3", **subcontractor.dict()}

@app.put("/api/subcontractors/{subcontractor_id}")
async def update_subcontractor(subcontractor_id: str, subcontractor: Subcontractor):
    # Placeholder implementation - in production, update database record
    return {"id": subcontractor_id, **subcontractor.dict()}

@app.delete("/api/subcontractors/{subcontractor_id}")
async def delete_subcontractor(subcontractor_id: str):
    # Placeholder implementation - in production, delete from database
    return {"message": f"Subcontractor {subcontractor_id} deleted"}

# Compliance endpoints
@app.get("/api/compliance/status")
async def get_compliance_status():
    # Placeholder implementation - in production, query database
    return {"overall_status": "COMPLIANT", "compliance_score": 85, "last_updated": "2026-04-25"}

@app.get("/api/compliance/alerts")
async def get_compliance_alerts():
    # Placeholder implementation - in production, query database
    return [
        {"id": 1, "type": "critical", "message": "Certification expiring in 30 days"},
        {"id": 2, "type": "warning", "message": "Documentation requires verification"}
    ]

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)