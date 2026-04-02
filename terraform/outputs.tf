output "repository_url" {
  description = "The URL for artifact registry"
  value       = module.artifact_registry.repository_url
}

output "bucket_url" {
  description = "The URL of the GCS bucket"
  value       = module.cloud_storage.url
}
