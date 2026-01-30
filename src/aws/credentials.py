"""AWS credential validation and permission checking."""

import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

logger = logging.getLogger(__name__)


class CredentialValidationError(Exception):
    """Raised when AWS credentials are invalid or missing."""

    pass


def validate_credentials(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """Validate AWS credentials and return caller identity information.

    Args:
        profile_name: AWS profile name from ~/.aws/config (optional)

    Returns:
        Dictionary with account ID, user ID, and ARN

    Raises:
        CredentialValidationError: If credentials are invalid or missing
    """
    try:
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            sts_client = session.client("sts")
        else:
            sts_client = boto3.client("sts")

        # Get caller identity to validate credentials
        identity = sts_client.get_caller_identity()

        logger.debug(f"Validated credentials for account {identity['Account']}")

        return {
            "account_id": identity["Account"],
            "user_id": identity["UserId"],
            "arn": identity["Arn"],
        }

    except NoCredentialsError:
        error_msg = (
            "AWS credentials not found. Please configure credentials using one of these methods:\n"
            "  1. Run: aws configure\n"
            "  2. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY\n"
            "  3. Use --profile option with a configured profile\n\n"
            "For more info: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html"
        )
        logger.error("No AWS credentials found")
        raise CredentialValidationError(error_msg)

    except PartialCredentialsError as e:
        error_msg = f"Incomplete AWS credentials: {e}"
        logger.error(error_msg)
        raise CredentialValidationError(error_msg)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "InvalidClientTokenId":
            error_msg = "AWS credentials are invalid. Please check your access key ID."
        elif error_code == "SignatureDoesNotMatch":
            error_msg = "AWS credentials signature mismatch. Please check your secret access key."
        elif error_code == "ExpiredToken":
            error_msg = "AWS credentials have expired. Please refresh your temporary credentials."
        else:
            error_msg = f"AWS credential validation failed: {e}"

        logger.error(error_msg)
        raise CredentialValidationError(error_msg)

    except Exception as e:
        error_msg = f"Unexpected error validating credentials: {e}"
        logger.error(error_msg)
        raise CredentialValidationError(error_msg)


def check_required_permissions(
    profile_name: Optional[str] = None, required_actions: Optional[List[str]] = None
) -> Dict[str, bool]:
    """Check if credentials have required IAM permissions.

    Note: This is a best-effort check using IAM policy simulation.
    Some permissions may not be accurately detected.

    Args:
        profile_name: AWS profile name (optional)
        required_actions: List of IAM actions to check (e.g., ['ec2:DescribeInstances'])

    Returns:
        Dictionary mapping action names to permission status (True/False)
    """
    if required_actions is None:
        # Default minimum required permissions for snapshot operations
        required_actions = [
            "ec2:DescribeInstances",
            "ec2:DescribeRegions",
            "iam:ListRoles",
            "lambda:ListFunctions",
            "s3:ListAllMyBuckets",
        ]

    try:
        # Get caller identity first
        identity = validate_credentials(profile_name)

        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            iam_client = session.client("iam")
        else:
            iam_client = boto3.client("iam")

        results = {}

        # Try to simulate policy for each action
        for action in required_actions:
            try:
                response = iam_client.simulate_principal_policy(
                    PolicySourceArn=identity["arn"],
                    ActionNames=[action],
                )

                # Check if action is allowed
                eval_results = response.get("EvaluationResults", [])
                if eval_results:
                    decision = eval_results[0].get("EvalDecision", "deny")
                    results[action] = decision.lower() == "allowed"
                else:
                    results[action] = False

            except ClientError as e:
                # If simulation fails (e.g., lack of iam:SimulatePrincipalPolicy permission),
                # we can't determine the permission status
                logger.debug(f"Could not check permission for {action}: {e}")
                results[action] = None  # Unknown

        return results

    except Exception as e:
        logger.warning(f"Permission check failed: {e}")
        return {action: None for action in required_actions}  # type: ignore


def get_account_id(profile_name: Optional[str] = None) -> str:
    """Get AWS account ID for the current credentials.

    Args:
        profile_name: AWS profile name (optional)

    Returns:
        12-digit AWS account ID

    Raises:
        CredentialValidationError: If credentials are invalid
    """
    identity = validate_credentials(profile_name)
    return identity["account_id"]


def get_credential_summary(profile_name: Optional[str] = None) -> str:
    """Get a human-readable summary of current AWS credentials.

    Args:
        profile_name: AWS profile name (optional)

    Returns:
        Formatted string with credential information
    """
    try:
        identity = validate_credentials(profile_name)

        summary = f"""
AWS Credentials Valid
Account ID: {identity["account_id"]}
User/Role: {identity["arn"].split("/")[-1]}
ARN: {identity["arn"]}
"""

        if profile_name:
            summary += f"Profile: {profile_name}\n"

        return summary.strip()

    except CredentialValidationError as e:
        return f"Credential Validation Failed:\n{e}"
