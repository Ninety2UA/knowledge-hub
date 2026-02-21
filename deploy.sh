#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Knowledge Hub -- Cloud Run deployment script
# ---------------------------------------------------------------------------
# Usage:
#   PROJECT_ID=my-gcp-project ./deploy.sh
#
# Prerequisites:
#   - gcloud CLI authenticated (`gcloud auth login`)
#   - Cloud Run, Cloud Build, Secret Manager, and Artifact Registry APIs enabled
#   - All secrets created in Secret Manager (see below)
#   - Default compute service account has roles/secretmanager.secretAccessor
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-}"
REGION="europe-west4"
SERVICE_NAME="knowledge-hub"

if [[ -z "$PROJECT_ID" ]]; then
    echo "ERROR: PROJECT_ID environment variable is required."
    echo "Usage: PROJECT_ID=my-gcp-project ./deploy.sh"
    exit 1
fi

echo "Deploying $SERVICE_NAME to Cloud Run..."
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --project="$PROJECT_ID" \
    --set-secrets="SLACK_BOT_TOKEN=slack-bot-token:latest,\
SLACK_SIGNING_SECRET=slack-signing-secret:latest,\
NOTION_API_KEY=notion-api-key:latest,\
NOTION_DATABASE_ID=notion-database-id:latest,\
GEMINI_API_KEY=gemini-api-key:latest,\
ALLOWED_USER_ID=allowed-user-id:latest" \
    --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO" \
    --min-instances=1 \
    --no-cpu-throttling \
    --cpu-boost \
    --memory=512Mi \
    --cpu=1 \
    --allow-unauthenticated

echo ""
echo "Deployment complete. Service URL:"
gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(status.url)'

# ---------------------------------------------------------------------------
# Cloud Scheduler setup (run manually after first deploy)
# ---------------------------------------------------------------------------
# These commands require the service URL from the deploy output above.
# Replace SERVICE_URL with the actual URL.
#
# 1. Create a service account for Cloud Scheduler:
#
#   gcloud iam service-accounts create scheduler-sa \
#       --project="$PROJECT_ID" \
#       --display-name="Cloud Scheduler SA"
#
# 2. Grant the invoker role on the Cloud Run service:
#
#   gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
#       --region="$REGION" \
#       --project="$PROJECT_ID" \
#       --member="serviceAccount:scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
#       --role="roles/run.invoker"
#
# 3. Weekly digest -- Monday 08:00 Amsterdam time:
#
#   gcloud scheduler jobs create http weekly-digest \
#       --project="$PROJECT_ID" \
#       --location="$REGION" \
#       --schedule="0 8 * * 1" \
#       --time-zone="Europe/Amsterdam" \
#       --http-method=POST \
#       --uri="SERVICE_URL/digest" \
#       --oidc-service-account-email="scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
#       --oidc-token-audience="SERVICE_URL"
#
# 4. Daily cost check -- every day at 23:55 Amsterdam time:
#
#   gcloud scheduler jobs create http daily-cost-check \
#       --project="$PROJECT_ID" \
#       --location="$REGION" \
#       --schedule="55 23 * * *" \
#       --time-zone="Europe/Amsterdam" \
#       --http-method=POST \
#       --uri="SERVICE_URL/cost-check" \
#       --oidc-service-account-email="scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
#       --oidc-token-audience="SERVICE_URL"
# ---------------------------------------------------------------------------
