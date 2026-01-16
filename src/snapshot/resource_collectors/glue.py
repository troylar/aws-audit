"""AWS Glue resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class GlueCollector(BaseResourceCollector):
    """Collector for AWS Glue resources (databases, tables, crawlers, jobs)."""

    @property
    def service_name(self) -> str:
        return "glue"

    def collect(self) -> List[Resource]:
        """Collect AWS Glue resources.

        Returns:
            List of Glue resources (databases, tables, crawlers, jobs)
        """
        resources = []
        client = self._create_client()
        account_id = self._get_account_id()

        # Collect databases and tables
        resources.extend(self._collect_databases(client, account_id))

        # Collect crawlers
        resources.extend(self._collect_crawlers(client, account_id))

        # Collect jobs
        resources.extend(self._collect_jobs(client, account_id))

        # Collect connections
        resources.extend(self._collect_connections(client, account_id))

        self.logger.debug(f"Collected {len(resources)} Glue resources in {self.region}")
        return resources

    def _collect_databases(self, client, account_id: str) -> List[Resource]:
        """Collect Glue databases and their tables."""
        resources = []

        try:
            paginator = client.get_paginator("get_databases")
            for page in paginator.paginate():
                for db in page.get("DatabaseList", []):
                    db_name = db.get("Name")
                    db_arn = f"arn:aws:glue:{self.region}:{account_id}:database/{db_name}"

                    resource = Resource(
                        arn=db_arn,
                        resource_type="AWS::Glue::Database",
                        name=db_name,
                        region=self.region,
                        tags={},  # Glue databases don't support tags directly
                        config_hash=compute_config_hash(db),
                        created_at=db.get("CreateTime"),
                        raw_config=db,
                    )
                    resources.append(resource)

                    # Collect tables for this database
                    resources.extend(self._collect_tables(client, account_id, db_name))

        except Exception as e:
            self.logger.error(f"Error collecting Glue databases in {self.region}: {e}")

        return resources

    def _collect_tables(self, client, account_id: str, database_name: str) -> List[Resource]:
        """Collect tables for a specific database."""
        resources = []

        try:
            paginator = client.get_paginator("get_tables")
            for page in paginator.paginate(DatabaseName=database_name):
                for table in page.get("TableList", []):
                    table_name = table.get("Name")
                    table_arn = f"arn:aws:glue:{self.region}:{account_id}:table/{database_name}/{table_name}"

                    resource = Resource(
                        arn=table_arn,
                        resource_type="AWS::Glue::Table",
                        name=f"{database_name}/{table_name}",
                        region=self.region,
                        tags={},  # Glue tables don't support tags directly
                        config_hash=compute_config_hash(table),
                        created_at=table.get("CreateTime"),
                        raw_config=table,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.debug(f"Error collecting tables for database {database_name}: {e}")

        return resources

    def _collect_crawlers(self, client, account_id: str) -> List[Resource]:
        """Collect Glue crawlers."""
        resources = []

        try:
            paginator = client.get_paginator("get_crawlers")
            for page in paginator.paginate():
                for crawler in page.get("Crawlers", []):
                    crawler_name = crawler.get("Name")
                    crawler_arn = f"arn:aws:glue:{self.region}:{account_id}:crawler/{crawler_name}"

                    # Get tags for crawler
                    tags = {}
                    try:
                        tag_response = client.get_tags(ResourceArn=crawler_arn)
                        tags = tag_response.get("Tags", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for crawler {crawler_name}: {e}")

                    resource = Resource(
                        arn=crawler_arn,
                        resource_type="AWS::Glue::Crawler",
                        name=crawler_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(crawler),
                        created_at=crawler.get("CreationTime"),
                        raw_config=crawler,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Glue crawlers in {self.region}: {e}")

        return resources

    def _collect_jobs(self, client, account_id: str) -> List[Resource]:
        """Collect Glue jobs."""
        resources = []

        try:
            paginator = client.get_paginator("get_jobs")
            for page in paginator.paginate():
                for job in page.get("Jobs", []):
                    job_name = job.get("Name")
                    job_arn = f"arn:aws:glue:{self.region}:{account_id}:job/{job_name}"

                    # Get tags for job
                    tags = {}
                    try:
                        tag_response = client.get_tags(ResourceArn=job_arn)
                        tags = tag_response.get("Tags", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for job {job_name}: {e}")

                    resource = Resource(
                        arn=job_arn,
                        resource_type="AWS::Glue::Job",
                        name=job_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(job),
                        created_at=job.get("CreatedOn"),
                        raw_config=job,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Glue jobs in {self.region}: {e}")

        return resources

    def _collect_connections(self, client, account_id: str) -> List[Resource]:
        """Collect Glue connections."""
        resources = []

        try:
            paginator = client.get_paginator("get_connections")
            for page in paginator.paginate():
                for conn in page.get("ConnectionList", []):
                    conn_name = conn.get("Name")
                    conn_arn = f"arn:aws:glue:{self.region}:{account_id}:connection/{conn_name}"

                    resource = Resource(
                        arn=conn_arn,
                        resource_type="AWS::Glue::Connection",
                        name=conn_name,
                        region=self.region,
                        tags={},  # Connections don't support tags
                        config_hash=compute_config_hash(conn),
                        created_at=conn.get("CreationTime"),
                        raw_config=conn,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Glue connections in {self.region}: {e}")

        return resources
