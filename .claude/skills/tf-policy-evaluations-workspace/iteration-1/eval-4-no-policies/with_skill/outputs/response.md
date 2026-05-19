# Policy Evaluations — `run-hGthAq8Kuv5wcKZq`

**Total policies**: 317 | Passed: 308 | Advisory-failed: 9 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-hGthAq8Kuv5wcKZq` — status `applied`, trigger `manual`, auto-apply `true`

### Post-plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| `poleval-wSxowX2UuPiDSipZ` | sentinel | passed | 308 | 9 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | Requires `aws_vpc` / `aws_default_vpc` to have flow logs enabled. |
| `vpc-flow-logging-enabled.sentinel` | failed | advisory | Requires `aws_vpc` / `aws_default_vpc` to have flow logs enabled. |

plus 33 advisory-passed policies.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `ec2-service-vpc-endpoint-enabled.sentinel` | failed | advisory | Requires `aws_vpc_endpoint` of type `Interface` for service `ec2`. |
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | Requires `aws_vpc` / `aws_default_vpc` to have flow logs enabled. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel` | failed | advisory | Requires interface VPC endpoint for Docker registry. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel` | failed | advisory | Requires interface VPC endpoint for ECR API. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel` | failed | advisory | Requires interface VPC endpoint for SSM Incident Manager Contacts. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel` | failed | advisory | Requires interface VPC endpoint for SSM Incident Manager. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel` | failed | advisory | Requires interface VPC endpoint for Systems Manager. |

plus 274 advisory-passed policies.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| _no failures_ | — | — | 1 policy passed |

### Key findings

- Run completed (`applied`) — no policies blocked it.
- 9 advisory failures across CIS and FSBP policy sets — informational only, no override required.
- Recurring theme: VPC flow logs not enabled and missing interface VPC endpoints (ec2, ECR API, Docker registry, Systems Manager / Incident Manager). Worth a follow-up if FSBP/CIS alignment matters.
- No mandatory failures and no policy-tool errors.
