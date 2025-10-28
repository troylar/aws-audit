"""CloudWatch resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class CloudWatchCollector(BaseResourceCollector):
    """Collector for AWS CloudWatch resources (alarms, log groups)."""

    @property
    def service_name(self) -> str:
        return "cloudwatch"

    def collect(self) -> List[Resource]:
        """Collect CloudWatch resources.

        Returns:
            List of CloudWatch resources
        """
        resources = []
        account_id = self._get_account_id()

        # Collect alarms
        resources.extend(self._collect_alarms(account_id))

        # Collect log groups
        resources.extend(self._collect_log_groups(account_id))

        self.logger.debug(f"Collected {len(resources)} CloudWatch resources in {self.region}")
        return resources

    def _collect_alarms(self, account_id: str) -> List[Resource]:
        """Collect CloudWatch alarms."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_alarms")
            for page in paginator.paginate():
                for alarm in page.get("MetricAlarms", []) + page.get("CompositeAlarms", []):
                    alarm_name = alarm["AlarmName"]
                    alarm_arn = alarm["AlarmArn"]

                    # Extract alarm type
                    alarm_type = "AWS::CloudWatch::Alarm"
                    if "CompositeAlarms" in str(type(alarm)):
                        alarm_type = "AWS::CloudWatch::CompositeAlarm"

                    # Create resource (CloudWatch alarms don't support tags directly)
                    resource = Resource(
                        arn=alarm_arn,
                        resource_type=alarm_type,
                        name=alarm_name,
                        region=self.region,
                        tags={},
                        config_hash=compute_config_hash(alarm),
                        created_at=alarm.get("AlarmConfigurationUpdatedTimestamp"),
                        raw_config=alarm,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting CloudWatch alarms in {self.region}: {e}")

        return resources

    def _collect_log_groups(self, account_id: str) -> List[Resource]:
        """Collect CloudWatch log groups."""
        resources = []

        try:
            logs_client = self._create_client("logs")

            paginator = logs_client.get_paginator("describe_log_groups")
            for page in paginator.paginate():
                for log_group in page.get("logGroups", []):
                    log_group_name = log_group["logGroupName"]

                    # Build ARN
                    arn = log_group.get("arn", f"arn:aws:logs:{self.region}:{account_id}:log-group:{log_group_name}")

                    # Get tags
                    tags = {}
                    try:
                        tag_response = logs_client.list_tags_log_group(logGroupName=log_group_name)
                        tags = tag_response.get("tags", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for log group {log_group_name}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::Logs::LogGroup",
                        name=log_group_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(log_group),
                        created_at=None,  # Log groups don't expose creation timestamp easily
                        raw_config=log_group,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting CloudWatch log groups in {self.region}: {e}")

        return resources
