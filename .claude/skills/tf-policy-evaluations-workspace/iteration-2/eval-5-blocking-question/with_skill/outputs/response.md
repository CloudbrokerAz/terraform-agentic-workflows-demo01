**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

No policies blocked this run. The run completed successfully (status `applied`).

### Post-plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| `poleval-qvaFSNdUdasiLqfU` | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

Plus 28 passed policies in this set. 7 advisory-failed (informational only — did not block):

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | Verifies `aws_s3_bucket_public_access_block` blocks public access. |
| s3-enable-object-logging-for-read-events.sentinel | failed | advisory | Requires `aws_s3_bucket` object logging for read events. |
| s3-enable-object-logging-for-write-events.sentinel | failed | advisory | Requires `aws_s3_bucket` object logging for write events. |
| s3-require-mfa-delete.sentinel | failed | advisory | Requires general-purpose S3 buckets to have MFA delete enabled. |
| s3-require-ssl.sentinel | failed | advisory | Mandates SSL on `aws_s3_bucket` via `aws_s3_bucket_policy`. |
| vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

Plus 262 passed policies in this set. 19 advisory-failed (informational only — did not block):

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| api-gateway-should-be-associated-with-a-waf-web-acl.sentinel | failed | advisory | Checks `aws_api_gateway_stage` uses `aws_wafv2_web_acl_association`. |
| dynamo-db-tables-delete-protection-enabled.sentinel | failed | advisory | Requires `aws_dynamodb_table` delete-protection enabled. |
| ec2-attached-ebs-volumes-encrypted-at-rest.sentinel | failed | advisory | Requires `aws_ebs_volume` to be encrypted and attached. |
| ec2-instance-should-not-have-public-ip.sentinel | failed | advisory | Requires `aws_instance` not to have a public IP. |
| ec2-instance-virtualization-should-not-be-paravirtual.sentinel | failed | advisory | Requires `aws_ami` `virtualization_type` to be `hvm`. |
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory | Requires `aws_vpc_endpoint` interface endpoint for `ec2`. |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | Requires VPC flow logs enabled. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory | Requires interface VPC endpoint for docker registry. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory | Requires interface VPC endpoint for ECR API. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory | Requires interface VPC endpoint for SSM Incident Manager contacts. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory | Requires interface VPC endpoint for SSM Incident Manager. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory | Requires interface VPC endpoint for Systems Manager. |
| elb-ensure-deletion-protection-enabled.sentinel | failed | advisory | Requires `aws_lb` `enable_deletion_protection = true`. |
| elb-ensure-http-request-redirection.sentinel | failed | advisory | Requires ALB listener rule to redirect HTTP to HTTPS. |
| redshift-cluster-unrestricted-port-access-check.sentinel | failed | advisory | Blocks ingress traffic from unknown sources to Redshift. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | Verifies S3 public access block. |
| s3-bucket-block-public-read-access.sentinel | failed | advisory | S3 buckets should block public read access. |
| s3-bucket-block-public-write-access.sentinel | failed | advisory | S3 buckets should block public write access. |
| s3-require-ssl.sentinel | failed | advisory | Mandates SSL on `aws_s3_bucket`. |

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Plus 1 passed policies in this set.

### Key findings

- Run **applied successfully** — no policies blocked it.
- **Zero mandatory-failed** policies — nothing required a hard block.
- **Zero soft-mandatory overridable failures** — no human override was needed. (All three policy sets show `overridable: true`, but that flag is irrelevant when no mandatory failures exist.)
- **Zero policy tool errors** — all evaluations executed cleanly. The 26 advisory failures across the CIS and FSBP sets are informational and did not affect the run.
