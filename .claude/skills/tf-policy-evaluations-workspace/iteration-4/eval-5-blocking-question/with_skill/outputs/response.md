**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`. No policies blocked the apply: zero mandatory failures, zero soft-mandatory failures, zero errors. All 26 failures were advisory (informational only).

### Post-Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| poleval-qvaFSNdUdasiLqfU | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | Verifies `aws_s3_bucket_public_access_block` blocks public access. |
| s3-enable-object-logging-for-read-events.sentinel | failed | advisory | Requires `aws_s3_bucket` to have object logging enabled for read events. |
| s3-enable-object-logging-for-write-events.sentinel | failed | advisory | Requires `aws_s3_bucket` to have object logging enabled for write events. |
| s3-require-mfa-delete.sentinel | failed | advisory | Requires MFA delete enabled on S3 bucket versioning. |
| s3-require-ssl.sentinel | failed | advisory | Mandates SSL for `aws_s3_bucket` via `aws_s3_bucket_policy`. |
| vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |

Plus 28 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| api-gateway-should-be-associated-with-a-waf-web-acl.sentinel | failed | advisory | Checks `aws_api_gateway_stage` uses `aws_wafv2_web_acl_association`. |
| dynamo-db-tables-delete-protection-enabled.sentinel | failed | advisory | Requires `aws_dynamodb_table` delete protection set to true. |
| ec2-attached-ebs-volumes-encrypted-at-rest.sentinel | failed | advisory | Requires `aws_ebs_volume` encrypted and attached. |
| ec2-instance-should-not-have-public-ip.sentinel | failed | advisory | Requires `aws_instance` to not have a public IP. |
| ec2-instance-virtualization-should-not-be-paravirtual.sentinel | failed | advisory | Requires `aws_ami` `virtualization_type` to be `hvm`. |
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory | Requires `aws_vpc_endpoint` `Interface` type for `ec2` service. |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory | Requires interface VPC endpoint for Docker registry. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory | Requires interface VPC endpoint for ECR API. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory | Requires interface VPC endpoint for SSM Incident Manager Contacts. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory | Requires interface VPC endpoint for SSM Incident Manager. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory | Requires interface VPC endpoint for Systems Manager. |
| elb-ensure-deletion-protection-enabled.sentinel | failed | advisory | Requires `aws_lb` `enable_deletion_protection` set to true. |
| elb-ensure-http-request-redirection.sentinel | failed | advisory | Requires ALB listener rule redirecting HTTP to HTTPS. |
| redshift-cluster-unrestricted-port-access-check.sentinel | failed | advisory | Blocks ingress from unknown sources to `aws_redshift_cluster`. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | Verifies `aws_s3_bucket_public_access_block` blocks public access. |
| s3-bucket-block-public-read-access.sentinel | failed | advisory | S3 buckets should block public read access. |
| s3-bucket-block-public-write-access.sentinel | failed | advisory | S3 buckets should block public write access. |
| s3-require-ssl.sentinel | failed | advisory | Mandates SSL for `aws_s3_bucket` via `aws_s3_bucket_policy`. |

Plus 262 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Zero failures (1 passed policy).
