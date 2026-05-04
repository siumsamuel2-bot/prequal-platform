"""
OSHA API Client for Violation Data Integration

Handles authentication, rate limiting, and data fetching from OSHA API.
Target: https://www.osha.gov/developer
"""
import os
import time
import requests
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
import logging


@dataclass
class OSHAViolation:
    osha_violation_id: str
    citation_number: str
    inspection_number: str
    activity_number: str
    violation_type: str
    description: str
    standard_cited: str
    issued_date: str
    abatement_date: Optional[str]
    gravity_score: Optional[float]
    penalty_amount: Optional[float]
    site_city: str
    site_state: str
    site_zip_code: str
    naics_code: str


class OSHAClient:
    BASE_URL = "https://api.osha.gov/v1"
    RATE_LIMIT_DELAY = 2  # seconds

    def __init__(self):
        self.api_key = os.getenv("OSHA_API_KEY")
        if not self.api_key:
            raise ValueError("OSHA_API_KEY environment variable not set")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        self.logger = logging.getLogger(__name__)

    def get_violations(self, params: Dict[str, Any]) -> List[OSHAViolation]:
        """
        Fetch OSHA violations with pagination and rate limiting.
        
        Args:
            params: Query parameters (e.g., {'establishment_name': 'Acme', 'naics_code': '23'})
            
        Returns:
            List of OSHAViolation dataclass instances
        """
        params = params.copy()
        params["api_key"] = self.api_key
        params.setdefault("limit", 100)
        
        violations = []
        endpoint = f"{self.BASE_URL}/violations"
        
        while endpoint:
            try:
                response = self.session.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Transform API response to dataclass
                for item in data.get("results", []):
                    violations.append(self._parse_violation(item))
                
                # Handle pagination
                endpoint = data.get("next")
                params = {}  # Clear params after first request (next URL contains them)
                
                # Respect rate limits
                time.sleep(self.RATE_LIMIT_DELAY)
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"OSHA API request failed: {e}")
                raise
        
        return violations

    def _parse_violation(self, api_data: Dict[str, Any]) -> OSHAViolation:
        """Map OSHA API fields to OSHAViolation dataclass."""
        return OSHAViolation(
            osha_violation_id=api_data.get("violation_id", ""),
            citation_number=api_data.get("citation_number", ""),
            inspection_number=api_data.get("inspection_number", ""),
            activity_number=api_data.get("activity_number", ""),
            violation_type=api_data.get("violation_type", ""),
            description=api_data.get("violation_description", ""),
            standard_cited=api_data.get("standard_cited", ""),
            issued_date=api_data.get("issued_date", ""),
            abatement_date=api_data.get("abatement_date"),
            gravity_score=api_data.get("gravity_score"),
            penalty_amount=api_data.get("initial_penalty"),
            site_city=api_data.get("site_city", ""),
            site_state=api_data.get("site_state", ""),
            site_zip_code=api_data.get("site_zip_code", ""),
            naics_code=api_data.get("naics_code", ""),
        )

    def log_api_call(self, request_type: str, params: Dict[str, Any], response_status: Optional[int] = None):
        """Log API calls to osha_api_logs table (via database)."""
        # Implementation deferred; logs to database via separate ETL process
        pass


if __name__ == "__main__":
    # Initialization test
    client = OSHAClient()
    print("OSHA Client initialized successfully")