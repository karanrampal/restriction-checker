# Project configuration
project_id  = "restrictor-check-p-0b1d"
region      = "europe-west1"
environment = "prod"

# Service accounts
sa_name = "api-sa-prod"

# Artifact Registry
artifact_registry_name = "restrictor-ar-prod"

# GCS Bucket
bucket_name = "restrictor-gcs-prod"

# Labels
labels = {
  environment = "prod"
  managed-by  = "terraform"
}

# IAP Access
iap_accessor_member = "group:restrictor-app-users@hm.com"
