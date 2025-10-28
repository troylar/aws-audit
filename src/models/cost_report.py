"""Cost report models for cost analysis and tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CostBreakdown:
    """Represents cost breakdown for baseline or non-baseline resources."""

    total: float
    by_service: Dict[str, float] = field(default_factory=dict)
    percentage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total": self.total,
            "by_service": self.by_service,
            "percentage": self.percentage,
        }


@dataclass
class CostReport:
    """Represents cost analysis separating baseline vs non-baseline costs."""

    generated_at: datetime
    baseline_snapshot_name: str
    period_start: datetime
    period_end: datetime
    baseline_costs: CostBreakdown
    non_baseline_costs: CostBreakdown
    total_cost: float
    data_complete: bool = True
    data_through: Optional[datetime] = None
    lag_days: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "baseline_snapshot_name": self.baseline_snapshot_name,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "baseline_costs": self.baseline_costs.to_dict(),
            "non_baseline_costs": self.non_baseline_costs.to_dict(),
            "total_cost": self.total_cost,
            "data_complete": self.data_complete,
            "data_through": self.data_through.isoformat() if self.data_through else None,
            "lag_days": self.lag_days,
            "summary": {
                "baseline_total": self.baseline_costs.total,
                "baseline_percentage": self.baseline_costs.percentage,
                "non_baseline_total": self.non_baseline_costs.total,
                "non_baseline_percentage": self.non_baseline_costs.percentage,
                "total": self.total_cost,
            },
        }

    @property
    def baseline_percentage(self) -> float:
        """Get baseline cost percentage."""
        return self.baseline_costs.percentage

    @property
    def non_baseline_percentage(self) -> float:
        """Get non-baseline cost percentage."""
        return self.non_baseline_costs.percentage

    def get_top_services(self, limit: int = 5, baseline: bool = True) -> Dict[str, float]:
        """Get top N services by cost.

        Args:
            limit: Number of top services to return
            baseline: If True, return baseline services; if False, non-baseline

        Returns:
            Dictionary of service name to cost, sorted by cost descending
        """
        services = self.baseline_costs.by_service if baseline else self.non_baseline_costs.by_service

        # Sort by cost descending
        sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)

        return dict(sorted_services[:limit])
