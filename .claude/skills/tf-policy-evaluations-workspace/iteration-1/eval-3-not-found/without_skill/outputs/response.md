# Policy Results for `run-NONEXISTENT12345`

I could not retrieve policy results for this run. HCP Terraform returned **404 Not Found / Unauthorized** when looking it up.

## What I tried

```
$ tfctl run status run-NONEXISTENT12345
ERROR: Resource not found or you are unauthorized to this action.

$ tfctl api /runs/run-NONEXISTENT12345
ERROR: Resource not found or you are unauthorized to this action.

$ tfctl api /runs/run-NONEXISTENT12345/policy-checks
ERROR: Resource not found or you are unauthorized to this action.
```

The API returns the same error for two distinct cases, so the run is either:

1. **Nonexistent** — the run ID `run-NONEXISTENT12345` doesn't exist (most likely, given the placeholder-looking name), or
2. **Inaccessible** — the run exists in an organization or workspace that the active tfctl profile is not authorized to view.

## Suggested next steps

- Double-check the run ID. Valid HCP Terraform run IDs look like `run-` followed by 16 alphanumeric characters (e.g. `run-CZcmD7eapUMQ1L4Z`). `run-NONEXISTENT12345` does not match that pattern and is almost certainly a placeholder.
- Confirm the active profile and organization:
  ```
  tfctl auth info
  tfctl profile list
  ```
- If you have the HCP Terraform UI URL for the run, the ID is in the path: `/app/<org>/workspaces/<workspace>/runs/<run-id>`. Re-run with that real ID:
  ```
  tfctl run status run-XXXXXXXXXXXXXXXX
  ```

Once you provide a valid run ID I can pull the policy evaluation results (Sentinel / OPA policy sets, per-policy outcomes, enforcement levels, and any soft-mandatory overrides).
