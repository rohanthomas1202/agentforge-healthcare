#!/bin/bash
# Cloud Setup Script — Run on Lightsail host after docker compose up
#
# This script:
#   1. Waits for OpenEMR to finish initializing
#   2. Registers an OAuth2 client
#   3. Enables the client in the database
#   4. Sets site_addr_oath for internal Docker networking
#   5. Writes client credentials to .env
#   6. Restarts the agentforge service
#   7. Runs all seed scripts
#
# Usage:
#   cd /path/to/agentforge-healthcare
#   chmod +x scripts/cloud_setup.sh
#   ./scripts/cloud_setup.sh

set -euo pipefail

COMPOSE_FILE="docker-compose.cloud.yml"
COMPOSE="docker compose -f $COMPOSE_FILE"

echo "=========================================="
echo "  AgentForge Cloud Setup"
echo "=========================================="

# --- Step 0: Install Python deps on host for seed scripts ---
echo ""
echo "[0/7] Installing httpx for seed scripts..."
pip3 install -q httpx 2>/dev/null || pip install -q httpx
echo "  Done."

# --- Step 1: Wait for OpenEMR ---
echo ""
echo "[1/7] Waiting for OpenEMR to initialize..."
echo "  (First boot takes 3-5 minutes)"

MAX_WAIT=300
WAITED=0
while true; do
    # Check if OpenEMR responds to a basic request
    if $COMPOSE exec -T openemr curl -ksf https://localhost/apis/default/fhir/metadata > /dev/null 2>&1; then
        echo "  OpenEMR is ready!"
        break
    fi
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "  ERROR: OpenEMR did not become ready within ${MAX_WAIT}s"
        echo "  Check logs: $COMPOSE logs openemr"
        exit 1
    fi
    sleep 10
    WAITED=$((WAITED + 10))
    echo "  Waiting... (${WAITED}s)"
done

# --- Step 2: Register OAuth Client ---
echo ""
echo "[2/7] Registering OAuth2 client..."

REGISTRATION_RESPONSE=$($COMPOSE exec -T openemr curl -ks -X POST \
    https://localhost/oauth2/default/registration \
    -H "Content-Type: application/json" \
    -d '{
        "application_type": "private",
        "redirect_uris": ["https://localhost"],
        "client_name": "AgentForge Cloud",
        "token_endpoint_auth_method": "client_secret_post",
        "grant_types": ["authorization_code", "password"],
        "response_types": ["code"],
        "scope": "openid api:fhir user/Patient.read user/Patient.write user/Encounter.read user/Condition.read user/AllergyIntolerance.read user/MedicationRequest.read user/Medication.read user/Immunization.read user/Appointment.read user/Practitioner.read user/Practitioner.write user/PractitionerRole.read user/Organization.read user/Location.read user/Observation.read user/Coverage.read user/DocumentReference.read"
    }')

# Extract client_id and client_secret from JSON response
CLIENT_ID=$(echo "$REGISTRATION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['client_id'])" 2>/dev/null)
CLIENT_SECRET=$(echo "$REGISTRATION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['client_secret'])" 2>/dev/null)

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "  ERROR: Failed to register OAuth client."
    echo "  Response: $REGISTRATION_RESPONSE"
    exit 1
fi

echo "  Client ID: $CLIENT_ID"
echo "  Client Secret: ${CLIENT_SECRET:0:20}..."

# --- Step 3: Enable client in DB ---
echo ""
echo "[3/7] Enabling OAuth client in database..."

$COMPOSE exec -T mariadb mariadb -u openemr -popenemr openemr -e \
    "UPDATE oauth_clients SET is_enabled=1, grant_types='authorization_code password' WHERE client_name='AgentForge Cloud';"

echo "  Done."

# --- Step 4: Set site_addr_oath for Docker internal networking ---
echo ""
echo "[4/7] Setting site_addr_oath to https://openemr..."

$COMPOSE exec -T mariadb mariadb -u openemr -popenemr openemr -e \
    "UPDATE globals SET gl_value='https://openemr' WHERE gl_name='site_addr_oath';"

echo "  Done."

# --- Step 5: Write credentials to .env ---
echo ""
echo "[5/7] Updating .env with OAuth credentials..."

# Update or add OPENEMR_CLIENT_ID and OPENEMR_CLIENT_SECRET in .env
if grep -q "^OPENEMR_CLIENT_ID=" .env 2>/dev/null; then
    sed -i "s|^OPENEMR_CLIENT_ID=.*|OPENEMR_CLIENT_ID=$CLIENT_ID|" .env
else
    echo "OPENEMR_CLIENT_ID=$CLIENT_ID" >> .env
fi

if grep -q "^OPENEMR_CLIENT_SECRET=" .env 2>/dev/null; then
    sed -i "s|^OPENEMR_CLIENT_SECRET=.*|OPENEMR_CLIENT_SECRET=$CLIENT_SECRET|" .env
else
    echo "OPENEMR_CLIENT_SECRET=$CLIENT_SECRET" >> .env
fi

echo "  .env updated."

# --- Step 6: Restart agentforge to pick up new creds ---
echo ""
echo "[6/7] Restarting agentforge service..."

$COMPOSE restart agentforge
sleep 5
echo "  Done."

# --- Step 7: Run seed scripts ---
echo ""
echo "[7/7] Running seed scripts..."

# Detect the mariadb container name for DB operations
MARIADB_CONTAINER=$($COMPOSE ps -q mariadb | xargs docker inspect --format '{{.Name}}' | sed 's|^/||')
echo "  MariaDB container: $MARIADB_CONTAINER"

# Export env vars for seed scripts (they connect to OpenEMR via localhost:9300)
export OPENEMR_BASE_URL="https://localhost:9300"
export OPENEMR_CLIENT_ID="$CLIENT_ID"
export OPENEMR_CLIENT_SECRET="$CLIENT_SECRET"
export OPENEMR_USERNAME="admin"
export OPENEMR_PASSWORD="pass"
export OPENEMR_CONTAINER="$MARIADB_CONTAINER"

echo ""
echo "  --- seed_data.py (3 patients + practitioners) ---"
python3 scripts/seed_data.py

echo ""
echo "  --- seed_providers_appointments.py (appointments) ---"
python3 scripts/seed_providers_appointments.py

echo ""
echo "  --- seed_10_patients.py (10 additional patients) ---"
python3 scripts/seed_10_patients.py

# --- Done ---
echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "  Your AgentForge instance is live at:"
echo "    http://$(curl -s http://checkip.amazonaws.com 2>/dev/null || echo 'YOUR_IP'):80"
echo ""
echo "  Test the API:"
echo "    curl http://localhost/api/health"
echo ""
echo "  13 patients + 3 providers + appointments seeded."
echo "=========================================="
