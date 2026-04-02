resource "google_service_account" "api_sa" {
  project      = var.project_id
  account_id   = var.sa_name
  display_name = "API Cloud Run Service Account"
  description  = "Service account for running API on Cloud Run"
}

resource "google_project_iam_member" "api_sa_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/aiplatform.user",
    "roles/run.invoker"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.api_sa.email}"
}

resource "google_project_iam_member" "iap_users" {
  count   = var.iap_accessor_member != "" ? 1 : 0
  project = var.project_id
  role    = "roles/iap.httpsResourceAccessor"
  member  = var.iap_accessor_member
}

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id    = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_name
  description   = "Docker repository for container images"

  cleanup_policies = [
    {
      id     = "delete-old-untagged"
      action = "DELETE"
      condition = {
        tag_state  = "UNTAGGED"
        older_than = "30d"
      }
    },
    {
      id     = "delete-old-tagged"
      action = "DELETE"
      condition = {
        tag_state  = "TAGGED"
        older_than = "90d"
      }
    }
  ]

  labels = merge(var.labels, { component = "artifact-registry" })

  iam_members = [
    {
      role   = "roles/artifactregistry.reader"
      member = "serviceAccount:${google_service_account.api_sa.email}"
    }
  ]
}

module "cloud_storage" {
  source = "./modules/cloud_storage"

  name       = var.bucket_name
  project_id = var.project_id
  location   = var.region

  labels = merge(var.labels, { component = "gcs-bucket" })

  iam_members = [
    {
      role   = "roles/storage.objectUser"
      member = "serviceAccount:${google_service_account.api_sa.email}"
    }
  ]
}
