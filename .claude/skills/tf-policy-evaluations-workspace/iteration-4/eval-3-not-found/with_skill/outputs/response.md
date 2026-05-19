**Run**: `run-NONEXISTENT12345` — not found.

`tfctl api /runs/run-NONEXISTENT12345` failed:

```
ERROR: Resource not found or you are unauthorized to this action. Check your account permissions.

  $ tfctl auth info
```

The run ID does not exist in the active profile's organization, or the profile's token lacks permission to read it. No policy evaluations can be retrieved. To diagnose:

- Confirm the active profile points at the correct host/org: `tfctl auth info`
- Verify the run ID is correct (expected format `run-` + 16 alphanumeric characters; `run-NONEXISTENT12345` is 17 characters and not a valid HCP Terraform ID).
