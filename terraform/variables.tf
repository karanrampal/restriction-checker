variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "environment" {
  description = "The environment (dev, prod, etc.)"
  type        = string
}

variable "region" {
  description = "The GCP region for the Cloud Run service."
  type        = string
}

variable "sa_name" {
  description = "The name of the service account."
  type        = string
}

variable "artifact_registry_name" {
  description = "The name/ID of the Artifact Registry repository."
  type        = string
}

variable "bucket_name" {
  description = "The name of the GCS bucket."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "Bucket name must comply with Google Cloud naming conventions."
  }
}

variable "labels" {
  description = "Labels to apply to the resources."
  type        = map(string)
  default     = {}
}

variable "iap_accessor_member" {
  description = "The principal (e.g., 'group:restrictor-app-users@hm.com') to grant IAP access to the App. If empty, the group IAM binding won't be created."
  type        = string
  default     = ""

  validation {
    condition     = var.iap_accessor_member == "" || can(regex("^(user|group|serviceAccount|domain):.+$", var.iap_accessor_member))
    error_message = "The iap_accessor_member must be empty or start with 'user:', 'group:', 'serviceAccount:', or 'domain:' followed by an identifier."
  }
}
