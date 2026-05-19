**Total policies**: 317 | Passed: 308 | Advisory-failed: 9 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-hGthAq8Kuv5wcKZq` — status `applied`, trigger `manual`, auto-apply `true`

### Post Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| poleval-wSxowX2UuPiDSipZ | sentinel | passed | 308 | 9 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | This policy requires resources of type `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| vpc-flow-logging-enabled.sentinel | failed | advisory | This policy requires resources of type `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |

Plus 33 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory | This policy requires `aws_vpc_endpoint` resources to have attribute 'vpc_endpoint_type' to be 'Interface' and 'service_name' to be 'ec2'. |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | This policy requires resources of type `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |

Plus 274 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

No failures. 1 passed policy in this set.
