**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

### Post-Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| poleval-qvaFSNdUdasiLqfU | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | Verifies `aws_s3_bucket_public_access_block` attributes block public access of an S3 general purpose bucket. |
| s3-enable-object-logging-for-read-events.sentinel | failed | advisory | Requires `aws_s3_bucket` to have object logging enabled for read events. |
| s3-enable-object-logging-for-write-events.sentinel | failed | advisory | Requires `aws_s3_bucket` to have object logging enabled for write events. |
| s3-require-mfa-delete.sentinel | failed | advisory | All general purpose S3 buckets should have MFA delete enabled in their versioning configuration. |
| s3-require-ssl.sentinel | failed | advisory | All requests to `aws_s3_bucket` must use SSL via `aws_s3_bucket_policy`. |
| vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |

Plus 28 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| api-gateway-should-be-associated-with-a-waf-web-acl.sentinel | failed | advisory | Checks whether `aws_api_gateway_stage` uses `aws_wafv2_web_acl_association`. |
| dynamo-db-tables-delete-protection-enabled.sentinel | failed | advisory | Requires `dynamo-db-tables-delete-protection-enabled` attribute of `aws_dynamodb_table` to be true. |
| ec2-attached-ebs-volumes-encrypted-at-rest.sentinel | failed | advisory | Requires `aws_ebs_volume` resources to be encrypted and attached. |
| ec2-instance-should-not-have-public-ip.sentinel | failed | advisory | Requires `aws_instance` to not have a public IP address. |
| ec2-instance-virtualization-should-not-be-paravirtual.sentinel | failed | advisory | Requires `aws_ami` `virtualization_type` to be `hvm`. |
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory | Requires `aws_vpc_endpoint` `vpc_endpoint_type` = `Interface`, `service_name` = `ec2`. |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | Requires `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory | `aws_vpc_endpoint` should be Interface type, referenced to `aws_vpc`. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory | `aws_vpc_endpoint` should be Interface type, referenced to `aws_vpc`. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory | `aws_vpc_endpoint` should be Interface type, referenced to `aws_vpc`. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory | `aws_vpc_endpoint` should be Interface type, referenced to `aws_vpc`. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory | `aws_vpc_endpoint` should be Interface type, referenced to `aws_vpc`. |
| elb-ensure-deletion-protection-enabled.sentinel | failed | advisory | Checks `aws_lb` has `enable_deletion_protection` set to true. |
| elb-ensure-http-request-redirection.sentinel | failed | advisory | ALB should have a listener rule redirecting HTTP to HTTPS. |
| redshift-cluster-unrestricted-port-access-check.sentinel | failed | advisory | Security groups/rules must block ingress from unknown sources to `aws_redshift_cluster`. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | `aws_s3_bucket_public_access_block` attributes must block public access. |
| s3-bucket-block-public-read-access.sentinel | failed | advisory | S3 general purpose buckets should block public read access. |
| s3-bucket-block-public-write-access.sentinel | failed | advisory | S3 general purpose buckets should block public write access. |
| s3-require-ssl.sentinel | failed | advisory | All requests to `aws_s3_bucket` must use SSL via `aws_s3_bucket_policy`. |

Plus 262 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Plus 1 passed policies in this set. No failures.

### Key findings

- Run **applied** successfully — no policy blocked it.
- **No mandatory failures** and no tool errors; all 26 failures are **advisory** (informational only).
- CIS policy set: 7 advisory failures concentrated on S3 hardening (public access, SSL, object logging, MFA delete) and VPC flow logs.
- FSBP policy set: 19 advisory failures — dominant themes are VPC interface endpoints for AWS services, S3 public access/SSL, and EC2/EBS hardening (encryption, public IPs, deletion protection).
