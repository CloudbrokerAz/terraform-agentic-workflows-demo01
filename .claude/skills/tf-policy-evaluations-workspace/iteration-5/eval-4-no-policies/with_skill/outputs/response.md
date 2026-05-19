**Total policies**: 317 | Passed: 308 | Advisory-failed: 9 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-hGthAq8Kuv5wcKZq` — status `applied`, trigger `manual`, auto-apply `true`

### Post-plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| poleval-wSxowX2UuPiDSipZ | sentinel | passed | 308 | 9 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement |
|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory |
| vpc-flow-logging-enabled.sentinel | failed | advisory |

Plus 33 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement |
|---|---|---|
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory |

Plus 274 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Zero failures (1 passed).
