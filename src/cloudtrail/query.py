"""CloudTrail query for resource creation events."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Set

from ..aws.client import create_boto_client

logger = logging.getLogger(__name__)

# Map of CloudTrail event names to resource types
# This maps creation events to the resource types they create
EVENT_TO_RESOURCE_TYPE: Dict[str, str] = {
    # EC2
    "RunInstances": "AWS::EC2::Instance",
    "CreateVolume": "AWS::EC2::Volume",
    "CreateVpc": "AWS::EC2::VPC",
    "CreateSubnet": "AWS::EC2::Subnet",
    "CreateSecurityGroup": "AWS::EC2::SecurityGroup",
    "CreateVpcEndpoint": "AWS::EC2::VPCEndpoint",
    # Lambda
    "CreateFunction20150331": "AWS::Lambda::Function",
    "CreateFunction": "AWS::Lambda::Function",
    # S3
    "CreateBucket": "AWS::S3::Bucket",
    # RDS
    "CreateDBInstance": "AWS::RDS::DBInstance",
    "CreateDBCluster": "AWS::RDS::DBCluster",
    # IAM
    "CreateRole": "AWS::IAM::Role",
    "CreateUser": "AWS::IAM::User",
    "CreateGroup": "AWS::IAM::Group",
    "CreatePolicy": "AWS::IAM::Policy",
    # CloudWatch
    "PutMetricAlarm": "AWS::CloudWatch::Alarm",
    "CreateLogGroup": "AWS::Logs::LogGroup",
    # SNS
    "CreateTopic": "AWS::SNS::Topic",
    # SQS
    "CreateQueue": "AWS::SQS::Queue",
    # ELB
    "CreateLoadBalancer": "AWS::ElasticLoadBalancingV2::LoadBalancer",
    # CloudFormation
    "CreateStack": "AWS::CloudFormation::Stack",
    # API Gateway
    "CreateRestApi": "AWS::ApiGateway::RestApi",
    "CreateApi": "AWS::ApiGatewayV2::Api",
    # EventBridge
    "CreateEventBus": "AWS::Events::EventBus",
    "PutRule": "AWS::Events::Rule",
    # Secrets Manager
    "CreateSecret": "AWS::SecretsManager::Secret",
    # KMS
    "CreateKey": "AWS::KMS::Key",
    # SSM
    "PutParameter": "AWS::SSM::Parameter",
    # Route53
    "CreateHostedZone": "AWS::Route53::HostedZone",
    # ECS
    "CreateService": "AWS::ECS::Service",
    "RegisterTaskDefinition": "AWS::ECS::TaskDefinition",
    # EKS
    "CreateNodegroup": "AWS::EKS::Nodegroup",
    # Step Functions
    "CreateStateMachine": "AWS::StepFunctions::StateMachine",
    # WAF
    "CreateWebACL": "AWS::WAFv2::WebACL",
    # CodePipeline
    "CreatePipeline": "AWS::CodePipeline::Pipeline",
    # CodeBuild
    "CreateProject": "AWS::CodeBuild::Project",
    # Backup
    "CreateBackupPlan": "AWS::Backup::BackupPlan",
    "CreateBackupVault": "AWS::Backup::BackupVault",
    # Glue
    "CreateDatabase": "AWS::Glue::Database",
    "CreateCrawler": "AWS::Glue::Crawler",
    "CreateJob": "AWS::Glue::Job",
    "CreateConnection": "AWS::Glue::Connection",
    # EFS
    "CreateFileSystem": "AWS::EFS::FileSystem",
    # ElastiCache
    "CreateCacheCluster": "AWS::ElastiCache::CacheCluster",
    "CreateReplicationGroup": "AWS::ElastiCache::ReplicationGroup",
}

# Events that map to different resource types based on event source
# Key: event_name, Value: dict mapping eventSource to resource type
MULTI_SERVICE_EVENTS: Dict[str, Dict[str, str]] = {
    "CreateCluster": {
        "ecs.amazonaws.com": "AWS::ECS::Cluster",
        "eks.amazonaws.com": "AWS::EKS::Cluster",
    },
    "CreateTable": {
        "dynamodb.amazonaws.com": "AWS::DynamoDB::Table",
        "glue.amazonaws.com": "AWS::Glue::Table",
    },
}


def get_resource_type_for_event(event_name: str, event_source: Optional[str] = None) -> Optional[str]:
    """Get resource type for a CloudTrail event.

    Args:
        event_name: The CloudTrail event name
        event_source: The event source (e.g., 'ecs.amazonaws.com')

    Returns:
        The AWS resource type or None if not a tracked creation event
    """
    # Check multi-service events first
    if event_name in MULTI_SERVICE_EVENTS:
        if event_source and event_source in MULTI_SERVICE_EVENTS[event_name]:
            return MULTI_SERVICE_EVENTS[event_name][event_source]
        # Fall back to first mapping if no event source provided
        return next(iter(MULTI_SERVICE_EVENTS[event_name].values()))

    return EVENT_TO_RESOURCE_TYPE.get(event_name)


@dataclass
class ResourceCreationEvent:
    """Represents a resource creation event from CloudTrail."""

    event_time: datetime
    event_name: str
    resource_type: str
    resource_name: Optional[str]
    resource_arn: Optional[str]
    created_by_arn: str
    created_by_type: str  # 'Role', 'User', 'AssumedRole'
    region: str
    account_id: str
    raw_event: dict


class CloudTrailQuery:
    """Query CloudTrail for resource creation events."""

    def __init__(
        self,
        profile_name: Optional[str] = None,
        regions: Optional[List[str]] = None,
    ):
        """Initialize CloudTrail query.

        Args:
            profile_name: AWS profile to use
            regions: Regions to query (defaults to all regions with events)
        """
        self.profile_name = profile_name
        self.regions = regions or ["us-east-1"]  # CloudTrail events are regional

    def get_resources_created_by_role(
        self,
        role_arn: str,
        days_back: int = 90,
        regions: Optional[List[str]] = None,
    ) -> List[ResourceCreationEvent]:
        """Get all resources created by a specific IAM role.

        Args:
            role_arn: Full ARN of the IAM role (or just role name)
            days_back: How many days to look back (max 90 for standard CloudTrail)
            regions: Regions to query

        Returns:
            List of ResourceCreationEvent objects
        """
        events = []
        query_regions = regions or self.regions

        # Normalize role ARN - extract role name for matching
        if role_arn.startswith("arn:aws:iam::"):
            # Full ARN like arn:aws:iam::123456789012:role/MyRole
            role_name = role_arn.split("/")[-1]
        elif "/" in role_arn:
            # Path format like role/MyRole
            role_name = role_arn.split("/")[-1]
        else:
            # Just the role name
            role_name = role_arn

        logger.info(f"Querying CloudTrail for resources created by role: {role_name}")

        for region in query_regions:
            try:
                region_events = self._query_region(role_name, role_arn, days_back, region)
                events.extend(region_events)
                logger.debug(f"Found {len(region_events)} creation events in {region}")
            except Exception as e:
                logger.warning(f"Error querying CloudTrail in {region}: {e}")

        logger.info(f"Total creation events found: {len(events)}")
        return events

    def _query_region(
        self,
        role_name: str,
        role_arn: str,
        days_back: int,
        region: str,
    ) -> List[ResourceCreationEvent]:
        """Query CloudTrail in a specific region."""
        client = create_boto_client(
            service_name="cloudtrail",
            region_name=region,
            profile_name=self.profile_name,
        )

        events = []
        start_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        end_time = datetime.now(timezone.utc)

        # Query by username (role session name includes role)
        # CloudTrail stores assumed role sessions as "role/session-name"
        paginator = client.get_paginator("lookup_events")

        try:
            # First try looking up by the role ARN pattern
            for page in paginator.paginate(
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=50,  # CloudTrail max per page
            ):
                for event in page.get("Events", []):
                    parsed = self._parse_event(event, role_name, role_arn, region)
                    if parsed:
                        events.append(parsed)

        except Exception as e:
            logger.error(f"Error querying CloudTrail: {e}")
            raise

        return events

    def _parse_event(
        self,
        event: dict,
        role_name: str,
        role_arn: str,
        region: str,
    ) -> Optional[ResourceCreationEvent]:
        """Parse a CloudTrail event and check if it matches our criteria."""
        try:
            cloud_trail_event = json.loads(event.get("CloudTrailEvent", "{}"))

            event_name = cloud_trail_event.get("eventName", "")
            event_source = cloud_trail_event.get("eventSource", "")

            # Check if this is a creation event we care about
            resource_type = get_resource_type_for_event(event_name, event_source)
            if not resource_type:
                return None

            # Check if the identity matches our role
            user_identity = cloud_trail_event.get("userIdentity", {})
            identity_type = user_identity.get("type", "")

            # Match by role ARN or role name
            matches_role = False
            created_by_arn = ""

            if identity_type == "AssumedRole":
                # For assumed roles, check the role ARN
                session_context = user_identity.get("sessionContext", {})
                session_issuer = session_context.get("sessionIssuer", {})
                arn = session_issuer.get("arn", "")
                created_by_arn = arn

                if role_arn and arn == role_arn:
                    matches_role = True
                elif role_name and role_name in arn:
                    matches_role = True

            elif identity_type == "Role":
                arn = user_identity.get("arn", "")
                created_by_arn = arn

                if role_arn and arn == role_arn:
                    matches_role = True
                elif role_name and role_name in arn:
                    matches_role = True

            if not matches_role:
                return None

            # Extract resource information
            resource_name, resource_arn_extracted = self._extract_resource_info(cloud_trail_event, event_name)

            # Get account ID
            account_id = cloud_trail_event.get("recipientAccountId", "")
            if not account_id:
                account_id = user_identity.get("accountId", "")

            return ResourceCreationEvent(
                event_time=event.get("EventTime", datetime.now(timezone.utc)),
                event_name=event_name,
                resource_type=resource_type,
                resource_name=resource_name,
                resource_arn=resource_arn_extracted,
                created_by_arn=created_by_arn,
                created_by_type=identity_type,
                region=cloud_trail_event.get("awsRegion", region),
                account_id=account_id,
                raw_event=cloud_trail_event,
            )

        except Exception as e:
            logger.debug(f"Error parsing CloudTrail event: {e}")
            return None

    def _extract_resource_info(self, event: dict, event_name: str) -> tuple[Optional[str], Optional[str]]:
        """Extract resource name and ARN from CloudTrail event.

        Returns:
            Tuple of (resource_name, resource_arn)
        """
        request_params = event.get("requestParameters", {}) or {}
        response_elements = event.get("responseElements", {}) or {}

        resource_name = None
        resource_arn = None

        # Try common patterns for resource names
        name_keys = [
            "name",
            "bucketName",
            "functionName",
            "tableName",
            "roleName",
            "userName",
            "groupName",
            "policyName",
            "topicName",
            "queueName",
            "stackName",
            "clusterName",
            "serviceName",
            "stateMachineName",
            "projectName",
            "pipelineName",
            "dBInstanceIdentifier",
            "dBClusterIdentifier",
            "hostedZoneName",
            "fileSystemId",
            "cacheClusterId",
            "replicationGroupId",
            "webACLName",
            "eventBusName",
            "ruleName",
            "secretId",
            "parameterName",
            "databaseName",
            "crawlerName",
            "jobName",
            "connectionName",
        ]

        for key in name_keys:
            if key in request_params:
                resource_name = request_params[key]
                break

        # Try to extract ARN from response
        arn_keys = [
            "functionArn",
            "roleArn",
            "topicArn",
            "queueUrl",  # SQS uses URL
            "stackId",
            "arn",
            "clusterArn",
            "serviceArn",
            "stateMachineArn",
            "webACLArn",
        ]

        for key in arn_keys:
            if response_elements and key in response_elements:
                resource_arn = response_elements[key]
                break

        # For EC2 instances, extract from response
        if event_name == "RunInstances" and response_elements:
            instances = response_elements.get("instancesSet", {}).get("items", [])
            if instances:
                resource_name = instances[0].get("instanceId")

        return resource_name, resource_arn

    def get_created_resource_arns(
        self,
        role_arn: str,
        days_back: int = 90,
        regions: Optional[List[str]] = None,
    ) -> Set[str]:
        """Get set of ARNs for resources created by a role.

        Args:
            role_arn: IAM role ARN or name
            days_back: Days to look back
            regions: Regions to query

        Returns:
            Set of resource ARNs
        """
        events = self.get_resources_created_by_role(role_arn, days_back, regions)

        arns = set()
        for event in events:
            if event.resource_arn:
                arns.add(event.resource_arn)

        return arns

    def get_created_resource_names(
        self,
        role_arn: str,
        days_back: int = 90,
        regions: Optional[List[str]] = None,
    ) -> Dict[str, Set[str]]:
        """Get resource names grouped by type for resources created by a role.

        Args:
            role_arn: IAM role ARN or name
            days_back: Days to look back
            regions: Regions to query

        Returns:
            Dict mapping resource_type to set of resource names
        """
        events = self.get_resources_created_by_role(role_arn, days_back, regions)

        by_type: Dict[str, Set[str]] = {}
        for event in events:
            if event.resource_name:
                if event.resource_type not in by_type:
                    by_type[event.resource_type] = set()
                by_type[event.resource_type].add(event.resource_name)

        return by_type

    def get_all_creation_events(
        self,
        days_back: int = 90,
        regions: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None,
        resource_types: Optional[Set[str]] = None,
    ) -> List[ResourceCreationEvent]:
        """Get all resource creation events from CloudTrail.

        Args:
            days_back: How many days to look back (max 90 for standard CloudTrail)
            regions: Regions to query
            progress_callback: Optional callback(event_name, events_found) for progress updates
            resource_types: Optional set of resource types to filter (e.g., {"AWS::Lambda::Function"})
                           If provided, only queries event types that create these resource types.

        Returns:
            List of ResourceCreationEvent objects
        """
        events = []
        query_regions = regions or self.regions

        logger.info(f"Querying CloudTrail for all creation events (last {days_back} days)")

        # Filter event types if resource_types specified
        if resource_types:
            filtered_event_names = [
                event_name for event_name, res_type in EVENT_TO_RESOURCE_TYPE.items() if res_type in resource_types
            ]
            # Also check multi-service events
            for event_name, source_mapping in MULTI_SERVICE_EVENTS.items():
                for res_type in source_mapping.values():
                    if res_type in resource_types and event_name not in filtered_event_names:
                        filtered_event_names.append(event_name)
            # If no matches found, fall back to querying all event types
            if not filtered_event_names:
                logger.warning(f"No matching event types found for resource types: {resource_types}")
                logger.info("Falling back to querying all event types")
                filtered_event_names = None
            else:
                logger.info(f"Filtering to {len(filtered_event_names)} event types matching snapshot resources")
        else:
            filtered_event_names = None

        # Process all regions in parallel for speed
        with ThreadPoolExecutor(max_workers=len(query_regions)) as executor:
            futures = {
                executor.submit(
                    self._query_all_creation_events_fast,
                    days_back,
                    region,
                    progress_callback,
                    filtered_event_names,
                ): region
                for region in query_regions
            }

            for future in as_completed(futures):
                region = futures[future]
                try:
                    region_events = future.result()
                    events.extend(region_events)
                    logger.debug(f"Found {len(region_events)} creation events in {region}")
                except Exception as e:
                    logger.warning(f"Error querying CloudTrail in {region}: {e}")

        logger.info(f"Total creation events found: {len(events)}")
        return events

    def _query_single_event_type(
        self,
        client,
        event_name: str,
        start_time: datetime,
        end_time: datetime,
        region: str,
    ) -> List[ResourceCreationEvent]:
        """Query CloudTrail for a single event type."""
        events = []
        try:
            paginator = client.get_paginator("lookup_events")
            for page in paginator.paginate(
                LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": event_name}],
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=50,
            ):
                for event in page.get("Events", []):
                    parsed = self._parse_creation_event(event, region)
                    if parsed:
                        events.append(parsed)
        except Exception as e:
            logger.debug(f"Error querying {event_name}: {e}")
        return events

    def _query_all_creation_events_fast(
        self,
        days_back: int,
        region: str,
        progress_callback: Optional[Callable] = None,
        event_names_filter: Optional[List[str]] = None,
    ) -> List[ResourceCreationEvent]:
        """Query CloudTrail for all creation events using parallel queries by event name."""
        client = create_boto_client(
            service_name="cloudtrail",
            region_name=region,
            profile_name=self.profile_name,
        )

        events = []
        start_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        end_time = datetime.now(timezone.utc)

        # Use filtered event names if provided, otherwise query all
        if event_names_filter:
            event_names = event_names_filter
        else:
            event_names = list(EVENT_TO_RESOURCE_TYPE.keys()) + list(MULTI_SERVICE_EVENTS.keys())

        # Use ThreadPoolExecutor for parallel queries - increase workers for faster I/O
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(
                    self._query_single_event_type,
                    client,
                    event_name,
                    start_time,
                    end_time,
                    region,
                ): event_name
                for event_name in event_names
            }

            for future in as_completed(futures):
                event_name = futures[future]
                try:
                    result = future.result()
                    events.extend(result)
                    if progress_callback:
                        progress_callback(event_name, len(result))
                except Exception as e:
                    logger.debug(f"Error querying {event_name}: {e}")

        return events

    def _query_all_creation_events(
        self,
        days_back: int,
        region: str,
    ) -> List[ResourceCreationEvent]:
        """Query CloudTrail for all creation events in a specific region (legacy method)."""
        return self._query_all_creation_events_fast(days_back, region)

    def _parse_creation_event(
        self,
        event: dict,
        region: str,
    ) -> Optional[ResourceCreationEvent]:
        """Parse a CloudTrail event for any creation event."""
        try:
            cloud_trail_event = json.loads(event.get("CloudTrailEvent", "{}"))

            event_name = cloud_trail_event.get("eventName", "")
            event_source = cloud_trail_event.get("eventSource", "")

            # Check if this is a creation event we care about
            resource_type = get_resource_type_for_event(event_name, event_source)
            if not resource_type:
                return None

            # Extract creator identity
            user_identity = cloud_trail_event.get("userIdentity", {})
            identity_type = user_identity.get("type", "")
            created_by_arn = ""

            if identity_type == "AssumedRole":
                session_context = user_identity.get("sessionContext", {})
                session_issuer = session_context.get("sessionIssuer", {})
                created_by_arn = session_issuer.get("arn", "")
            elif identity_type == "Role":
                created_by_arn = user_identity.get("arn", "")
            elif identity_type == "IAMUser":
                created_by_arn = user_identity.get("arn", "")
            elif identity_type == "Root":
                created_by_arn = "root"
            elif identity_type == "AWSService":
                invoking_service = user_identity.get("invokedBy", "")
                created_by_arn = f"service:{invoking_service}"

            # Extract resource information
            resource_name, resource_arn_extracted = self._extract_resource_info(cloud_trail_event, event_name)

            # Get account ID
            account_id = cloud_trail_event.get("recipientAccountId", "")
            if not account_id:
                account_id = user_identity.get("accountId", "")

            return ResourceCreationEvent(
                event_time=event.get("EventTime", datetime.now(timezone.utc)),
                event_name=event_name,
                resource_type=resource_type,
                resource_name=resource_name,
                resource_arn=resource_arn_extracted,
                created_by_arn=created_by_arn,
                created_by_type=identity_type,
                region=cloud_trail_event.get("awsRegion", region),
                account_id=account_id,
                raw_event=cloud_trail_event,
            )

        except Exception as e:
            logger.debug(f"Error parsing CloudTrail event: {e}")
            return None

    def get_resource_creators(
        self,
        days_back: int = 90,
        regions: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None,
        resource_types: Optional[Set[str]] = None,
    ) -> Dict[str, Dict[str, str]]:
        """Build a mapping of resources to their creators.

        Args:
            days_back: Days to look back
            regions: Regions to query
            progress_callback: Optional callback(event_name, events_found) for progress updates
            resource_types: Optional set of resource types to filter queries
                           (speeds up queries by only looking for relevant event types)

        Returns:
            Dict mapping (resource_type, resource_name) key to creator info:
            {
                "AWS::S3::Bucket:my-bucket": {
                    "created_by": "arn:aws:iam::123:role/MyRole",
                    "created_by_type": "AssumedRole",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            }
        """
        events = self.get_all_creation_events(days_back, regions, progress_callback, resource_types)

        creators: Dict[str, Dict[str, str]] = {}
        for event in events:
            if event.resource_name:
                key = f"{event.resource_type}:{event.resource_name}"
                # Keep the most recent creation event for each resource
                if key not in creators or event.event_time > datetime.fromisoformat(
                    creators[key]["created_at"].replace("Z", "+00:00")
                ):
                    creators[key] = {
                        "created_by": event.created_by_arn,
                        "created_by_type": event.created_by_type,
                        "created_at": event.event_time.isoformat(),
                    }

        return creators
