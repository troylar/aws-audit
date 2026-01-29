"""AWS resource deletion strategies.

Maps AWS resource types to their deletion methods with proper error handling
and retry logic. Handles prerequisite cleanup for resources that require it
(e.g., emptying S3 buckets, detaching IAM policies).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from botocore.exceptions import ClientError

from src.aws.client import create_boto_client

logger = logging.getLogger(__name__)

# Resource types that require prerequisite cleanup before deletion
RESOURCES_WITH_PREREQUISITES = {
    "AWS::S3::Bucket",
    "AWS::IAM::Role",
    "AWS::IAM::User",
    "AWS::IAM::Policy",
    "AWS::Events::Rule",
    "AWS::Route53::HostedZone",
    "AWS::Backup::BackupVault",
    "AWS::WAFv2::WebACL",
    "AWS::WAFv2::RuleGroup",
}


class ResourceDeleter:
    """AWS resource deletion orchestrator.

    Handles deletion of various AWS resource types using appropriate boto3 API calls.
    Implements retry logic and error handling for safe resource cleanup.
    """

    # Deletion method mapping: resource_type -> (service, method, id_field)
    DELETION_METHODS = {
        # EC2 Resources
        "AWS::EC2::Instance": ("ec2", "terminate_instances", "InstanceIds"),
        "AWS::EC2::SecurityGroup": ("ec2", "delete_security_group", "GroupId"),
        "AWS::EC2::Volume": ("ec2", "delete_volume", "VolumeId"),
        "AWS::EC2::VPC": ("ec2", "delete_vpc", "VpcId"),
        "AWS::EC2::Subnet": ("ec2", "delete_subnet", "SubnetId"),
        "AWS::EC2::InternetGateway": ("ec2", "delete_internet_gateway", "InternetGatewayId"),
        "AWS::EC2::RouteTable": ("ec2", "delete_route_table", "RouteTableId"),
        "AWS::EC2::NetworkInterface": ("ec2", "delete_network_interface", "NetworkInterfaceId"),
        "AWS::EC2::KeyPair": ("ec2", "delete_key_pair", "KeyName"),
        # S3
        "AWS::S3::Bucket": ("s3", "delete_bucket", "Bucket"),
        # Lambda
        "AWS::Lambda::Function": ("lambda", "delete_function", "FunctionName"),
        # DynamoDB
        "AWS::DynamoDB::Table": ("dynamodb", "delete_table", "TableName"),
        # RDS
        "AWS::RDS::DBInstance": ("rds", "delete_db_instance", "DBInstanceIdentifier"),
        "AWS::RDS::DBCluster": ("rds", "delete_db_cluster", "DBClusterIdentifier"),
        # IAM
        "AWS::IAM::Role": ("iam", "delete_role", "RoleName"),
        "AWS::IAM::User": ("iam", "delete_user", "UserName"),
        "AWS::IAM::Policy": ("iam", "delete_policy", "PolicyArn"),
        # ECS
        "AWS::ECS::Service": ("ecs", "delete_service", "service"),
        "AWS::ECS::Cluster": ("ecs", "delete_cluster", "cluster"),
        "AWS::ECS::TaskDefinition": ("ecs", "deregister_task_definition", "taskDefinition"),
        # EKS
        "AWS::EKS::Cluster": ("eks", "delete_cluster", "name"),
        # SNS
        "AWS::SNS::Topic": ("sns", "delete_topic", "TopicArn"),
        # SQS
        "AWS::SQS::Queue": ("sqs", "delete_queue", "QueueUrl"),
        # CloudWatch
        "AWS::CloudWatch::Alarm": ("cloudwatch", "delete_alarms", "AlarmNames"),
        # API Gateway
        "AWS::ApiGateway::RestApi": ("apigateway", "delete_rest_api", "restApiId"),
        # KMS
        "AWS::KMS::Key": ("kms", "schedule_key_deletion", "KeyId"),
        # Secrets Manager
        "AWS::SecretsManager::Secret": ("secretsmanager", "delete_secret", "SecretId"),
        # ELB
        "AWS::ElasticLoadBalancing::LoadBalancer": ("elb", "delete_load_balancer", "LoadBalancerName"),
        "AWS::ElasticLoadBalancingV2::LoadBalancer": ("elbv2", "delete_load_balancer", "LoadBalancerArn"),
        # EFS
        "AWS::EFS::FileSystem": ("efs", "delete_file_system", "FileSystemId"),
        # ElastiCache
        "AWS::ElastiCache::CacheCluster": ("elasticache", "delete_cache_cluster", "CacheClusterId"),
        # SSM
        "AWS::SSM::Parameter": ("ssm", "delete_parameter", "Name"),
        # Step Functions
        "AWS::StepFunctions::StateMachine": ("sfn", "delete_state_machine", "stateMachineArn"),
        # EventBridge
        "AWS::Events::Rule": ("events", "delete_rule", "Name"),
        # CodeBuild
        "AWS::CodeBuild::Project": ("codebuild", "delete_project", "name"),
        # VPC Endpoints
        "AWS::EC2::VPCEndpoint": ("ec2", "delete_vpc_endpoints", "VpcEndpointIds"),
        # CodePipeline
        "AWS::CodePipeline::Pipeline": ("codepipeline", "delete_pipeline", "name"),
        # CloudFormation
        "AWS::CloudFormation::Stack": ("cloudformation", "delete_stack", "StackName"),
        # Glue
        "AWS::Glue::Job": ("glue", "delete_job", "JobName"),
        "AWS::Glue::Database": ("glue", "delete_database", "Name"),
        "AWS::Glue::Crawler": ("glue", "delete_crawler", "Name"),
        # Route53
        "AWS::Route53::HostedZone": ("route53", "delete_hosted_zone", "Id"),
        # Backup
        "AWS::Backup::BackupPlan": ("backup", "delete_backup_plan", "BackupPlanId"),
        "AWS::Backup::BackupVault": ("backup", "delete_backup_vault", "BackupVaultName"),
        # WAF
        "AWS::WAFv2::WebACL": ("wafv2", "delete_web_acl", "Id"),
        "AWS::WAFv2::RuleGroup": ("wafv2", "delete_rule_group", "Id"),
    }

    def __init__(self, aws_profile: Optional[str] = None, max_retries: int = 3):
        """Initialize resource deleter.

        Args:
            aws_profile: AWS profile name (optional)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.aws_profile = aws_profile
        self.max_retries = max_retries

    def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
        region: str,
        arn: str,
    ) -> tuple[bool, Optional[str], bool]:
        """Delete an AWS resource.

        Args:
            resource_type: AWS resource type (e.g., "AWS::EC2::Instance")
            resource_id: Resource identifier
            region: AWS region
            arn: Resource ARN

        Returns:
            Tuple of (success: bool, error_message: Optional[str], was_skipped: bool)
            - success: True if resource is gone (deleted or already didn't exist)
            - error_message: Error details if failed
            - was_skipped: True if resource was already deleted/not found
        """
        # Check if we support this resource type
        if resource_type not in self.DELETION_METHODS:
            error_msg = f"Unsupported resource type: {resource_type}"
            logger.warning(error_msg)
            return (False, error_msg, False)

        service, method, id_field = self.DELETION_METHODS[resource_type]

        # Try deletion with retries
        for attempt in range(self.max_retries):
            try:
                success, error, was_skipped = self._attempt_deletion(
                    service=service,
                    method=method,
                    id_field=id_field,
                    resource_id=resource_id,
                    resource_type=resource_type,
                    region=region,
                    arn=arn,
                )

                if success:
                    if was_skipped:
                        logger.info(f"Resource {resource_type}: {resource_id} already deleted")
                    else:
                        logger.info(f"Successfully deleted {resource_type}: {resource_id}")
                    return (True, None, was_skipped)
                elif "DependencyViolation" in (error or ""):
                    # Dependency violations should be retried
                    if attempt < self.max_retries - 1:
                        wait_time = 2**attempt  # Exponential backoff
                        logger.debug(
                            f"Dependency violation for {resource_id}, "
                            f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                else:
                    # Non-retryable error
                    return (False, error, False)

            except Exception as e:
                error_msg = f"Unexpected error deleting {resource_type} {resource_id}: {str(e)}"
                logger.error(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                return (False, error_msg, False)

        # All retries exhausted
        error_msg = f"Failed to delete {resource_type} {resource_id} after {self.max_retries} attempts"
        logger.error(error_msg)
        return (False, error_msg, False)

    def _attempt_deletion(
        self,
        service: str,
        method: str,
        id_field: str,
        resource_id: str,
        resource_type: str,
        region: str,
        arn: str,
    ) -> tuple[bool, Optional[str], bool]:
        """Attempt a single deletion operation.

        Args:
            service: AWS service name
            method: Boto3 method name
            id_field: Parameter name for resource ID
            resource_id: Resource identifier
            resource_type: AWS resource type
            region: AWS region
            arn: Resource ARN

        Returns:
            Tuple of (success: bool, error_message: Optional[str], was_skipped: bool)
        """
        try:
            # Run prerequisite cleanup if needed (e.g., empty S3 bucket, detach IAM policies)
            prep_success, prep_error = self._prepare_for_deletion(
                resource_type=resource_type,
                resource_id=resource_id,
                region=region,
                arn=arn,
            )
            if not prep_success:
                return (False, prep_error, False)

            # Create boto3 client for the service
            client = create_boto_client(
                service_name=service,
                region_name=region,
                profile_name=self.aws_profile,
            )

            # Build parameters based on resource type
            params = self._build_deletion_params(
                resource_type=resource_type,
                id_field=id_field,
                resource_id=resource_id,
                arn=arn,
            )

            # Call the deletion method
            deletion_method = getattr(client, method)
            deletion_method(**params)

            return (True, None, False)  # Actually deleted

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            # Handle specific error cases
            if error_code in [
                "InvalidInstanceID.NotFound",
                "NoSuchEntity",
                "ResourceNotFoundException",
                "WAFNonexistentItemException",
                "NoSuchHostedZone",
                "NonExistentQueue",  # SQS queue already deleted
                "QueueDoesNotExist",  # SQS alternative error code
                "AWS.SimpleQueueService.NonExistentQueue",  # SQS full error code
                "DBInstanceNotFound",  # RDS instance already deleted
                "DBClusterNotFoundFault",  # RDS cluster already deleted
                "EntityNotFoundException",  # Glue/generic entity not found
            ]:
                # Resource already deleted
                logger.info(f"Resource {resource_id} already deleted")
                return (True, None, True)  # Skipped - already gone
            elif error_code == "InvalidDBInstanceState":
                # RDS instance already being deleted
                if "already being deleted" in error_message.lower():
                    logger.info(f"RDS instance {resource_id} already being deleted")
                    return (True, None, True)  # Skipped - already being deleted
                return (False, f"{error_code}: {error_message}", False)
            elif error_code == "InvalidRequestException":
                # Handle Secrets Manager secrets owned by RDS
                if "owned by" in error_message.lower():
                    logger.info(f"Secret {resource_id} is managed by another service, skipping")
                    return (True, None, True)  # Skipped - managed by another service
                return (False, f"{error_code}: {error_message}", False)
            elif error_code == "DependencyViolation":
                # Dependencies still exist
                logger.debug(f"Dependency violation for {resource_id}: {error_message}")
                return (False, f"DependencyViolation: {error_message}", False)
            else:
                # Other client errors
                logger.error(f"Failed to delete {resource_id}: {error_code} - {error_message}")
                return (False, f"{error_code}: {error_message}", False)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Failed to delete {resource_id}: {error_msg}")
            return (False, error_msg, False)

    def _build_deletion_params(
        self,
        resource_type: str,
        id_field: str,
        resource_id: str,
        arn: str,
    ) -> dict[str, Any]:
        """Build deletion parameters for boto3 call.

        Args:
            resource_type: AWS resource type
            id_field: Parameter name for resource ID
            resource_id: Resource identifier
            arn: Resource ARN

        Returns:
            Dictionary of parameters for boto3 method call
        """
        # Handle list parameters (e.g., InstanceIds, AlarmNames)
        if id_field.endswith("s"):  # Plural form indicates list
            return {id_field: [resource_id]}

        # Handle ARN-based parameters
        if "Arn" in id_field:
            return {id_field: arn}

        # Handle special cases
        if resource_type == "AWS::RDS::DBInstance":
            # Skip final snapshot for faster deletion
            return {
                id_field: resource_id,
                "SkipFinalSnapshot": True,
                "DeleteAutomatedBackups": True,
            }
        elif resource_type == "AWS::RDS::DBCluster":
            # Skip final snapshot for faster deletion
            return {
                id_field: resource_id,
                "SkipFinalSnapshot": True,
            }
        elif resource_type == "AWS::KMS::Key":
            # Schedule deletion with minimum waiting period
            return {
                id_field: resource_id,
                "PendingWindowInDays": 7,
            }
        elif resource_type == "AWS::SecretsManager::Secret":
            # Immediate deletion (no recovery window)
            return {
                id_field: resource_id,
                "ForceDeleteWithoutRecovery": True,
            }

        # Standard parameter
        return {id_field: resource_id}

    def _prepare_for_deletion(
        self,
        resource_type: str,
        resource_id: str,
        region: str,
        arn: str,
    ) -> tuple[bool, Optional[str]]:
        """Run prerequisite cleanup before resource deletion.

        Some resources require cleanup before they can be deleted (e.g., S3 buckets
        must be emptied, IAM roles must have policies detached).

        Args:
            resource_type: AWS resource type
            resource_id: Resource identifier
            region: AWS region
            arn: Resource ARN

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if resource_type not in RESOURCES_WITH_PREREQUISITES:
            return (True, None)

        try:
            if resource_type == "AWS::S3::Bucket":
                return self._empty_s3_bucket(resource_id, region)
            elif resource_type == "AWS::IAM::Role":
                return self._cleanup_iam_role(resource_id)
            elif resource_type == "AWS::IAM::User":
                return self._cleanup_iam_user(resource_id)
            elif resource_type == "AWS::IAM::Policy":
                return self._cleanup_iam_policy(arn)
            elif resource_type == "AWS::Events::Rule":
                return self._cleanup_eventbridge_rule(resource_id, region)
            elif resource_type == "AWS::Route53::HostedZone":
                return self._cleanup_route53_hosted_zone(resource_id)
            elif resource_type == "AWS::Backup::BackupVault":
                return self._cleanup_backup_vault(resource_id)
            elif resource_type == "AWS::WAFv2::WebACL":
                return self._cleanup_waf_webacl(resource_id, arn, region)
            elif resource_type == "AWS::WAFv2::RuleGroup":
                return self._cleanup_waf_rulegroup(resource_id, arn, region)
        except Exception as e:
            error_msg = f"Prerequisite cleanup failed for {resource_type} {resource_id}: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)

        return (True, None)

    def _empty_s3_bucket(self, bucket_name: str, region: str) -> tuple[bool, Optional[str]]:
        """Empty an S3 bucket before deletion.

        Handles both versioned and non-versioned buckets by deleting all objects,
        versions, and delete markers.

        Args:
            bucket_name: Name of the S3 bucket
            region: AWS region (used for client creation)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            s3_client = create_boto_client(
                service_name="s3",
                region_name=region,
                profile_name=self.aws_profile,
            )

            # Check if bucket has object lock (cannot empty these buckets easily)
            try:
                lock_config = s3_client.get_object_lock_configuration(Bucket=bucket_name)
                if lock_config.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") == "Enabled":
                    return (False, "Bucket has Object Lock enabled - cannot empty automatically")
            except ClientError as e:
                # ObjectLockConfigurationNotFoundError means no lock - that's fine
                if e.response.get("Error", {}).get("Code") != "ObjectLockConfigurationNotFoundError":
                    raise

            deleted_count = 0

            # Delete all object versions (handles versioned buckets)
            paginator = s3_client.get_paginator("list_object_versions")
            try:
                for page in paginator.paginate(Bucket=bucket_name):
                    objects_to_delete = []

                    # Collect versions
                    for version in page.get("Versions", []):
                        objects_to_delete.append(
                            {
                                "Key": version["Key"],
                                "VersionId": version["VersionId"],
                            }
                        )

                    # Collect delete markers
                    for marker in page.get("DeleteMarkers", []):
                        objects_to_delete.append(
                            {
                                "Key": marker["Key"],
                                "VersionId": marker["VersionId"],
                            }
                        )

                    if objects_to_delete:
                        # Batch delete (max 1000 per request)
                        for i in range(0, len(objects_to_delete), 1000):
                            batch = objects_to_delete[i : i + 1000]
                            s3_client.delete_objects(
                                Bucket=bucket_name,
                                Delete={"Objects": batch, "Quiet": True},
                            )
                            deleted_count += len(batch)

            except ClientError as e:
                # If versioning was never enabled, fall back to simple object listing
                if e.response.get("Error", {}).get("Code") == "NoSuchBucket":
                    return (True, None)  # Bucket already gone

                # Try non-versioned approach
                paginator = s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket_name):
                    objects_to_delete = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]

                    if objects_to_delete:
                        for i in range(0, len(objects_to_delete), 1000):
                            batch = objects_to_delete[i : i + 1000]
                            s3_client.delete_objects(
                                Bucket=bucket_name,
                                Delete={"Objects": batch, "Quiet": True},
                            )
                            deleted_count += len(batch)

            logger.info(f"Emptied S3 bucket {bucket_name}: deleted {deleted_count} objects/versions")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchBucket":
                return (True, None)  # Bucket already deleted

            return (False, f"Failed to empty bucket: {error_code}: {error_message}")

    def _cleanup_iam_role(self, role_name: str) -> tuple[bool, Optional[str]]:
        """Clean up IAM role before deletion.

        Detaches managed policies, deletes inline policies, and removes the role
        from any instance profiles.

        Args:
            role_name: Name of the IAM role

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            iam_client = create_boto_client(
                service_name="iam",
                region_name="us-east-1",  # IAM is global
                profile_name=self.aws_profile,
            )

            # 1. Detach all managed policies
            paginator = iam_client.get_paginator("list_attached_role_policies")
            for page in paginator.paginate(RoleName=role_name):
                for policy in page.get("AttachedPolicies", []):
                    iam_client.detach_role_policy(
                        RoleName=role_name,
                        PolicyArn=policy["PolicyArn"],
                    )
                    logger.debug(f"Detached policy {policy['PolicyArn']} from role {role_name}")

            # 2. Delete all inline policies
            paginator = iam_client.get_paginator("list_role_policies")
            for page in paginator.paginate(RoleName=role_name):
                for policy_name in page.get("PolicyNames", []):
                    iam_client.delete_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name,
                    )
                    logger.debug(f"Deleted inline policy {policy_name} from role {role_name}")

            # 3. Remove role from all instance profiles
            paginator = iam_client.get_paginator("list_instance_profiles_for_role")
            for page in paginator.paginate(RoleName=role_name):
                for profile in page.get("InstanceProfiles", []):
                    iam_client.remove_role_from_instance_profile(
                        InstanceProfileName=profile["InstanceProfileName"],
                        RoleName=role_name,
                    )
                    logger.debug(f"Removed role {role_name} from instance profile {profile['InstanceProfileName']}")

            logger.info(f"Cleaned up IAM role {role_name} for deletion")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchEntity":
                return (True, None)  # Role already deleted

            return (False, f"Failed to cleanup IAM role: {error_code}: {error_message}")

    def _cleanup_iam_user(self, user_name: str) -> tuple[bool, Optional[str]]:
        """Clean up IAM user before deletion.

        Removes access keys, MFA devices, signing certificates, SSH keys,
        service-specific credentials, detaches policies, deletes inline policies,
        and removes from groups.

        Args:
            user_name: Name of the IAM user

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            iam_client = create_boto_client(
                service_name="iam",
                region_name="us-east-1",  # IAM is global
                profile_name=self.aws_profile,
            )

            # 1. Delete access keys
            paginator = iam_client.get_paginator("list_access_keys")
            for page in paginator.paginate(UserName=user_name):
                for key in page.get("AccessKeyMetadata", []):
                    iam_client.delete_access_key(
                        UserName=user_name,
                        AccessKeyId=key["AccessKeyId"],
                    )
                    logger.debug(f"Deleted access key {key['AccessKeyId']} for user {user_name}")

            # 2. Deactivate and delete MFA devices
            paginator = iam_client.get_paginator("list_mfa_devices")
            for page in paginator.paginate(UserName=user_name):
                for device in page.get("MFADevices", []):
                    iam_client.deactivate_mfa_device(
                        UserName=user_name,
                        SerialNumber=device["SerialNumber"],
                    )
                    # Only delete virtual MFA devices (not hardware)
                    if "arn:aws:iam::" in device["SerialNumber"] and "mfa/" in device["SerialNumber"]:
                        try:
                            iam_client.delete_virtual_mfa_device(
                                SerialNumber=device["SerialNumber"],
                            )
                        except ClientError:
                            pass  # May fail for hardware devices
                    logger.debug(f"Deactivated MFA device {device['SerialNumber']} for user {user_name}")

            # 3. Delete signing certificates
            paginator = iam_client.get_paginator("list_signing_certificates")
            for page in paginator.paginate(UserName=user_name):
                for cert in page.get("Certificates", []):
                    iam_client.delete_signing_certificate(
                        UserName=user_name,
                        CertificateId=cert["CertificateId"],
                    )
                    logger.debug(f"Deleted signing certificate {cert['CertificateId']} for user {user_name}")

            # 4. Delete SSH public keys
            paginator = iam_client.get_paginator("list_ssh_public_keys")
            for page in paginator.paginate(UserName=user_name):
                for key in page.get("SSHPublicKeys", []):
                    iam_client.delete_ssh_public_key(
                        UserName=user_name,
                        SSHPublicKeyId=key["SSHPublicKeyId"],
                    )
                    logger.debug(f"Deleted SSH key {key['SSHPublicKeyId']} for user {user_name}")

            # 5. Delete service-specific credentials
            try:
                response = iam_client.list_service_specific_credentials(UserName=user_name)
                for cred in response.get("ServiceSpecificCredentials", []):
                    iam_client.delete_service_specific_credential(
                        UserName=user_name,
                        ServiceSpecificCredentialId=cred["ServiceSpecificCredentialId"],
                    )
                    cred_id = cred["ServiceSpecificCredentialId"]
                    logger.debug(f"Deleted service credential {cred_id} for user {user_name}")
            except ClientError:
                pass  # Service-specific credentials may not exist

            # 6. Detach managed policies
            paginator = iam_client.get_paginator("list_attached_user_policies")
            for page in paginator.paginate(UserName=user_name):
                for policy in page.get("AttachedPolicies", []):
                    iam_client.detach_user_policy(
                        UserName=user_name,
                        PolicyArn=policy["PolicyArn"],
                    )
                    logger.debug(f"Detached policy {policy['PolicyArn']} from user {user_name}")

            # 7. Delete inline policies
            paginator = iam_client.get_paginator("list_user_policies")
            for page in paginator.paginate(UserName=user_name):
                for policy_name in page.get("PolicyNames", []):
                    iam_client.delete_user_policy(
                        UserName=user_name,
                        PolicyName=policy_name,
                    )
                    logger.debug(f"Deleted inline policy {policy_name} from user {user_name}")

            # 8. Remove user from all groups
            paginator = iam_client.get_paginator("list_groups_for_user")
            for page in paginator.paginate(UserName=user_name):
                for group in page.get("Groups", []):
                    iam_client.remove_user_from_group(
                        GroupName=group["GroupName"],
                        UserName=user_name,
                    )
                    logger.debug(f"Removed user {user_name} from group {group['GroupName']}")

            # 9. Delete login profile (console password)
            try:
                iam_client.delete_login_profile(UserName=user_name)
                logger.debug(f"Deleted login profile for user {user_name}")
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") != "NoSuchEntity":
                    raise  # Re-raise if not "already deleted"

            logger.info(f"Cleaned up IAM user {user_name} for deletion")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchEntity":
                return (True, None)  # User already deleted

            return (False, f"Failed to cleanup IAM user: {error_code}: {error_message}")

    def _cleanup_iam_policy(self, policy_arn: str) -> tuple[bool, Optional[str]]:
        """Delete all non-default versions of an IAM policy before deletion.

        IAM policies with multiple versions cannot be deleted until all non-default
        versions are removed first. The default version is deleted with the policy.

        Args:
            policy_arn: ARN of the IAM policy

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            iam_client = create_boto_client(
                service_name="iam",
                region_name="us-east-1",  # IAM is global
                profile_name=self.aws_profile,
            )

            # List all policy versions
            paginator = iam_client.get_paginator("list_policy_versions")
            for page in paginator.paginate(PolicyArn=policy_arn):
                for version in page.get("Versions", []):
                    # Skip the default version - it's deleted with the policy
                    if not version.get("IsDefaultVersion", False):
                        iam_client.delete_policy_version(
                            PolicyArn=policy_arn,
                            VersionId=version["VersionId"],
                        )
                        logger.debug(f"Deleted policy version {version['VersionId']} for {policy_arn}")

            logger.info(f"Cleaned up IAM policy versions for {policy_arn}")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchEntity":
                return (True, None)  # Policy already deleted

            return (False, f"Failed to cleanup IAM policy versions: {error_code}: {error_message}")

    def _cleanup_eventbridge_rule(self, rule_name: str, region: str) -> tuple[bool, Optional[str]]:
        """Remove all targets from an EventBridge rule before deletion.

        EventBridge rules cannot be deleted if they have targets attached.
        This method removes all targets first.

        Args:
            rule_name: Name of the EventBridge rule
            region: AWS region

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            events_client = create_boto_client(
                service_name="events",
                region_name=region,
                profile_name=self.aws_profile,
            )

            # List all targets for this rule
            targets_to_remove = []
            paginator = events_client.get_paginator("list_targets_by_rule")

            try:
                for page in paginator.paginate(Rule=rule_name):
                    for target in page.get("Targets", []):
                        targets_to_remove.append(target["Id"])
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                    return (True, None)  # Rule already deleted
                raise

            # Remove targets in batches of 10 (API limit)
            if targets_to_remove:
                for i in range(0, len(targets_to_remove), 10):
                    batch = targets_to_remove[i : i + 10]
                    events_client.remove_targets(
                        Rule=rule_name,
                        Ids=batch,
                    )
                    logger.debug(f"Removed {len(batch)} targets from rule {rule_name}")

            logger.info(f"Cleaned up EventBridge rule {rule_name}: removed {len(targets_to_remove)} targets")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "ResourceNotFoundException":
                return (True, None)  # Rule already deleted

            return (False, f"Failed to cleanup EventBridge rule: {error_code}: {error_message}")

    def _cleanup_route53_hosted_zone(self, zone_id: str) -> tuple[bool, Optional[str]]:
        """Delete all records from a Route53 hosted zone before deletion.

        Route53 hosted zones cannot be deleted if they contain records other than
        the default NS and SOA records. This method deletes all other records first.

        Args:
            zone_id: Hosted zone ID (with or without /hostedzone/ prefix)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            route53_client = create_boto_client(
                service_name="route53",
                region_name="us-east-1",  # Route53 is global
                profile_name=self.aws_profile,
            )

            # Normalize zone ID (remove /hostedzone/ prefix if present)
            if zone_id.startswith("/hostedzone/"):
                zone_id = zone_id.replace("/hostedzone/", "")

            # List all records in the zone
            records_to_delete = []
            paginator = route53_client.get_paginator("list_resource_record_sets")

            try:
                for page in paginator.paginate(HostedZoneId=zone_id):
                    for record in page.get("ResourceRecordSets", []):
                        # Skip NS and SOA records at zone apex (cannot be deleted)
                        if record["Type"] in ["NS", "SOA"]:
                            continue
                        records_to_delete.append(record)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "NoSuchHostedZone":
                    return (True, None)  # Zone already deleted
                raise

            # Delete records in batches
            if records_to_delete:
                # Route53 allows up to 1000 changes per request
                for i in range(0, len(records_to_delete), 100):
                    batch = records_to_delete[i : i + 100]
                    changes = [{"Action": "DELETE", "ResourceRecordSet": record} for record in batch]
                    route53_client.change_resource_record_sets(
                        HostedZoneId=zone_id,
                        ChangeBatch={"Changes": changes},
                    )
                    logger.debug(f"Deleted {len(batch)} records from zone {zone_id}")

            logger.info(f"Cleaned up Route53 zone {zone_id}: deleted {len(records_to_delete)} records")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchHostedZone":
                return (True, None)  # Zone already deleted

            return (False, f"Failed to cleanup Route53 zone: {error_code}: {error_message}")

    def _cleanup_backup_vault(self, vault_name: str) -> tuple[bool, Optional[str]]:
        """Delete all recovery points from a Backup vault before deletion.

        Backup vaults cannot be deleted if they contain recovery points.
        This method deletes all recovery points first.

        Args:
            vault_name: Name of the backup vault

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            backup_client = create_boto_client(
                service_name="backup",
                region_name="us-east-1",  # Will be overridden by the vault's region
                profile_name=self.aws_profile,
            )

            # List all recovery points in the vault
            recovery_points = []
            paginator = backup_client.get_paginator("list_recovery_points_by_backup_vault")

            try:
                for page in paginator.paginate(BackupVaultName=vault_name):
                    for rp in page.get("RecoveryPoints", []):
                        recovery_points.append(rp["RecoveryPointArn"])
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ["ResourceNotFoundException", "AccessDeniedException"]:
                    return (True, None)  # Vault already deleted or no access
                raise

            # Delete each recovery point
            for rp_arn in recovery_points:
                try:
                    backup_client.delete_recovery_point(
                        BackupVaultName=vault_name,
                        RecoveryPointArn=rp_arn,
                    )
                    logger.debug(f"Deleted recovery point {rp_arn} from vault {vault_name}")
                except ClientError as e:
                    # Continue on individual failures
                    logger.warning(f"Failed to delete recovery point {rp_arn}: {e}")

            logger.info(f"Cleaned up Backup vault {vault_name}: deleted {len(recovery_points)} recovery points")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "ResourceNotFoundException":
                return (True, None)  # Vault already deleted

            return (False, f"Failed to cleanup Backup vault: {error_code}: {error_message}")

    def _cleanup_waf_webacl(self, webacl_id: str, arn: str, region: str) -> tuple[bool, Optional[str]]:
        """Disassociate all resources from a WAF WebACL and delete it.

        WAF WebACLs cannot be deleted if they are associated with resources.
        This method disassociates all resources and then deletes the WebACL.
        The deletion is done here because it requires a LockToken.

        Args:
            webacl_id: WebACL ID
            arn: WebACL ARN
            region: AWS region

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Determine scope from ARN
            scope = "CLOUDFRONT" if "global" in arn or "cloudfront" in arn.lower() else "REGIONAL"
            waf_region = "us-east-1" if scope == "CLOUDFRONT" else region

            wafv2_client = create_boto_client(
                service_name="wafv2",
                region_name=waf_region,
                profile_name=self.aws_profile,
            )

            # Extract name from ARN (format: ...webacl/name/id)
            arn_parts = arn.split("/")
            webacl_name = arn_parts[-2] if len(arn_parts) >= 2 else webacl_id

            # Get WebACL to retrieve LockToken
            try:
                response = wafv2_client.get_web_acl(Name=webacl_name, Scope=scope, Id=webacl_id)
                lock_token = response["LockToken"]
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "WAFNonexistentItemException":
                    return (True, None)  # WebACL already deleted
                raise

            # Disassociate from all resources (only for REGIONAL scope)
            if scope == "REGIONAL":
                try:
                    resources = wafv2_client.list_resources_for_web_acl(
                        WebACLArn=arn, ResourceType="APPLICATION_LOAD_BALANCER"
                    )
                    for resource_arn in resources.get("ResourceArns", []):
                        wafv2_client.disassociate_web_acl(ResourceArn=resource_arn)
                        logger.debug(f"Disassociated {resource_arn} from WebACL {webacl_name}")
                except ClientError:
                    pass  # May not have associations

                # Also check API Gateway
                try:
                    resources = wafv2_client.list_resources_for_web_acl(WebACLArn=arn, ResourceType="API_GATEWAY")
                    for resource_arn in resources.get("ResourceArns", []):
                        wafv2_client.disassociate_web_acl(ResourceArn=resource_arn)
                        logger.debug(f"Disassociated {resource_arn} from WebACL {webacl_name}")
                except ClientError:
                    pass

            # Delete the WebACL
            wafv2_client.delete_web_acl(
                Name=webacl_name,
                Scope=scope,
                Id=webacl_id,
                LockToken=lock_token,
            )

            logger.info(f"Deleted WAF WebACL {webacl_name}")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "WAFNonexistentItemException":
                return (True, None)  # WebACL already deleted

            return (False, f"Failed to cleanup WAF WebACL: {error_code}: {error_message}")

    def _cleanup_waf_rulegroup(self, rulegroup_id: str, arn: str, region: str) -> tuple[bool, Optional[str]]:
        """Delete a WAF RuleGroup (requires LockToken).

        WAF RuleGroup deletion requires a LockToken obtained from get_rule_group.
        This method handles the full deletion.

        Args:
            rulegroup_id: RuleGroup ID
            arn: RuleGroup ARN
            region: AWS region

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Determine scope from ARN
            scope = "CLOUDFRONT" if "global" in arn or "cloudfront" in arn.lower() else "REGIONAL"
            waf_region = "us-east-1" if scope == "CLOUDFRONT" else region

            wafv2_client = create_boto_client(
                service_name="wafv2",
                region_name=waf_region,
                profile_name=self.aws_profile,
            )

            # Extract name from ARN (format: ...rulegroup/name/id)
            arn_parts = arn.split("/")
            rulegroup_name = arn_parts[-2] if len(arn_parts) >= 2 else rulegroup_id

            # Get RuleGroup to retrieve LockToken
            try:
                response = wafv2_client.get_rule_group(Name=rulegroup_name, Scope=scope, Id=rulegroup_id)
                lock_token = response["LockToken"]
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "WAFNonexistentItemException":
                    return (True, None)  # RuleGroup already deleted
                raise

            # Delete the RuleGroup
            wafv2_client.delete_rule_group(
                Name=rulegroup_name,
                Scope=scope,
                Id=rulegroup_id,
                LockToken=lock_token,
            )

            logger.info(f"Deleted WAF RuleGroup {rulegroup_name}")
            return (True, None)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "WAFNonexistentItemException":
                return (True, None)  # RuleGroup already deleted

            return (False, f"Failed to cleanup WAF RuleGroup: {error_code}: {error_message}")
