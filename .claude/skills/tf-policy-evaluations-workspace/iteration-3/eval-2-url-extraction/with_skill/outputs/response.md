**Total policies**: 317 | Passed: 291 | Advisory-failed: 26 | Mandatory-failed: 0 | Errored: 0
**Run**: `run-iURWDL3wVxzefsjo` — status `applied`, trigger `manual`, auto-apply `false`

### Post Plan Policy Evaluations (stage status: passed)

| Evaluation | Kind | Status | Passed | Advisory-failed | Mandatory-failed | Errored |
|---|---|---|---|---|---|---|
| poleval-qvaFSNdUdasiLqfU | sentinel | passed | 291 | 26 | 0 | 0 |

#### policy-library-CIS-Policy-Set-for-AWS-Terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | This policy requires resources of type `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | This policy verifies if the attributes of the 'aws_s3_bucket_public_access_block' resource (if present) block public access of an S3 general purpose bucket. |
| s3-enable-object-logging-for-read-events.sentinel | failed | advisory | This policy requires resources of type 'aws_s3_bucket' have object logging enabled for read/write events. |
| s3-enable-object-logging-for-write-events.sentinel | failed | advisory | This policy requires resources of type 'aws_s3_bucket' have object logging enabled for read/write events. |
| s3-require-mfa-delete.sentinel | failed | advisory | This policy verifies that all general purpose S3 buckets should have MFA delete enabled in their versioning configuration. |
| s3-require-ssl.sentinel | failed | advisory | This policy mandates all requests to 'aws_s3_bucket' resources to use SSL using 'aws_s3_bucket_policy' resource. |
| vpc-flow-logging-enabled.sentinel | failed | advisory | This policy requires resources of type `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |

Plus 28 passed policies in this set.

#### policy-library-fsbp-policy-set-for-aws-terraform (0.40.0) — overridable: true

| Policy | Status | Enforcement | Description |
|---|---|---|---|
| api-gateway-should-be-associated-with-a-waf-web-acl.sentinel | failed | advisory | This policy checks whether an 'aws_api_gateway_stage' uses 'aws_wafv2_web_acl_association'. |
| dynamo-db-tables-delete-protection-enabled.sentinel | failed | advisory | This policy requires that `dynamo-db-tables-delete-protection-enabled` attribute of the `aws_dynamodb_table` resource is set to true. |
| ec2-attached-ebs-volumes-encrypted-at-rest.sentinel | failed | advisory | This policy requires `aws_ebs_volume` resources to be encrypted and in attached state. |
| ec2-instance-should-not-have-public-ip.sentinel | failed | advisory | This policy requires resources of type `aws_instance` to not have a public IP address. |
| ec2-instance-virtualization-should-not-be-paravirtual.sentinel | failed | advisory | This policy requires `aws_ami` resources to have attribute 'virtualization_type' to be 'hvm'. |
| ec2-service-vpc-endpoint-enabled.sentinel | failed | advisory | This policy requires `aws_vpc_endpoint` resources to have attribute 'vpc_endpoint_type' to be 'Interface' and 'service_name' to be 'ec2'. |
| ec2-vpc-flow-logging-enabled.sentinel | failed | advisory | This policy requires resources of type `aws_vpc` and `aws_default_vpc` to have flow logs enabled. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-docker-registry.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-ecr-api.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager-contacts.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager-incident-manager.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| ec2-vpc-should-be-configured-for-interface-endpoint-for-systems-manager.sentinel | failed | advisory | This policy requires resources of type `aws_vpc_endpoint` should have 'vpc_endpoint_type' configured with interface endpoint and should be referenced to `aws_vpc` resource. |
| elb-ensure-deletion-protection-enabled.sentinel | failed | advisory | This policy checks if resources of type 'aws_lb' has the 'enable_deletion_protection' attribute set to true. |
| elb-ensure-http-request-redirection.sentinel | failed | advisory | This policy ensures that application load balancer in the terraform configurations have a listener rule configured to redirect HTTP requests to HTTPS. |
| redshift-cluster-unrestricted-port-access-check.sentinel | failed | advisory | This policy requires resources of type `aws_security_group`, `aws_security_group_rule` and `aws_vpc_security_group_ingress_rule` to block ingress traffic from unknown sources to resources of type aws_redshift_cluster. |
| s3-block-public-access-bucket-level.sentinel | failed | advisory | This policy verifies if the attributes of the 'aws_s3_bucket_public_access_block' resource (if present) block public access of an S3 general purpose bucket. |
| s3-bucket-block-public-read-access.sentinel | failed | advisory | S3 general purpose buckets should block public read access. |
| s3-bucket-block-public-write-access.sentinel | failed | advisory | S3 general purpose buckets should block public write access. |
| s3-require-ssl.sentinel | failed | advisory | This policy mandates all requests to 'aws_s3_bucket' resources to use ssl using 'aws_s3_bucket_policy' resource. |

Plus 262 passed policies in this set.

#### hashicorp-sentinel-require-pmr (0.40.0) — overridable: true

Plus 1 passed policies in this set.
