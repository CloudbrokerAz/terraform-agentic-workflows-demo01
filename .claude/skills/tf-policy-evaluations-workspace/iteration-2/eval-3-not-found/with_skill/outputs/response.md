# Policy Evaluations — `run-NONEXISTENT12345`

Could not retrieve policy evaluations: the run could not be found.

## tfctl error

```
$ tfctl api /runs/run-NONEXISTENT12345
ERROR: Resource not found or you are unauthorized to this action. Check your account permissions.

  $ tfctl auth info
```

(exit code 2)

## What this means

The HCP Terraform API returned a not-found / unauthorized response for run ID `run-NONEXISTENT12345`. Two possibilities:

- **The run ID does not exist** on the host targeted by the active `tfctl` profile.
- **The run exists but the authenticated profile lacks permission** to read it (wrong organization / workspace, or insufficient token scope).

## Suggested next steps

- Double-check the run ID — copy it from the HCP Terraform run URL (`…/runs/run-XXXXXXXXXXXXXXXX`).
- Confirm the active profile points at the correct host/org: `tfctl profile display` and `tfctl auth info`.
- If the ID is correct, verify the token has access to the workspace that owns the run.

No task-stages or policy-evaluations calls were made — without a valid run there is nothing further to query.
