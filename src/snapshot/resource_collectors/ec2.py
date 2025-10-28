"""EC2 resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class EC2Collector(BaseResourceCollector):
    """Collector for AWS EC2 resources (instances, volumes, VPCs, security groups, etc.)."""

    @property
    def service_name(self) -> str:
        return "ec2"

    def collect(self) -> List[Resource]:
        """Collect EC2 resources.

        Returns:
            List of EC2 resources
        """
        resources = []
        account_id = self._get_account_id()

        # Collect instances
        resources.extend(self._collect_instances(account_id))

        # Collect volumes
        resources.extend(self._collect_volumes(account_id))

        # Collect VPCs
        resources.extend(self._collect_vpcs(account_id))

        # Collect security groups
        resources.extend(self._collect_security_groups(account_id))

        # Collect subnets
        resources.extend(self._collect_subnets(account_id))

        self.logger.debug(f"Collected {len(resources)} EC2 resources in {self.region}")
        return resources

    def _collect_instances(self, account_id: str) -> List[Resource]:
        """Collect EC2 instances."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]

                        # Extract tags
                        tags = {}
                        for tag in instance.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]

                        # Get instance name from tags
                        name = tags.get("Name", instance_id)

                        # Build ARN
                        arn = f"arn:aws:ec2:{self.region}:{account_id}:instance/{instance_id}"

                        # Create resource
                        resource = Resource(
                            arn=arn,
                            resource_type="AWS::EC2::Instance",
                            name=name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(instance),
                            created_at=instance.get("LaunchTime"),
                            raw_config=instance,
                        )
                        resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting EC2 instances in {self.region}: {e}")

        return resources

    def _collect_volumes(self, account_id: str) -> List[Resource]:
        """Collect EBS volumes."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page["Volumes"]:
                    volume_id = volume["VolumeId"]

                    # Extract tags
                    tags = {}
                    for tag in volume.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]

                    # Get volume name from tags
                    name = tags.get("Name", volume_id)

                    # Build ARN
                    arn = f"arn:aws:ec2:{self.region}:{account_id}:volume/{volume_id}"

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::EC2::Volume",
                        name=name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(volume),
                        created_at=volume.get("CreateTime"),
                        raw_config=volume,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting EBS volumes in {self.region}: {e}")

        return resources

    def _collect_vpcs(self, account_id: str) -> List[Resource]:
        """Collect VPCs."""
        resources = []
        client = self._create_client()

        try:
            response = client.describe_vpcs()
            for vpc in response["Vpcs"]:
                vpc_id = vpc["VpcId"]

                # Extract tags
                tags = {}
                for tag in vpc.get("Tags", []):
                    tags[tag["Key"]] = tag["Value"]

                # Get VPC name from tags
                name = tags.get("Name", vpc_id)

                # Build ARN
                arn = f"arn:aws:ec2:{self.region}:{account_id}:vpc/{vpc_id}"

                # Create resource
                resource = Resource(
                    arn=arn,
                    resource_type="AWS::EC2::VPC",
                    name=name,
                    region=self.region,
                    tags=tags,
                    config_hash=compute_config_hash(vpc),
                    created_at=None,  # VPCs don't have creation timestamp
                    raw_config=vpc,
                )
                resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting VPCs in {self.region}: {e}")

        return resources

    def _collect_security_groups(self, account_id: str) -> List[Resource]:
        """Collect security groups."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_security_groups")
            for page in paginator.paginate():
                for sg in page["SecurityGroups"]:
                    sg_id = sg["GroupId"]
                    sg_name = sg["GroupName"]

                    # Extract tags
                    tags = {}
                    for tag in sg.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]

                    # Build ARN
                    arn = f"arn:aws:ec2:{self.region}:{account_id}:security-group/{sg_id}"

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::EC2::SecurityGroup",
                        name=sg_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(sg),
                        created_at=None,  # Security groups don't have creation timestamp
                        raw_config=sg,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting security groups in {self.region}: {e}")

        return resources

    def _collect_subnets(self, account_id: str) -> List[Resource]:
        """Collect subnets."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_subnets")
            for page in paginator.paginate():
                for subnet in page["Subnets"]:
                    subnet_id = subnet["SubnetId"]

                    # Extract tags
                    tags = {}
                    for tag in subnet.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]

                    # Get subnet name from tags
                    name = tags.get("Name", subnet_id)

                    # Build ARN
                    arn = f"arn:aws:ec2:{self.region}:{account_id}:subnet/{subnet_id}"

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::EC2::Subnet",
                        name=name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(subnet),
                        created_at=None,  # Subnets don't have creation timestamp
                        raw_config=subnet,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting subnets in {self.region}: {e}")

        return resources
