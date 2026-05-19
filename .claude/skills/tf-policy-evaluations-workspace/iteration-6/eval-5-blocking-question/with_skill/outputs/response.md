**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0 — no policies blocked this run (all 26 failures were advisory).
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`

### Post Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| poleval-qvaFSNdUdasiLqfU | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement |
|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory |
| s3-block-public-access-bucket-level.sentinel | failed | advisory |
| s3-enable-object-logging-for-read-events.sentinel | failed | advisory |
| s3-enable-object-logging-for-write-events.sentinel | failed | advisory |
| s3-require-mfa-delete.sentinel | failed | advisory |
| s3-require-ssl.sentinel | failed | advisory |
| vpc-flow-logging-enabled.sentinel | failed | advisory |

Plus 28 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement |
|---|---|---|
| api-gateway-should-be-associated-with-a-waf-web-acl.sentinel | failed | advisory |
| dynamo-db-tables-delete-protection-enabled.sentinel | failed | advisory |
| ec2-attached-ebs-volumes-encrypted-at-rest.sentinel | failed | advisory |
| ec2-instance-should-not-have-public-ip.sentinel | failed | advisory |
| ec2-instance-virtualization-should-not-be-paravirtual.sentinel | failed | advisory |
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory |
| elb-ensure-deletion-protection-enabled.sentinel | failed | advisory |
| elb-ensure-http-request-redirection.sentinel | failed | advisory |
| redshift-cluster-unrestricted-port-access-check.sentinel | failed | advisory |
| s3-block-public-access-bucket-level.sentinel | failed | advisory |
| s3-bucket-block-public-read-access.sentinel | failed | advisory |
| s3-bucket-block-public-write-access.sentinel | failed | advisory |
| s3-require-ssl.sentinel | failed | advisory |

Plus 262 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

No failures. 1 passed policy in this set.
