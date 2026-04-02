# Project configuration
project_id  = "restrictor-check-345e"
region      = "europe-west1"
environment = "dev"

# Service accounts
sa_name = "api-sa-dev"

# Artifact Registry
artifact_registry_name = "restrictor-ar-dev"

# GCS Bucket
bucket_name = "restrictor-gcs-dev"

# Labels
labels = {
  environment = "dev"
  managed-by  = "terraform"
}

# IAP Access
iap_accessor_member = "group:restrictor-app-users@hm.com"
