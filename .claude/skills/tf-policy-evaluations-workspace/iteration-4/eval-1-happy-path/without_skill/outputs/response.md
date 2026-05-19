# Policy Evaluations for run-iURWDL3wVxzefsjo

## Run summary

- **Run ID:** `run-iURWDL3wVxzefsjo`
- **Status:** `applied` (run succeeded)
- **Workspace:** `ws-SiAiPyX8CpKS3MtB`
- **Terraform version:** 1.14.7

## Policy evaluation overview

The run produced a single Sentinel policy evaluation, attached to the `post_plan` task stage (`ts-rEt6yNBSjhxDpKMU`).

| Field | Value |
|---|---|
| Policy evaluation ID | `poleval-qvaFSNdUdasiLqfU` |
| Policy kind | `sentinel` |
| Overall status | **passed** |
| Passed | 291 |
| Advisory failed | 26 |
| Mandatory failed | 0 |
| Errored | 0 |

No OPA evaluations were attached (`/runs/.../tf-policy-evaluations` returned 0 records) and the legacy `/runs/.../policy-checks` endpoint was empty — all policy results came through the modern task-stage / Sentinel pipeline.

Because no mandatory policies failed and there were no errors, the run was **not blocked** by policy. All 26 failures are at the `advisory` enforcement level (informational only).

## Policy set outcomes

| Policy set | Passed | Advisory failed | Mandatory failed | Errored |
|---|---:|---:|---:|---:|
| `policy-library-CIS-Policy-Set-for-AWS-Terraform` | 28 | 7 | 0 | 0 |
| `policy-library-fsbp-policy-set-for-aws-terraform` | 262 | 19 | 0 | 0 |
| `hashicorp-sentinel-require-pmr` | 1 | 0 | 0 | 0 |

## Advisory failures

### policy-library-CIS-Policy-Set-for-AWS-Terraform (7 advisory failures)

| Policy | Description |
|---|---|
| `ec2-vpc-flow-logging-enabled.sentinel` | Requires `aws_vpc` / `aws_default_vpc` to have flow logs enabled. |
| `s3-block-public-access-bucket-level.sentinel` | Requires `aws_s3_bucket_public_access_block` to block public access on S3 buckets. |
| `s3-enable-object-logging-for-read-events.sentinel` | Requires S3 buckets to have object-level read logging enabled. |
| `s3-enable-object-logging-for-write-events.sentinel` | Requires S3 buckets to have object-level write logging enabled. |
| `s3-require-mfa-delete.sentinel` | Requires MFA delete on bucket versioning. |
| `s3-require-ssl.sentinel` | Requires `aws_s3_bucket_policy` to enforce SSL/TLS. |
| `vpc-flow-logging-enabled.sentinel` | Requires VPC flow logs (duplicate baseline check). |

### policy-library-fsbp-policy-set-for-aws-terraform (19 advisory failures)

| Policy | Description |
|---|---|
| `api-gateway-should-be-associated-with-a-waf-web-acl.sentinel` | `aws_api_gateway_stage` should use `aws_wafv2_web_acl_association`. |
| `dynamo-db-tables-delete-protection-enabled.sentinel` | DynamoDB tables must enable delete protection. |
| `ec2-attached-ebs-volumes-encrypted-at-rest.sentinel` | Attached EBS volumes must be encrypted. |
| `ec2-instance-should-not-have-public-ip.sentinel` | EC2 instances must not have a public IP. |
| `ec2-instance-virtualization-should-not-be-paravirtual.sentinel` | AMI `virtualization_type` must be `hvm`. |
| `ec2-service-vpc-endpoint-enabled.sentinel` | Requires an `ec2` interface VPC endpoint. |
| `ec2-vpc-flow-logging-enabled.sentinel` | VPC flow logs required. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel` | Interface VPC endpoint for Docker registry. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel` | Interface VPC endpoint for ECR API. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel` | Interface endpoint for SSM Incident Manager Contacts. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel` | Interface endpoint for SSM Incident Manager. |
| `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel` | Interface endpoint for SSM. |
| `elb-ensure-deletion-protection-enabled.sentinel` | `aws_lb.enable_deletion_protection` must be `true`. |
| `elb-ensure-http-request-redirection.sentinel` | ALB listener must redirect HTTP to HTTPS. |
| `redshift-cluster-unrestricted-port-access-check.sentinel` | Block unrestricted ingress to Redshift clusters. |
| `s3-block-public-access-bucket-level.sentinel` | Block S3 bucket public access. |
| `s3-bucket-block-public-read-access.sentinel` | Block public read on S3 buckets. |
| `s3-bucket-block-public-write-access.sentinel` | Block public write on S3 buckets. |
| `s3-require-ssl.sentinel` | Enforce SSL on S3 bucket policies. |

### hashicorp-sentinel-require-pmr

All 1 policy passed; no failures.

## Bottom line

The policy stage **passed** and did not block the run. However, 26 advisory findings (concentrated on S3 public-access controls, VPC flow logging, EBS encryption, and missing VPC interface endpoints) are worth triaging — particularly the S3 public-access and `s3-require-ssl` findings, which would typically be promoted to `soft-mandatory` or `hard-mandatory` in a hardened policy set.
