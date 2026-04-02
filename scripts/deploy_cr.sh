#!/usr/bin/env bash
# Deploy a Cloud Run service with optional flags
set -euo pipefail

# Defaults (can be overridden via env or CLI args)
PROJECT_ID="${PROJECT_ID:-restrictor-check-345e}"
REGION="${REGION:-europe-west1}"
ENV="${ENV:-dev}"

CONCURRENCY="${CONCURRENCY:-4}"
CPU="${CPU:-1}"
MEMORY="${MEMORY:-2Gi}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
CPU_THROTTLING="${CPU_THROTTLING:-true}"
CPU_BOOST="${CPU_BOOST:-false}"
IAP="${IAP:-false}"
TIMEOUT="${TIMEOUT:-3600}"
PORT="${PORT:-8080}"

# Deferred until after CLI parsing.
IMAGE="${IMAGE:-}"
SERVICE_NAME="${SERVICE_NAME:-}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-}"
VPC_NETWORK="${VPC_NETWORK:-}"
VPC_SUBNET="${VPC_SUBNET:-}"
ENV_VARS="${ENV_VARS:-}"
CMD="${CMD:-}"

# CLI overrides (simple parser: --key=value)
for arg in "$@"; do
  case $arg in
    --project=*) PROJECT_ID="${arg#*=}" ;;
    --region=*) REGION="${arg#*=}" ;;
    --env=*) ENV="${arg#*=}" ;;
    --image=*) IMAGE="${arg#*=}" ;;
    --service=*) SERVICE_NAME="${arg#*=}" ;;
    --service-account=*) SERVICE_ACCOUNT_NAME="${arg#*=}" ;;
    --concurrency=*) CONCURRENCY="${arg#*=}" ;;
    --cpu=*) CPU="${arg#*=}" ;;
    --memory=*) MEMORY="${arg#*=}" ;;
    --min-instances=*) MIN_INSTANCES="${arg#*=}" ;;
    --max-instances=*) MAX_INSTANCES="${arg#*=}" ;;
    --no-cpu-throttling) CPU_THROTTLING="false" ;;
    --cpu-boost) CPU_BOOST="true" ;;
    --timeout=*) TIMEOUT="${arg#*=}" ;;
    --port=*) PORT="${arg#*=}" ;;
    --vpc-network=*) VPC_NETWORK="${arg#*=}" ;;
    --vpc-subnet=*) VPC_SUBNET="${arg#*=}" ;;
    --env-vars=*) ENV_VARS="${arg#*=}" ;;
    --cmd=*) CMD="${arg#*=}" ;;
    --iap) IAP="true" ;;
    *) echo "Unknown arg: $arg" ;;
  esac
done

# Compute derived defaults now that PROJECT_ID, REGION, and ENV are finalised
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT_ID}/restrictor-ar-${ENV}/restrictor:latest}"
SERVICE_NAME="${SERVICE_NAME:-restrictor-${ENV}}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-api-sa-${ENV}}"

echo "=========================================="
echo "Cloud Run Deploy"
echo "Service: ${SERVICE_NAME}"
echo "Image:   ${IMAGE}"
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Env:     ${ENV}"
echo "Service Account: ${SERVICE_ACCOUNT_NAME}"
echo "=========================================="

# Build args array conditionally
ARGS=(
  "${SERVICE_NAME}"
  "--project" "${PROJECT_ID}"
  "--region" "${REGION}"
  "--image" "${IMAGE}"
  "--cpu" "${CPU}"
  "--memory" "${MEMORY}"
  "--min-instances" "${MIN_INSTANCES}"
  "--max-instances" "${MAX_INSTANCES}"
  "--timeout" "${TIMEOUT}"
  "--port" "${PORT}"
  "--service-account" "${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  "--labels" "env=${ENV}"
  "--no-allow-unauthenticated"
)

# CPU throttling
if [[ "${CPU_THROTTLING}" == "true" ]]; then
  ARGS+=("--cpu-throttling")
else
  ARGS+=("--no-cpu-throttling")
fi

# CPU boost
if [[ "${CPU_BOOST}" == "true" ]]; then
  ARGS+=("--cpu-boost")
else
  ARGS+=("--no-cpu-boost")
fi

# IAP
if [[ "${IAP}" == "true" ]]; then
  ARGS+=("--iap")
fi

# Concurrency (skip if "default")
if [[ "${CONCURRENCY}" != "default" ]]; then
  ARGS+=("--concurrency" "${CONCURRENCY}")
fi

# Env vars
if [[ -n "${ENV_VARS}" ]]; then
  ARGS+=("--set-env-vars" "${ENV_VARS}")
fi

# Direct VPC Egress
if [[ -n "${VPC_NETWORK}" && -n "${VPC_SUBNET}" ]]; then
  ARGS+=("--network" "${VPC_NETWORK}")
  ARGS+=("--subnet" "${VPC_SUBNET}")
  ARGS+=("--vpc-egress" "private-ranges-only")
fi

# Custom command
if [[ -n "${CMD}" ]]; then
  ARGS+=("--args" "${CMD}")
fi

# Execute deploy
echo ""
echo "The following command will be executed:"
echo "gcloud run deploy ${ARGS[@]}"
echo ""
gcloud run deploy "${ARGS[@]}"

# Example command for reference:
# ./scripts/deploy_cr.sh \
#   --service=restrictor-api-dev \
#   --env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=restrictor-check-345e,GOOGLE_CLOUD_LOCATION=europe-west1"
# or
#
# ./scripts/deploy_cr.sh \
#   --service=restrictor-app-dev \
#   --env-vars="API_URL=https://restrictor-api-dev-608877602050.europe-west1.run.app,STREAMLIT_BROWSER_GATHER_USAGE_STATS=false" \
#   --cmd="streamlit,run,src/app.py,--server.port,8080,--server.address,0.0.0.0" \
#   --iap