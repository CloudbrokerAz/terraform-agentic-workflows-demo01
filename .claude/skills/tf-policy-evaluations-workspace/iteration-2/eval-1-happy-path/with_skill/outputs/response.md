**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

### Post-plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| `poleval-qvaFSNdUdasiLqfU` | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| `s3-block-public-access-bucket-level.sentinel` | failed | advisory | Verifies `aws_s3_bucket_public_access_block` blocks public access on S3 general purpose buckets. |
| `s3-enable-object-logging-for-read-events.sentinel` | failed | advisory | Requires `aws_s3_bucket` to have object logging enabled for read events. |
| `s3-enable-object-logging-for-write-events.sentinel` | failed | advisory | Requires `aws_s3_bucket` to have object logging enabled for write events. |
| `s3-require-mfa-delete.sentinel` | failed | advisory | Verifies S3 general purpose buckets have MFA delete enabled in versioning configuration. |
| `s3-require-ssl.sentinel` | failed | advisory | Mandates all requests to `aws_s3_bucket` use SSL via `aws_s3_bucket_policy`. |
| `vpc-flow-logging-enabled.sentinel` | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |

Plus 28 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `api-gateway-should-be-associated-with-a-waf-web-acl.sentinel` | failed | advisory | Checks whether `aws_api_gateway_stage` uses `aws_wafv2_web_acl_association`. |
| `dynamo-db-tables-delete-protection-enabled.sentinel` | failed | advisory | Requires `deletion_protection_enabled` on `aws_dynamodb_table` to be true. |
| `ec2-attached-ebs-volumes-encrypted-at-rest.sentinel` | failed | advisory | Requires `aws_ebs_volume` resources to be encrypted and in attached state. |
| `ec2-instance-should-not-have-public-ip.sentinel` | failed | advisory | Requires `aws_instance` to not have a public IP address. |
| `ec2-instance-virtualization-should-not-be-paravirtual.sentinel` | failed | advisory | Requires `aws_ami` `virtualization_type` to be `hvm`. |
| `ec2-service-vpc-endpoint-enabled.sentinel` | failed | advisory | Requires `aws_vpc_endpoint` of Interface type for the `ec2` service. |
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel` | failed | advisory | Requires interface `aws_vpc_endpoint` for docker registry referenced to a VPC. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel` | failed | advisory | Requires interface `aws_vpc_endpoint` for ECR API referenced to a VPC. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel` | failed | advisory | Requires interface `aws_vpc_endpoint` for SSM Incident Manager Contacts. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel` | failed | advisory | Requires interface `aws_vpc_endpoint` for SSM Incident Manager. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel` | failed | advisory | Requires interface `aws_vpc_endpoint` for Systems Manager. |
| `elb-ensure-deletion-protection-enabled.sentinel` | failed | advisory | Requires `aws_lb` to have `enable_deletion_protection = true`. |
| `elb-ensure-http-request-redirection.sentinel` | failed | advisory | Ensures ALB has a listener rule redirecting HTTP to HTTPS. |
| `redshift-cluster-unrestricted-port-access-check.sentinel` | failed | advisory | Requires security groups to block ingress from unknown sources to `aws_redshift_cluster`. |
| `s3-block-public-access-bucket-level.sentinel` | failed | advisory | Verifies `aws_s3_bucket_public_access_block` blocks public access on S3 buckets. |
| `s3-bucket-block-public-read-access.sentinel` | failed | advisory | S3 general purpose buckets should block public read access. |
| `s3-bucket-block-public-write-access.sentinel` | failed | advisory | S3 general purpose buckets should block public write access. |
| `s3-require-ssl.sentinel` | failed | advisory | Mandates all requests to `aws_s3_bucket` use SSL via `aws_s3_bucket_policy`. |

Plus 262 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

All 1 policy passed.

### Key findings

- Run **applied** successfully — no policies blocked it. Stage `post_plan` passed with all enforcement at advisory level.
- **26 advisory failures** across two policy sets (CIS: 7, AWS FSBP: 19) — informational only, but flag widespread S3 public-access, SSL, and VPC flow-logging gaps.
- S3 hardening is the dominant theme: SSL, public-access block, object logging, and MFA-delete failures appear in both CIS and FSBP sets.
- No mandatory failures and no tool errors — nothing requires override action.
