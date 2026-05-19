# Policy Evaluation Results — `run-NONEXISTENT12345`

Could not retrieve policy evaluations for this run.

## Error

```
$ tfctl api /runs/run-NONEXISTENT12345
ERROR: Resource not found or you are unauthorized to this action. Check your account permissions.
```

The HCP Terraform / Terraform Enterprise API returned a not-found / unauthorized response for run ID `run-NONEXISTENT12345`, so no run metadata, task stages, or policy evaluations could be fetched.

## Possible causes

- The run ID does not exist (typo, copy/paste error, or fabricated ID).
- The run exists in an organization or workspace the active `tfctl` profile does not have permission to read.
- The run was deleted or belongs to a different HCP Terraform host than the active profile.

## Suggested next steps

- Double-check the run ID — valid IDs look like `run-` followed by a base-58 token (e.g. `run-CZcmD7eagjhyX0v3`).
- Verify the active profile and host:
  ```
  tfctl profile display
  tfctl auth info
  ```
- Confirm the run is visible in the HCP Terraform UI under the expected organization and workspace, and that your token has access to that workspace.
