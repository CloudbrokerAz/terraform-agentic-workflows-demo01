# Policy Evaluation Results — run-iURWDL3wVxzefsjo

**Workspace:** `terraform-agentic-workflows-demo01` (org: `hashi-demos-apj`)
**Run status:** Succeeded (applied)
**Policy stage outcome:** Passed — no mandatory or errored policies; advisories only.

## Overall summary

| Metric | Count |
|---|---|
| Policy kind | Sentinel |
| Policies passed | 291 |
| Advisory failed | 26 |
| Mandatory failed | 0 |
| Errored | 0 |
| Policy evaluation id | `poleval-qvaFSNdUdasiLqfU` |
| Task stage id | `ts-rEt6yNBSjhxDpKMU` |

Because every failure is `advisory`, the run was not blocked — the apply was confirmed and completed successfully. The advisories should still be triaged.

## Per policy set

| Policy set | Passed | Advisory failed | Mandatory failed | Errored |
|---|---:|---:|---:|---:|
| `policy-library-CIS-Policy-Set-for-AWS-Terraform` | 28 | 7 | 0 | 0 |
| `policy-library-fsbp-policy-set-for-aws-terraform` | 262 | 19 | 0 | 0 |
| `hashicorp-sentinel-require-pmr` | 1 | 0 | 0 | 0 |

## Advisory failures (26)

### CIS policy set (7)
- `ec2-vpc-flow-logging-enabled.sentinel` — VPC / default VPC should have flow logs enabled.
- `vpc-flow-logging-enabled.sentinel` — Same VPC flow-logging requirement (duplicate finding under the CIS pack).
- `s3-block-public-access-bucket-level.sentinel` — S3 bucket-level public-access-block not set / not blocking public access.
- `s3-enable-object-logging-for-read-events.sentinel` — S3 object-level read logging not enabled.
- `s3-enable-object-logging-for-write-events.sentinel` — S3 object-level write logging not enabled.
- `s3-require-mfa-delete.sentinel` — S3 buckets missing MFA-delete on versioning.
- `s3-require-ssl.sentinel` — Bucket policy doesn't force TLS-only access.

### AWS FSBP policy set (19)
- `s3-block-public-access-bucket-level.sentinel`
- `s3-bucket-block-public-read-access.sentinel`
- `s3-bucket-block-public-write-access.sentinel`
- `s3-require-ssl.sentinel`
- `ec2-vpc-flow-logging-enabled.sentinel`
- `ec2-instance-should-not-have-public-ip.sentinel`
- `ec2-instance-virtualization-should-not-be-paravirtual.sentinel`
- `ec2-attached-ebs-volumes-encrypted-at-rest.sentinel`
- `ec2-service-vpc-endpoint-enabled.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel`
- `elb-ensure-deletion-protection-enabled.sentinel`
- `elb-ensure-http-request-redirection.sentinel`
- `api-gateway-should-be-associated-with-a-waf-web-acl.sentinel`
- `dynamo-db-tables-delete-protection-enabled.sentinel`
- `redshift-cluster-unrestricted-port-access-check.sentinel`

### `hashicorp-sentinel-require-pmr` (0)
All policies passed (1/1).

## Themes worth fixing

The advisories cluster into a few recurring gaps:

1. **S3 hardening** — public-access blocks, TLS-only bucket policy, MFA delete, and object-level read/write logging are missing on at least one bucket. Largest single category of findings, flagged by both CIS and FSBP.
2. **VPC flow logs** — flagged three times (CIS x2, FSBP x1); enabling `aws_flow_log` for the VPC closes all three.
3. **EC2 / network hardening** — public-IP instances, unencrypted attached EBS volumes, and missing interface VPC endpoints for EC2/ECR/SSM (FSBP only).
4. **Load balancer & API Gateway** — ELB deletion protection off, missing HTTP-to-HTTPS redirect, API Gateway stage not bound to a WAF web ACL.
5. **Other** — DynamoDB table deletion-protection disabled, Redshift cluster permitting unrestricted port ingress.

## How to dig deeper

Each finding is in `poleval-qvaFSNdUdasiLqfU`'s policy-set outcomes; to inspect any single policy's print output / rule trace:

```bash
tfctl api /policy-evaluations/poleval-qvaFSNdUdasiLqfU/policy-set-outcomes \
  --jq '.data[].attributes.outcomes[] | select(.policy_name=="s3-require-ssl.sentinel")'
```
