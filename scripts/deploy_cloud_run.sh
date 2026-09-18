#!/usr/bin/env bash
set -euo pipefail

# Deploys a Cloud Run MCP endpoint. This script never places the
# Apify token in an image or command history; it uses Secret Manager instead.
# Usage: ./scripts/deploy_cloud_run.sh [PROJECT_ID] [REGION]

# Auto-load token from .env if present and not already set
if [[ -z "${APIFY_API_TOKEN:-}" && -f .env ]]; then
  APIFY_API_TOKEN="$(grep -E '^APIFY_API_TOKEN=' .env | cut -d '=' -f2- | tr -d '\"'\''')"
  export APIFY_API_TOKEN
fi

project_id="${1:-${GCP_PROJECT:-gen-lang-client-0076218291}}"
region="${2:-${GCP_REGION:-us-central1}}"
service_name="social-analytics-mcp"
service_account_name="social-analytics-mcp"
secret_name="apify-api-token"
allow_unauth="${ALLOW_UNAUTHENTICATED:-true}"

if [[ -z "${APIFY_API_TOKEN:-}" ]]; then
  echo "Error: APIFY_API_TOKEN must be set in .env or the environment." >&2
  exit 2
fi

echo "Deploying $service_name to Google Cloud Run (project: $project_id, region: $region)..."

gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com \
  --project "$project_id"

service_account_email="${service_account_name}@${project_id}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$service_account_email" --project "$project_id" >/dev/null 2>&1; then
  echo "Creating service account $service_account_name..."
  gcloud iam service-accounts create "$service_account_name" \
    --display-name="Social Analytics MCP" \
    --project "$project_id"
fi

if gcloud secrets describe "$secret_name" --project "$project_id" >/dev/null 2>&1; then
  echo "Updating Secret Manager secret $secret_name..."
  printf %s "$APIFY_API_TOKEN" | gcloud secrets versions add "$secret_name" --data-file=- --project "$project_id"
else
  echo "Creating Secret Manager secret $secret_name..."
  printf %s "$APIFY_API_TOKEN" | gcloud secrets create "$secret_name" \
    --replication-policy=automatic \
    --data-file=- \
    --project "$project_id"
fi

gcloud secrets add-iam-policy-binding "$secret_name" \
  --member="serviceAccount:${service_account_email}" \
  --role="roles/secretmanager.secretAccessor" \
  --project "$project_id" >/dev/null

auth_flag="--allow-unauthenticated"
if [[ "$allow_unauth" == "false" ]]; then
  auth_flag="--no-allow-unauthenticated"
fi

echo "Building container and deploying to Cloud Run (memory: 2Gi, cpu: 2, timeout: 300s)..."
gcloud run deploy "$service_name" \
  --source . \
  --project "$project_id" \
  --region "$region" \
  --service-account "$service_account_email" \
  --memory "2Gi" \
  --cpu "2" \
  --timeout "300" \
  --concurrency "80" \
  --set-secrets="APIFY_API_TOKEN=${secret_name}:latest" \
  --set-env-vars="MCP_TRANSPORT=streamable-http,MCP_HOST=0.0.0.0,MCP_HTTP_PATH=/mcp" \
  "$auth_flag" \
  --quiet

service_url="$(gcloud run services describe "$service_name" --project "$project_id" --region "$region" --format='value(status.url)')"
echo "=========================================================="
echo "Deployment successful!"
echo "Service Base URL:     ${service_url}"
echo "MCP Streamable URL:   ${service_url}/mcp"
echo "Health Check:         ${service_url}/health"
echo "Live Stats/Telemetry: ${service_url}/stats"
echo "Access Policy:        $([ "$allow_unauth" == "true" ] && echo "Public (Unauthenticated)" || echo "Authenticated")"
echo "=========================================================="

