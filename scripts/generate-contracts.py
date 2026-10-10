"""Export source-owned simulator schema, never runtime data or real credentials."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'onesa-ai-robot-backend'))
from robot_api.main import Settings, create_app
from robot_api.security import password_hash
config = Settings(operator_password_hash=password_hash('contract-export-test-only', '0'*32))
schema = create_app(config).openapi()
target = root / 'onesa-ai-robot-frontend/contracts/openapi.json'
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(schema, indent=2, sort_keys=True)+'\n')
print('Exported versioned simulation contract without opening a database.')
