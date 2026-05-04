"""
ETL Pipeline for OSHA Violation Data

Process flow:
1. Extract: Fetch violations from OSHA API via OSHAClient
2. Transform: Map to database schema, deduplicate, enrich
3. Load: Insert/upsert into PostgreSQL (violations, osha_inspections tables)
4. Error Handling: Log failed records to osha_api_logs

Usage:
python scripts/etl_osha.py --establishment "Acme Construction" --naics "23" --full-refresh
"""

import argparse
import logging
from typing import List, Dict, Any
from datetime import datetime
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from dataclasses import asdict

# Local imports
from services.osha_client import OSHAClient, OSHAViolation


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OSHAETL:
    def __init__(self, db_uri: str):
        self.db_uri = db_uri
        self.client = OSHAClient()

    def extract(self, params: Dict[str, Any]) -> List[OSHAViolation]:
        """Fetch violations from OSHA API."""
        try:
            logger.info(f"Extracting OSHA violations with params: {params}")
            violations = self.client.get_violations(params)
            logger.info(f"Extracted {len(violations)} violations")
            return violations
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

    def transform(self, violations: List[OSHAViolation]) -> Dict[str, List[Dict]]:
        """Transform violations into database-ready dicts."""
        # Deduplicate by osha_violation_id
        seen = set()
        unique_violations = []
        inspections = set()
        
        for v in violations:
            if v.osha_violation_id not in seen:
                seen.add(v.osha_violation_id)
                unique_violations.append(asdict(v))
                
                # Collect unique inspections for osha_inspections table
                inspections.add((
                    v.inspection_number,
                    v.activity_number,
                    v.site_city,
                    v.site_state,
                    v.site_zip_code,
                    v.naics_code,
                    v.issued_date[:4]  # Extract year from YYYY-MM-DD
                ))
        
        # Prepare inspection records
        inspection_records = [
            {
                "inspection_number": insp[0],
                "activity_number": insp[1],
                "site_city": insp[2],
                "site_state": insp[3],
                "site_zip_code": insp[4],
                "naics_code": insp[5],
                "inspection_date": f"{insp[6]}-01-01",  # Placeholder for full date
                "type": "N/A",
                "total_penalty": 0.0
            }
            for insp in inspections
        ]
        
        return {
            "violations": unique_violations,
            "inspections": inspection_records
        }

    def load(self, transformed_data: Dict[str, List[Dict]]) -> None:
        """Load data into PostgreSQL using upsert."""
        conn = None
        try:
            conn = psycopg2.connect(self.db_uri)
            cursor = conn.cursor()
            
            # Upsert violations
            if transformed_data["violations"]:
                violations = transformed_data["violations"]
                query = sql.SQL("""
                    INSERT INTO violations (
                        osha_violation_id, citation_number, inspection_number,
                        activity_number, violation_type, description, standard_cited,
                        issued_date, abatement_date, gravity_score, penalty_amount,
                        site_city, site_state, site_zip_code, naics_code,
                        is_osha_violation
                    )
                    VALUES %s
                    ON CONFLICT (osha_violation_id) DO UPDATE SET
                        citation_number = EXCLUDED.citation_number,
                        inspection_number = EXCLUDED.inspection_number,
                        violation_type = EXCLUDED.violation_type,
                        description = EXCLUDED.description,
                        standard_cited = EXCLUDED.standard_cited,
                        issued_date = EXCLUDED.issued_date,
                        abatement_date = EXCLUDED.abatement_date,
                        gravity_score = EXCLUDED.gravity_score,
                        penalty_amount = EXCLUDED.penalty_amount,
                        site_city = EXCLUDED.site_city,
                        site_state = EXCLUDED.site_state,
                        site_zip_code = EXCLUDED.site_zip_code,
                        naics_code = EXCLUDED.naics_code,
                        is_osha_violation = EXCLUDED.is_osha_violation
                """)
                values = [(
                    v["osha_violation_id"],
                    v["citation_number"],
                    v["inspection_number"],
                    v["activity_number"],
                    v["violation_type"],
                    v["description"],
                    v["standard_cited"],
                    v["issued_date"],
                    v["abatement_date"],
                    v["gravity_score"],
                    v["penalty_amount"],
                    v["site_city"],
                    v["site_state"],
                    v["site_zip_code"],
                    v["naics_code"],
                    True
                ) for v in violations]
                
                execute_values(cursor, query, values)
                logger.info(f"Loaded {len(values)} violations")
            
            # Upsert inspections
            if transformed_data["inspections"]:
                inspections = transformed_data["inspections"]
                query = sql.SQL("""
                    INSERT INTO osha_inspections (
                        inspection_number, activity_number,
                        site_city, site_state, site_zip_code, site_address,
                        naics_code, inspection_date, type, total_penalty
                    )
                    VALUES %s
                    ON CONFLICT (inspection_number) DO UPDATE SET
                        activity_number = EXCLUDED.activity_number,
                        site_city = EXCLUDED.site_city,
                        site_state = EXCLUDED.site_state,
                        site_zip_code = EXCLUDED.site_zip_code,
                        site_address = EXCLUDED.site_address,
                        naics_code = EXCLUDED.naics_code,
                        inspection_date = EXCLUDED.inspection_date,
                        type = EXCLUDED.type,
                        total_penalty = EXCLUDED.total_penalty
                """)
                values = [(
                    i["inspection_number"],
                    i["activity_number"],
                    i["site_city"],
                    i["site_state"],
                    i["site_zip_code"],
                    None,  # site_address placeholder
                    i["naics_code"],
                    i["inspection_date"],
                    i["type"],
                    i["total_penalty"]
                ) for i in inspections]
                
                execute_values(cursor, query, values)
                logger.info(f"Loaded {len(values)} inspections")
            
            conn.commit()
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Load failed: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def log_api_call(self, params: Dict[str, Any], records_processed: int, success: bool):
        """Log API call results to osha_api_logs."""
        conn = None
        try:
            conn = psycopg2.connect(self.db_uri)
            cursor = conn.cursor()
            
            query = sql.SQL("""
                INSERT INTO osha_api_logs (
                    request_type, request_parameters,
                    response_status, records_processed, records_failed,
                    error_message
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """)
            
            records_failed = records_processed if not success else 0
            cursor.execute(query, (
                "violations",
                params,
                200 if success else 500,
                records_processed,
                records_failed,
                None if success else "Pipeline exception"
            ))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to log API call: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def run(self, params: Dict[str, Any]) -> None:
        """Run full ETL pipeline."""
        try:
            # Extract
            violations = self.extract(params)
            
            # Transform
            transformed = self.transform(violations)
            
            # Load
            self.load(transformed)
            
            # Log
            self.log_api_call(
                params,
                len(transformed["violations"]),
                success=True
            )
            
        except Exception as e:
            logger.error(f"ETL failed: {e}")
            self.log_api_call(
                params,
                0,
                success=False
            )
            raise


def parse_args():
    parser = argparse.ArgumentParser(description="OSHA Violation ETL Pipeline")
    parser.add_argument("--establishment", help="Establishment name to filter violations")
    parser.add_argument("--naics", help="NAICS code to filter violations (e.g., 23 for construction)")
    parser.add_argument("--full-refresh", action="store_true", help="Perform full refresh")
    parser.add_argument("--db-uri", default="postgresql://postgres@localhost:5432/compliance", help="Database URI")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Build API params
    params = {}
    if args.establishment:
        params["establishment_name"] = args.establishment
    if args.naics:
        params["naics_code"] = args.naics
    
    etl = OSHAETL(args.db_uri)
    etl.run(params)