output "published_modules" {
  description = "Private registry source addresses for the published modules."
  value = {
    for repo, mod in tfe_registry_module.this :
    repo => "${var.hostname}/${var.organization}/${mod.name}/${mod.module_provider}"
  }
}

output "module_count" {
  description = "Number of modules published into the private registry."
  value       = length(tfe_registry_module.this)
}
