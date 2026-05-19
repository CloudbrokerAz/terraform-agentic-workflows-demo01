**Run**: `run-NONEXISTENT12345` — not found.

`tfctl api /runs/run-NONEXISTENT12345` returned:

```
ERROR: Resource not found or you are unauthorized to this action. Check your account permissions.
```

No policy evaluations can be retrieved. Possible causes:

- The run ID does not exist on the active `tfctl` profile's host.
- The active profile's token lacks permission to read this run.

Verify the run ID, then check the active profile with `tfctl auth info` (or re-initialise with `tfctl profile init`) and retry.
