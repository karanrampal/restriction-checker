#!/usr/bin/env bash
# Check the API by sending a test request to the /chat endpoint
set -euo pipefail

SERVICE_URL="https://restrictor-api-dev-608877602050.europe-west1.run.app"
TOKEN=$(gcloud auth print-identity-token)
TEST_USER_EMAIL="test-script-user@local.dev"
TEST_IMAGE_URL="https://imagebankstorageprod.blob.core.windows.net/articleimagebank/4-2026/cf385c86-f26c-4e1c-a749-206fbbba7979/new-%20dune%20for%20print%2009-104.png?sv=2025-07-05&se=2032-01-13T13%3A59%3A31Z&sr=b&sp=rw&sig=4gqFkgcNpRiP3i%2BgD8tp1OzwHjRjNV%2BnCXhtkRYd4iE%3D"

curl -X POST "${SERVICE_URL}/chat" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-App-User-Email: ${TEST_USER_EMAIL}" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"${TEST_IMAGE_URL}\"}"