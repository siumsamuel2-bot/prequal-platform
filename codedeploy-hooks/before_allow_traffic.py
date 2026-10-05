"""
CodeDeploy Hook: BeforeAllowTraffic

This hook runs just before production traffic is shifted to the new task set.
It performs final validation to ensure the deployment is ready for production traffic.
"""

import json
import os
import requests
from datetime import datetime


def lambda_handler(event, context):
    """
    CodeDeploy lifecycle event handler for BeforeAllowTraffic hook.
    
    Args:
        event: CodeDeploy event containing deployment information
        context: Lambda context object
        
    Returns:
        dict: Status response indicating success or failure
    """
    print(f"Starting BeforeAllowTraffic hook at {datetime.utcnow().isoformat()}")
    print(f"Deployment ID: {event.get('DeploymentId', '')}")
    
    try:
        environment = os.environ.get('ENVIRONMENT', 'production')
        base_url = os.environ.get('SERVICE_URL', '')
        
        if not base_url:
            base_url = 'https://prequal.yourcompany.com' if environment == 'production' else 'https://staging.prequal.yourcompany.com'
        
        # Final health check before allowing traffic
        print(f"Running final health check against {base_url}...")
        
        response = requests.get(f"{base_url}/api/health", timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"Health check failed with status {response.status_code}")
        
        data = response.json()
        print(f"Health check response: {json.dumps(data, indent=2)}")
        
        # Verify critical services are connected
        if 'services' in data:
            for service, status in data['services'].items():
                if status != 'healthy':
                    raise Exception(f"Service {service} is not healthy: {status}")
        
        print("✅ All checks passed - ready to accept production traffic")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'SUCCEEDED',
                'message': 'Ready to accept production traffic',
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"❌ Pre-traffic validation failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'FAILED',
                'message': str(e),
                'deployment_id': event.get('DeploymentId', '')
            })
        }


if __name__ == '__main__':
    test_event = {'DeploymentId': 'test-123'}
    test_context = type('Context', (), {})()
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))