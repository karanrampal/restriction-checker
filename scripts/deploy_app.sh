#!/usr/bin/env bash
# Deploy a restrictor application
set -euo pipefail

echo "Deploying restrictor API to Cloud Run..."
./scripts/deploy_cr.sh \
  --service=restrictor-api-dev \
  --env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=restrictor-check-345e,GOOGLE_CLOUD_LOCATION=global"

echo ""
echo "Deploying restrictor App to Cloud Run..."
./scripts/deploy_cr.sh \
  --service=restrictor-app-dev \
  --env-vars="API_URL=https://restrictor-api-dev-608877602050.europe-west1.run.app,STREAMLIT_BROWSER_GATHER_USAGE_STATS=false" \
  --cmd="streamlit,run,src/app.py,--server.port,8080,--server.address,0.0.0.0" \
  --iap