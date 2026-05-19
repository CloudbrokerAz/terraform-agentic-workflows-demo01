**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

No policies blocked this run. It reached `applied`.

### Post-Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| `poleval-qvaFSNdUdasiLqfU` | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

Counts: passed 28, advisory-failed 7, mandatory-failed 0, errored 0.

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | VPC / default VPC must have flow logs enabled. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | `aws_s3_bucket_public_access_block` must block public access. |
| s3-enable-object-logging-for-read-events.sentinel | failed | advisory | S3 buckets must log read events. |
| s3-enable-object-logging-for-write-events.sentinel | failed | advisory | S3 buckets must log write events. |
| s3-require-mfa-delete.sentinel | failed | advisory | S3 buckets must have MFA delete enabled. |
| s3-require-ssl.sentinel | failed | advisory | All S3 bucket requests must use SSL. |
| vpc-flow-logging-enabled.sentinel | failed | advisory | VPC / default VPC must have flow logs enabled. |

Plus 28 advisory-passed policies.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

Counts: passed 262, advisory-failed 19, mandatory-failed 0, errored 0.

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| api-gateway-should-be-associated-with-a-waf-web-acl.sentinel | failed | advisory | API Gateway stage should use a WAFv2 web ACL association. |
| dynamo-db-tables-delete-protection-enabled.sentinel | failed | advisory | DynamoDB tables must enable delete protection. |
| ec2-attached-ebs-volumes-encrypted-at-rest.sentinel | failed | advisory | EBS volumes must be encrypted and attached. |
| ec2-instance-should-not-have-public-ip.sentinel | failed | advisory | EC2 instances should not have a public IP. |
| ec2-instance-virtualization-should-not-be-paravirtual.sentinel | failed | advisory | AMIs must use `hvm` virtualization. |
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory | VPC endpoint for EC2 service must be Interface type. |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | VPC / default VPC must have flow logs enabled. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory | Interface VPC endpoint required for Docker registry. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory | Interface VPC endpoint required for ECR API. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory | Interface VPC endpoint required for SSM Incident Manager Contacts. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory | Interface VPC endpoint required for SSM Incident Manager. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory | Interface VPC endpoint required for SSM. |
| elb-ensure-deletion-protection-enabled.sentinel | failed | advisory | ALB/NLB must enable deletion protection. |
| elb-ensure-http-request-redirection.sentinel | failed | advisory | ALB must redirect HTTP to HTTPS. |
| redshift-cluster-unrestricted-port-access-check.sentinel | failed | advisory | Block ingress from unknown sources to Redshift clusters. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | `aws_s3_bucket_public_access_block` must block public access. |
| s3-bucket-block-public-read-access.sentinel | failed | advisory | S3 buckets must block public read access. |
| s3-bucket-block-public-write-access.sentinel | failed | advisory | S3 buckets must block public write access. |
| s3-require-ssl.sentinel | failed | advisory | All S3 bucket requests must use SSL. |

Plus 262 advisory-passed policies.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Counts: passed 1, advisory-failed 0, mandatory-failed 0, errored 0. All policies passed.

### Key findings

- Run lifecycle: **applied** — no policies blocked the run.
- **No mandatory failures** — nothing required an override.
- **No soft-mandatory overrides used** — no policies were soft-mandatory failed.
- **No tool errors** — every policy evaluated cleanly. The 26 failures are all `advisory` (informational), spread across the CIS (7) and FSBP (19) AWS policy sets.
