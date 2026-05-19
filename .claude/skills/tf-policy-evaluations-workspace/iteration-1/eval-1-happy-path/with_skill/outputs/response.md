# Policy Evaluations — `run-iURWDL3wVxzefsjo`

**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

### Post-plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| `poleval-qvaFSNdUdasiLqfU` | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

Counts: 28 passed / 7 advisory-failed / 0 mandatory-failed / 0 errored.

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | `aws_vpc` / `aws_default_vpc` must have flow logs enabled |
| `s3-block-public-access-bucket-level.sentinel` | failed | advisory | Bucket-level S3 public-access block must be compliant |
| `s3-enable-object-logging-for-read-events.sentinel` | failed | advisory | `aws_s3_bucket` must have CloudTrail read-event object logging |
| `s3-enable-object-logging-for-write-events.sentinel` | failed | advisory | `aws_s3_bucket` must have CloudTrail write-event object logging |
| `s3-require-mfa-delete.sentinel` | failed | advisory | S3 buckets must have MFA delete enabled in versioning |
| `s3-require-ssl.sentinel` | failed | advisory | S3 bucket policies must require SSL |
| `vpc-flow-logging-enabled.sentinel` | failed | advisory | `aws_vpc` / `aws_default_vpc` must have flow logs enabled |

<details><summary>Violation detail — CIS failures</summary>

- `ec2-vpc-flow-logging-enabled` / `vpc-flow-logging-enabled`: `module.vpc.aws_vpc.this`, `module.vpc.aws_default_vpc.this` — no flow logs
- `s3-block-public-access-bucket-level`: `module.demo_bucket.aws_s3_bucket.this`
- `s3-enable-object-logging-for-read-events` / `s3-enable-object-logging-for-write-events`: `module.demo_bucket.aws_s3_bucket.this[0]`
- `s3-require-mfa-delete`: `module.demo_bucket.aws_s3_bucket.this` — no linked `aws_s3_bucket_versioning` with `mfa_delete = Enabled`
- `s3-require-ssl`: `module.demo_bucket.aws_s3_bucket.this` — no SSL-enforcing `aws_s3_bucket_policy`

</details>

Plus 28 advisory-passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

Counts: 262 passed / 19 advisory-failed / 0 mandatory-failed / 0 errored.

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `api-gateway-should-be-associated-with-a-waf-web-acl.sentinel` | failed | advisory | `aws_api_gateway_stage` should be associated with a WAFv2 web ACL |
| `dynamo-db-tables-delete-protection-enabled.sentinel` | failed | advisory | `aws_dynamodb_table.deletion_protection_enabled` must be true |
| `ec2-attached-ebs-volumes-encrypted-at-rest.sentinel` | failed | advisory | Attached `aws_ebs_volume` must be encrypted |
| `ec2-instance-should-not-have-public-ip.sentinel` | failed | advisory | EC2 instances must not have a public IP |
| `ec2-instance-virtualization-should-not-be-paravirtual.sentinel` | failed | advisory | `aws_ami.virtualization_type` must be `hvm` |
| `ec2-service-vpc-endpoint-enabled.sentinel` | failed | advisory | VPC must have an `ec2` interface endpoint |
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | `aws_vpc` / `aws_default_vpc` must have flow logs enabled |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel` | failed | advisory | VPC missing interface endpoint (docker registry) |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel` | failed | advisory | VPC missing interface endpoint (ecr-api) |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel` | failed | advisory | VPC missing interface endpoint (SSM) |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel` | failed | advisory | VPC missing interface endpoint (SSM Incident Manager) |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel` | failed | advisory | VPC missing interface endpoint (SSM Incident Manager Contacts) |
| `elb-ensure-deletion-protection-enabled.sentinel` | failed | advisory | `aws_lb.enable_deletion_protection` must be true |
| `elb-ensure-http-request-redirection.sentinel` | failed | advisory | ALB must redirect HTTP to HTTPS |
| `redshift-cluster-unrestricted-port-access-check.sentinel` | failed | advisory | Security groups must not allow `0.0.0.0/0` / `::/0` to Redshift ports |
| `s3-block-public-access-bucket-level.sentinel` | failed | advisory | Bucket-level S3 public-access block must be compliant |
| `s3-bucket-block-public-read-access.sentinel` | failed | advisory | S3 buckets must block public read access |
| `s3-bucket-block-public-write-access.sentinel` | failed | advisory | S3 buckets must block public write access |
| `s3-require-ssl.sentinel` | failed | advisory | S3 bucket policies must require SSL |

<details><summary>Violation detail — FSBP failures</summary>

- `api-gateway-should-be-associated-with-a-waf-web-acl`: `module.alb.aws_wafv2_web_acl_association.this`
- `dynamo-db-tables-delete-protection-enabled`: `module.demo_metadata.aws_dynamodb_table.this[0]`
- `ec2-attached-ebs-volumes-encrypted-at-rest`: `module.app_server.aws_ebs_volume.this`, `module.app_server.aws_volume_attachment.this`
- `ec2-instance-should-not-have-public-ip`: `module.app_server.aws_instance.this[0]`
- `ec2-instance-virtualization-should-not-be-paravirtual`: `module.app_server.aws_instance.this`, `module.app_server.aws_instance.ignore_ami`
- `ec2-service-vpc-endpoint-enabled` / all `ec2-vpc-should-be-configured-for-interface-endpoint-*`: `module.vpc.aws_vpc.this`
- `ec2-vpc-flow-logging-enabled`: `module.vpc.aws_vpc.this`, `module.vpc.aws_default_vpc.this`
- `elb-ensure-deletion-protection-enabled` / `elb-ensure-http-request-redirection`: `module.alb.aws_lb.this[0]`
- `redshift-cluster-unrestricted-port-access-check`: `module.alb.aws_security_group.this[0]`, `module.alb.aws_vpc_security_group_ingress_rule.this["all_http"]`
- `s3-block-public-access-bucket-level` / `s3-require-ssl`: `module.demo_bucket.aws_s3_bucket.this`
- `s3-bucket-block-public-read-access` / `s3-bucket-block-public-write-access`: `module.demo_bucket.aws_iam_policy_document.lb_log_delivery[0]`, `module.demo_bucket.aws_iam_policy_document.elb_log_delivery[0]`

</details>

Plus 262 advisory-passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Counts: 1 passed / 0 advisory-failed / 0 mandatory-failed / 0 errored. All policies passed.

### Key findings

- Run **applied** successfully — no policy blocked it (zero mandatory failures, zero tool errors).
- **26 advisory failures** across two AWS security baselines (CIS: 7, FSBP: 19). Advisory = informational only, but they flag real Security Hub control gaps.
- Hot spots: `module.vpc` (no flow logs, missing interface endpoints), `module.demo_bucket` (no public-access block, no SSL enforcement, no MFA delete, no object logging), `module.app_server` (unencrypted EBS, public IP), `module.alb` (no deletion protection, no HTTP→HTTPS redirect, unrestricted ingress).
- Both failing policy sets are `overridable: true` — if these were promoted to soft-mandatory they could still be overridden, but today nothing requires override.
