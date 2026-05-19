**Run**: `run-NONEXISTENT12345` — lookup failed

The HCP Terraform API returned an error fetching task-stages for this run:

```
ERROR: Resource not found or you are unauthorized to this action. Check your account permissions.
```

This typically means the run ID does not exist on the host bound to the active `tfctl` profile, or the profile's token lacks permission to view it. No task stages, policy evaluations, or outcomes could be retrieved.

Next steps:
- Verify the run ID is correct (copy from the run URL in the HCP Terraform UI).
- Confirm the active profile points at the right host: `tfctl profile display`.
- Confirm the token has read access to the workspace/organization that owns the run.
