import os
import sys

# Ensure current directory is on python path for Lambda execution
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Set production environment defaults for Lambda
os.environ.setdefault("MEDGUARD_ENVIRONMENT", "production")
os.environ.setdefault("MEDGUARD_AGENT_MODE", "enforced")
os.environ.setdefault("MEDGUARD_AGENT_SYNC_ENABLED", "true")
os.environ.setdefault("MEDGUARD_RATE_LIMIT_ENABLED", "false")  # Handled at CloudFront / Lambda level

from mangum import Mangum
from app.main import app

# Mangum ASGI adapter for AWS Lambda
handler = Mangum(app, lifespan="off")

def lambda_handler(event, context):
    return handler(event, context)
