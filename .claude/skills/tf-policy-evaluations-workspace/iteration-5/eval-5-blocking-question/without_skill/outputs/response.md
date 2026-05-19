# Policy evaluation for `run-iURWDL3wVxzefsjo`

## Answer

**No. No policies blocked this run from applying.** The run completed successfully with status `applied`.

- **Mandatory failures (hard block):** 0
- **Soft-mandatory overridable failures:** 0
- **Errored policies:** 0
- **Advisory failures (non-blocking):** 26

There were no Open Policy Agent (OPA) policy evaluations on this run — only Sentinel.

## Sentinel evaluation summary

Evaluation `poleval-qvaFSNdUdasiLqfU` — status `passed`, kind `sentinel`.

| Result type        | Count |
| ------------------ | ----- |
| Passed             | 291   |
| Advisory failed    | 26    |
| Mandatory failed   | 0     |
| Soft-mandatory failed | 0  |
| Errored            | 0     |

### Per policy set

| Policy set                                              | Passed | Advisory failed | Mandatory failed | Errored |
| ------------------------------------------------------- | -----: | --------------: | ---------------: | ------: |
| `policy-library-CIS-Policy-Set-for-AWS-Terraform`       | 28     | 7               | 0                | 0       |
| `policy-library-fsbp-policy-set-for-aws-terraform`      | 262    | 19              | 0                | 0       |
| `hashicorp-sentinel-require-pmr`                        | 1      | 0               | 0                | 0       |

## The 26 advisory failures (informational only — did not block)

All failures were at `advisory` enforcement level, which surfaces a warning but does not gate the apply.

**CIS policy set (7):**
- `ec2-vpc-flow-logging-enabled.sentinel`
- `s3-block-public-access-bucket-level.sentinel`
- `s3-enable-object-logging-for-read-events.sentinel`
- `s3-enable-object-logging-for-write-events.sentinel`
- `s3-require-mfa-delete.sentinel`
- `s3-require-ssl.sentinel`
- `vpc-flow-logging-enabled.sentinel`

**FSBP policy set (19):**
- `api-gateway-should-be-associated-with-a-waf-web-acl.sentinel`
- `dynamo-db-tables-delete-protection-enabled.sentinel`
- `ec2-attached-ebs-volumes-encrypted-at-rest.sentinel`
- `ec2-instance-should-not-have-public-ip.sentinel`
- `ec2-instance-virtualization-should-not-be-paravirtual.sentinel`
- `ec2-service-vpc-endpoint-enabled.sentinel`
- `ec2-vpc-flow-logging-enabled.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel`
- `ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel`
- `elb-ensure-deletion-protection-enabled.sentinel`
- `elb-ensure-http-request-redirection.sentinel`
- `redshift-cluster-unrestricted-port-access-check.sentinel`
- `s3-block-public-access-bucket-level.sentinel`
- `s3-bucket-block-public-read-access.sentinel`
- `s3-bucket-block-public-write-access.sentinel`
- `s3-require-ssl.sentinel`

## Bottom line

Nothing was mandatory, nothing was soft-mandatory, nothing errored. The 26 advisory findings are best-practice signals worth triaging (S3 public-access blocks, SSL enforcement, VPC flow logging, EBS encryption, etc.) but they did not — and could not — prevent this run from applying.
