"""Resource name normalizer using rules and AI."""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .config import NormalizerConfig
from .prompts import NORMALIZATION_SYSTEM_PROMPT


@dataclass
class NormalizationResult:
    """Result of normalizing a resource name.

    Attributes:
        normalized_name: The semantic part after stripping auto-generated components
        extracted_patterns: List of patterns that were stripped from the name
        method: How normalization was determined ('tag:logical-id', 'tag:Name', 'pattern', 'none')
        confidence: Confidence score (0.0-1.0) indicating reliability of the normalization
    """

    normalized_name: str
    extracted_patterns: List[str] = field(default_factory=list)
    method: str = "none"
    confidence: float = 0.9


logger = logging.getLogger(__name__)

# Try to import openai, but don't fail if not installed
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class ResourceNormalizer:
    """Normalize resource names using rules-based and AI approaches.

    The normalizer first tries rules-based normalization for obvious cases,
    then falls back to AI for ambiguous names.
    """

    def __init__(self, config: Optional[NormalizerConfig] = None):
        """Initialize the normalizer.

        Args:
            config: Configuration for normalization. If None, loads from environment.
        """
        self.config = config or NormalizerConfig.from_env()
        self._client: Optional[Any] = None
        self._total_tokens = 0

        # Compile regex patterns for performance
        self._random_patterns = [re.compile(p) for p in self.config.random_patterns]

    @property
    def client(self) -> Optional[Any]:
        """Lazy-init OpenAI client."""
        if self._client is None and self.config.is_ai_enabled:
            if not OPENAI_AVAILABLE:
                logger.warning("OpenAI package not installed. Install with: pip install openai")
                return None

            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    @property
    def tokens_used(self) -> int:
        """Total tokens used for AI normalization."""
        return self._total_tokens

    def normalize_resources(
        self,
        resources: List[Dict[str, Any]],
        use_ai: bool = True,
    ) -> Dict[str, str]:
        """Normalize a list of resources.

        Args:
            resources: List of resource dicts with 'arn', 'name', 'tags', 'resource_type'
            use_ai: Whether to use AI for ambiguous names

        Returns:
            Dict mapping ARN -> normalized_name
        """
        results: Dict[str, str] = {}
        needs_ai: List[Dict[str, Any]] = []

        # Phase 1: Try rules-based normalization
        for resource in resources:
            arn = resource.get("arn", "")
            normalized = self._try_rules_based(resource)

            if normalized:
                results[arn] = normalized
                logger.debug(f"Rules-based: {resource.get('name')} -> {normalized}")
            else:
                needs_ai.append(resource)

        logger.info(f"Normalization: {len(results)} via rules, {len(needs_ai)} need AI")

        # Phase 2: AI normalization for ambiguous names
        if needs_ai and use_ai and self.client:
            ai_results = self._normalize_with_ai(needs_ai)
            results.update(ai_results)
            logger.info(f"AI normalized {len(ai_results)} resources")
        elif needs_ai:
            # Fallback: use lowercase name if AI not available
            for resource in needs_ai:
                arn = resource.get("arn", "")
                name = resource.get("name", "")
                results[arn] = self._basic_normalize(name)
                logger.debug(f"Fallback: {name} -> {results[arn]}")

        return results

    def normalize_single(
        self,
        name: str,
        resource_type: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> NormalizationResult:
        """Normalize a single resource and return detailed result.

        This method is used by snapshot_store to compute normalized names
        during snapshot save.

        Args:
            name: Physical resource name
            resource_type: AWS resource type (e.g., 'AWS::Lambda::Function')
            tags: Resource tags

        Returns:
            NormalizationResult with normalized_name, extracted_patterns, method, confidence
        """
        tags = tags or {}

        # Priority 1: CloudFormation logical ID tag (most reliable)
        logical_id = tags.get("aws:cloudformation:logical-id")
        if logical_id:
            return NormalizationResult(
                normalized_name=self._basic_normalize(logical_id),
                extracted_patterns=[],
                method="tag:logical-id",
                confidence=1.0,
            )

        # Priority 2: Name tag (user-defined, stable)
        name_tag = tags.get("Name")
        if name_tag and not self._has_random_patterns(name_tag):
            return NormalizationResult(
                normalized_name=self._basic_normalize(name_tag),
                extracted_patterns=[],
                method="tag:Name",
                confidence=0.95,
            )

        # Priority 3: Check if entirely AWS-generated ID (subnet-xxx, vpc-xxx, etc.)
        if self._is_aws_resource_id(name, resource_type):
            # Can't normalize - needs Name tag for stable matching
            return NormalizationResult(
                normalized_name=self._basic_normalize(name),
                extracted_patterns=[name],
                method="none",
                confidence=0.0,  # Low confidence - needs tag for reliable matching
            )

        # Priority 4: Try to extract patterns from physical name
        normalized, extracted = self._extract_patterns(name)
        if extracted:
            return NormalizationResult(
                normalized_name=self._basic_normalize(normalized),
                extracted_patterns=extracted,
                method="pattern",
                confidence=0.8,
            )

        # Priority 5: Clean name - no normalization needed
        return NormalizationResult(
            normalized_name=self._basic_normalize(name),
            extracted_patterns=[],
            method="none",
            confidence=0.9,  # Clean name, high confidence
        )

    def _is_aws_resource_id(self, name: str, resource_type: str) -> bool:
        """Check if name is entirely an AWS-generated resource ID.

        These IDs (subnet-xxx, vpc-xxx, vol-xxx, etc.) are stable but
        provide no semantic meaning without a Name tag.
        """
        # Map resource types to their ID patterns
        aws_id_patterns = {
            "AWS::EC2::Subnet": r"^subnet-[a-f0-9]+$",
            "AWS::EC2::VPC": r"^vpc-[a-f0-9]+$",
            "AWS::EC2::SecurityGroup": r"^sg-[a-f0-9]+$",
            "AWS::EC2::Volume": r"^vol-[a-f0-9]+$",
            "AWS::EC2::Instance": r"^i-[a-f0-9]+$",
            "AWS::EC2::InternetGateway": r"^igw-[a-f0-9]+$",
            "AWS::EC2::RouteTable": r"^rtb-[a-f0-9]+$",
            "AWS::EC2::NetworkAcl": r"^acl-[a-f0-9]+$",
            "AWS::EC2::NetworkInterface": r"^eni-[a-f0-9]+$",
            "AWS::EC2::NatGateway": r"^nat-[a-f0-9]+$",
            "AWS::EC2::EIP": r"^eipalloc-[a-f0-9]+$",
        }

        pattern = aws_id_patterns.get(resource_type)
        if pattern:
            # AWS resource IDs are always lowercase hex, no IGNORECASE needed
            return bool(re.match(pattern, name))
        return False

    def _extract_patterns(self, name: str) -> Tuple[str, List[str]]:
        """Extract auto-generated patterns from name.

        Strips common patterns like CloudFormation suffixes, account IDs,
        regions, timestamps, etc.

        Returns:
            Tuple of (cleaned_name, list_of_extracted_patterns)
        """
        extracted = []
        result = name

        # Patterns to extract (ordered by specificity)
        extraction_patterns = [
            # CloudFormation suffix (uppercase alphanumeric, 8-13 chars at end)
            (r"-[A-Z0-9]{8,13}$", "cfn_suffix"),
            # Bedrock/Kendra suffix (underscore + lowercase alphanumeric)
            (r"_[a-z0-9]{4,6}$", "bedrock_suffix"),
            # Account ID (12 digits, with optional surrounding hyphens)
            (r"-?\d{12}-?", "account_id"),
            # Region (e.g., us-east-1, eu-west-2)
            (r"-?(us|eu|ap|sa|ca|me|af)-(east|west|north|south|central|northeast|southeast)-\d-?", "region"),
            # Hex suffix (8+ lowercase hex chars at end)
            (r"-[a-f0-9]{8,}$", "hex_suffix"),
            # Timestamp suffix (8-14 digits at end)
            (r"-\d{8,14}$", "timestamp"),
        ]

        for pattern, _pattern_name in extraction_patterns:
            # Note: Don't use IGNORECASE - CloudFormation suffixes are uppercase,
            # and we want case-sensitive matching for accuracy
            match = re.search(pattern, result)
            if match:
                extracted.append(match.group().strip("-"))
                result = result[: match.start()] + result[match.end() :]

        # Clean up trailing/leading separators
        result = re.sub(r"^[-_]+|[-_]+$", "", result)
        # Collapse multiple separators
        result = re.sub(r"[-_]{2,}", "-", result)

        return result, extracted

    def _try_rules_based(self, resource: Dict[str, Any]) -> Optional[str]:
        """Try to normalize using rules.

        Priority:
        1. CloudFormation logical ID tag
        2. Name tag (if clean)
        3. Physical name (if clean)

        Returns None if name appears to have random patterns.
        """
        tags = resource.get("tags", {}) or {}
        name = resource.get("name", "")

        # 1. CloudFormation logical ID is the best canonical identifier
        logical_id = tags.get("aws:cloudformation:logical-id")
        if logical_id:
            return self._basic_normalize(logical_id)

        # 2. Name tag (if it looks clean)
        name_tag = tags.get("Name")
        if name_tag and not self._has_random_patterns(name_tag):
            return self._basic_normalize(name_tag)

        # 3. Physical name (if it looks clean)
        if name and not self._has_random_patterns(name):
            return self._basic_normalize(name)

        # Name has random patterns - needs AI
        return None

    def _has_random_patterns(self, name: str) -> bool:
        """Check if name contains random-looking patterns."""
        if not name:
            return True

        for pattern in self._random_patterns:
            if pattern.search(name):
                return True
        return False

    def _basic_normalize(self, name: str) -> str:
        """Basic string normalization without AI.

        - Lowercase
        - Replace underscores/spaces with hyphens
        - Strip leading/trailing hyphens
        """
        if not name:
            return ""

        result = name.lower()
        result = re.sub(r"[_\s]+", "-", result)
        result = re.sub(r"-+", "-", result)
        return result.strip("-")

    def _normalize_with_ai(
        self,
        resources: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Normalize resources using AI.

        Batches resources and calls the AI API.

        Args:
            resources: Resources that need AI normalization

        Returns:
            Dict mapping ARN -> normalized_name
        """
        results: Dict[str, str] = {}

        # Process in batches
        for i in range(0, len(resources), self.config.max_batch_size):
            batch = resources[i : i + self.config.max_batch_size]
            batch_results = self._process_ai_batch(batch)
            results.update(batch_results)

        return results

    def _process_ai_batch(
        self,
        resources: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Process a single batch through the AI.

        Args:
            resources: Batch of resources

        Returns:
            Dict mapping ARN -> normalized_name
        """
        # Build the user prompt with resource details
        resource_list = []
        for r in resources:
            item = {
                "arn": r.get("arn", ""),
                "name": r.get("name", ""),
                "type": r.get("resource_type", ""),
            }
            # Include Name tag if present
            tags = r.get("tags", {}) or {}
            if tags.get("Name"):
                item["name_tag"] = tags["Name"]
            resource_list.append(item)

        user_prompt = json.dumps({"resources": resource_list}, indent=2)

        # Call the AI with retries
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": NORMALIZATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,  # Low for consistency
                )

                # Track token usage
                if hasattr(response, "usage") and response.usage:
                    self._total_tokens += response.usage.total_tokens

                # Parse response
                content = response.choices[0].message.content
                return self._parse_ai_response(content, resources)

            except Exception as e:
                wait_time = 2**attempt
                logger.warning(f"AI normalization attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                if attempt < self.config.max_retries - 1:
                    time.sleep(wait_time)

        # All retries failed - use fallback
        logger.error("AI normalization failed after all retries")
        return {r.get("arn", ""): self._basic_normalize(r.get("name", "")) for r in resources}

    def _parse_ai_response(
        self,
        content: str,
        resources: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Parse AI response into ARN -> normalized_name mapping.

        Args:
            content: AI response content (JSON string)
            resources: Original resources (for fallback)

        Returns:
            Dict mapping ARN -> normalized_name
        """
        try:
            data = json.loads(content)
            normalizations = data.get("normalizations", [])

            results = {}
            for norm in normalizations:
                arn = norm.get("arn", "")
                normalized_name = norm.get("normalized_name", "")
                if arn and normalized_name:
                    results[arn] = normalized_name

            # Fallback for any missing
            for r in resources:
                arn = r.get("arn", "")
                if arn and arn not in results:
                    results[arn] = self._basic_normalize(r.get("name", ""))

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response content: {content[:500]}...")
            return {r.get("arn", ""): self._basic_normalize(r.get("name", "")) for r in resources}
