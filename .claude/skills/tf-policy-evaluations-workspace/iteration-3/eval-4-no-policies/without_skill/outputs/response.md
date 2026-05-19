# Policy Evaluations — `run-hGthAq8Kuv5wcKZq`

**Run status:** `applied` (succeeded, auto-applied 2026-03-11 04:21:33 UTC)

Policies **did** run on this run — they were attached to the `post_plan` task stage as a Sentinel evaluation (the legacy `/policy-checks` and `/tf-policy-evaluations` endpoints on the run were both empty, but the task stage held the actual evaluation).

## Overall evaluation

| Field | Value |
|---|---|
| Evaluation ID | `poleval-wSxowX2UuPiDSipZ` |
| Policy kind | Sentinel |
| Status | **passed** |
| Task stage | `ts-typfk8e6VteKbnXG` (`post_plan`, passed) |
| Passed | 308 |
| Advisory failed | 9 |
| Mandatory failed | 0 |
| Errored | 0 |

No mandatory policies blocked the run. All 9 failures were **advisory** only, so the run was free to apply.

## Per–policy-set summary

| Policy set | Passed | Advisory failed | Mandatory failed | Errored |
|---|---:|---:|---:|---:|
| `policy-library-CIS-Policy-Set-for-AWS-Terraform` | 33 | 2 | 0 | 0 |
| `policy-library-fsbp-policy-set-for-aws-terraform` | 274 | 7 | 0 | 0 |
| `hashicorp-sentinel-require-pmr` | 1 | 0 | 0 | 0 |

## Advisory failures (9)

All are advisory — informational only — and point at two themes: VPC flow logging and VPC interface endpoints.

**VPC flow logs not enabled** (2 policies, fired twice across sets)
- `ec2-vpc-flow-logging-enabled.sentinel` — `aws_vpc` / `aws_default_vpc` should have flow logs enabled (appears in CIS set and FSBP set).
- `vpc-flow-logging-enabled.sentinel` — same requirement, separate policy.

**Missing VPC interface endpoints** (FSBP set)
- `ec2-service-vpc-endpoint-enabled.sentinel` — expects an Interface VPC endpoint for `ec2`.
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel`

## Takeaway

Run passed policy evaluation and was applied. No overrides were needed (mandatory-failed = 0). The advisory findings are worth tracking as follow-up hardening — enable VPC flow logs and add the missing Interface VPC endpoints — but they did not gate this run.
