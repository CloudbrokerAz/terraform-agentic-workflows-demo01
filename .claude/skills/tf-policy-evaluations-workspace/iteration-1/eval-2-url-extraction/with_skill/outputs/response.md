# Policy Evaluation Results

**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

### Post-Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| `poleval-qvaFSNdUdasiLqfU` | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

Counts: passed 28 | advisory-failed 7 | mandatory-failed 0 | errored 0

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | VPC resources must have flow logs enabled. |
| `s3-block-public-access-bucket-level.sentinel` | failed | advisory | S3 bucket-level public access block must be compliant. |
| `s3-enable-object-logging-for-read-events.sentinel` | failed | advisory | S3 buckets must have object logging for read events. |
| `s3-enable-object-logging-for-write-events.sentinel` | failed | advisory | S3 buckets must have object logging for write events. |
| `s3-require-mfa-delete.sentinel` | failed | advisory | S3 buckets must have MFA delete enabled in versioning. |
| `s3-require-ssl.sentinel` | failed | advisory | S3 buckets must require requests to use SSL. |
| `vpc-flow-logging-enabled.sentinel` | failed | advisory | VPC resources must have flow logging. |

Plus 28 advisory-passed policies.

<details><summary>Violation detail (CIS)</summary>

- `ec2-vpc-flow-logging-enabled` — `module.vpc.aws_vpc.this`, `module.vpc.aws_default_vpc.this` (2 violations)
- `s3-block-public-access-bucket-level` — `module.demo_bucket.aws_s3_bucket.this`
- `s3-enable-object-logging-for-read-events` — `module.demo_bucket.aws_s3_bucket.this[0]`
- `s3-enable-object-logging-for-write-events` — `module.demo_bucket.aws_s3_bucket.this[0]`
- `s3-require-mfa-delete` — `module.demo_bucket.aws_s3_bucket.this`
- `s3-require-ssl` — `module.demo_bucket.aws_s3_bucket.this`
- `vpc-flow-logging-enabled` — `module.vpc.aws_vpc.this`, `module.vpc.aws_default_vpc.this` (2 violations)

</details>

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

Counts: passed 262 | advisory-failed 19 | mandatory-failed 0 | errored 0

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| `api-gateway-should-be-associated-with-a-waf-web-acl.sentinel` | failed | advisory | API Gateway stage should be associated with a WAFv2 web ACL. |
| `dynamo-db-tables-delete-protection-enabled.sentinel` | failed | advisory | `deletion_protection_enabled` must be true on DynamoDB tables. |
| `ec2-attached-ebs-volumes-encrypted-at-rest.sentinel` | failed | advisory | Attached EBS volumes must be encrypted. |
| `ec2-instance-should-not-have-public-ip.sentinel` | failed | advisory | EC2 instances should not have a public IP. |
| `ec2-instance-virtualization-should-not-be-paravirtual.sentinel` | failed | advisory | AMI `virtualization_type` must be `hvm`. |
| `ec2-service-vpc-endpoint-enabled.sentinel` | failed | advisory | VPC endpoint for EC2 service must be configured (interface). |
| `ec2-vpc-flow-logging-enabled.sentinel` | failed | advisory | VPC resources must have flow logging. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel` | failed | advisory | VPC must have interface endpoint for ECR Docker registry. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel` | failed | advisory | VPC must have interface endpoint for ECR API. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel` | failed | advisory | VPC must have interface endpoint for SSM Incident Manager Contacts. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel` | failed | advisory | VPC must have interface endpoint for SSM Incident Manager. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel` | failed | advisory | VPC must have interface endpoint for Systems Manager. |
| `elb-ensure-deletion-protection-enabled.sentinel` | failed | advisory | ALB/NLB/GLB must have deletion protection enabled. |
| `elb-ensure-http-request-redirection.sentinel` | failed | advisory | ALB must redirect HTTP to HTTPS. |
| `redshift-cluster-unrestricted-port-access-check.sentinel` | failed | advisory | Security groups must not allow unrestricted ingress to Redshift port. |
| `s3-block-public-access-bucket-level.sentinel` | failed | advisory | S3 bucket-level public access block must be compliant. |
| `s3-bucket-block-public-read-access.sentinel` | failed | advisory | S3 buckets should block public read access. |
| `s3-bucket-block-public-write-access.sentinel` | failed | advisory | S3 buckets should block public write access. |
| `s3-require-ssl.sentinel` | failed | advisory | S3 buckets must require requests to use SSL. |

Plus 262 advisory-passed policies.

<details><summary>Violation detail (FSBP)</summary>

- `api-gateway-should-be-associated-with-a-waf-web-acl` — `module.alb.aws_wafv2_web_acl_association.this`
- `dynamo-db-tables-delete-protection-enabled` — `module.demo_metadata.aws_dynamodb_table.this[0]`
- `ec2-attached-ebs-volumes-encrypted-at-rest` — `module.app_server.aws_ebs_volume.this`, `module.app_server.aws_volume_attachment.this`
- `ec2-instance-should-not-have-public-ip` — `module.app_server.aws_instance.this[0]`
- `ec2-instance-virtualization-should-not-be-paravirtual` — `module.app_server.aws_instance.this`, `module.app_server.aws_instance.ignore_ami`
- `ec2-service-vpc-endpoint-enabled` — `module.vpc.aws_vpc.this`
- `ec2-vpc-flow-logging-enabled` — `module.vpc.aws_vpc.this`, `module.vpc.aws_default_vpc.this`
- `ec2-vpc-should-be-configured-for-interface-endpoint-*` (5 policies) — `module.vpc.aws_vpc.this`
- `elb-ensure-deletion-protection-enabled` — `module.alb.aws_lb.this[0]`
- `elb-ensure-http-request-redirection` — `module.alb.aws_lb.this[0]`
- `redshift-cluster-unrestricted-port-access-check` — `module.alb.aws_security_group.this[0]`, `module.alb.aws_vpc_security_group_ingress_rule.this["all_http"]`
- `s3-block-public-access-bucket-level` — `module.demo_bucket.aws_s3_bucket.this`
- `s3-bucket-block-public-read-access` — `module.demo_bucket.aws_iam_policy_document.lb_log_delivery[0]`
- `s3-bucket-block-public-write-access` — `module.demo_bucket.aws_iam_policy_document.lb_log_delivery[0]`, `module.demo_bucket.aws_iam_policy_document.elb_log_delivery[0]`
- `s3-require-ssl` — `module.demo_bucket.aws_s3_bucket.this`

</details>

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Counts: passed 1 | advisory-failed 0 | mandatory-failed 0 | errored 0

All policies passed.

### Key findings

- Run **applied** successfully — no policies blocked it; all 26 failures were advisory.
- **CIS baseline**: 7 advisory failures, mostly S3 hardening (`s3-block-public-access`, `s3-require-ssl`, `s3-require-mfa-delete`, S3 object logging) on `module.demo_bucket` and VPC flow logging on `module.vpc`.
- **AWS FSBP baseline**: 19 advisory failures concentrated in VPC (missing flow logs and interface endpoints), EC2 (`module.app_server` — public IP, unencrypted EBS, non-hvm AMI), ALB (deletion protection, HTTP→HTTPS redirect, open ingress), S3 public access controls, and a DynamoDB delete-protection gap.
- No mandatory failures and no tool errors — these are informational signals only; promoting any of these baselines to `soft-mandatory` or `hard-mandatory` would block this run today.
