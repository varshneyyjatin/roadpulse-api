"""
Schemas for dashboard API.

Date/Time filtering rules (enforced at schema level):
  - start_date / end_date accept either a `date` or a `datetime`.
  - If EITHER value carries a non-midnight / non-end-of-day time component the
    request is considered a "time-filtered" request.
  - Time-filtered requests are only valid when start and end fall on the
    SAME calendar date.  Cross-day time windows are explicitly rejected here so
    that the route handler never has to think about it.
"""
from __future__ import annotations
from datetime import date, datetime, time
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_MIDNIGHT: time = time(0, 0, 0)
_END_OF_DAY: time = time(23, 59, 59, 999999)

def _has_time_component(value: Union[date, datetime, None]) -> bool:
    """Return True when *value* is a datetime with a meaningful time part."""
    if not isinstance(value, datetime):
        return False
    t = value.time()
    # Treat midnight as "no time specified" (common default) and
    # end-of-day as "no time specified" (common default for end bounds).
    return t not in (_MIDNIGHT, _END_OF_DAY)

def _to_date(value: Union[date, datetime, None]) -> Optional[date]:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ScopeEnum(str, Enum):
    dashboard = "dashboard"
    report = "report"

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class VehicleLogsRequest(BaseModel):
    scope: ScopeEnum = Field(
        default=ScopeEnum.dashboard,
        description="Scope of the request: 'dashboard' (≤30 days) or 'report' (≤90 days).",
    )
    location_ids: Optional[List[int]] = Field(
        default=None,
        description="Specific location IDs to query. None = all accessible locations.",
    )
    checkpoint_ids: Optional[List[int]] = Field(
        default=None,
        description="Specific checkpoint IDs to query. None = all accessible checkpoints.",
    )
    start_date: Optional[Union[datetime, date]] = Field(
        default=None,
        description=(
            "Range start.  Accepts a plain date (e.g. '2025-01-01') or a full "
            "datetime with time (e.g. '2025-01-01T08:30:00').  "
            "When a time is supplied the request becomes time-filtered and "
            "start_date + end_date must share the same calendar date."
        ),
    )
    end_date: Optional[Union[datetime, date]] = Field(
        default=None,
        description=(
            "Range end.  Same rules as start_date apply.  "
            "Must be ≥ start_date."
        ),
    )
    is_blacklisted: Optional[bool] = Field(
        default=None,
        description="Filter by blacklist status. None = include all.",
    )
    is_whitelisted: Optional[bool] = Field(
        default=None,
        description="Filter by whitelist status. None = include all.",
    )
    plate_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="Exact plate number search (case-insensitive). Report scope only.",
    )
    page: int = Field(default=1, ge=1, description="1-based page number.")
    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Records per page (1–500).",
    )
    excel_report: bool = Field(
        default=False,
        description="Stream an Excel file instead of JSON. Report scope only.",
    )

    # ------------------------------------------------------------------
    # Computed properties (available after validation)
    # ------------------------------------------------------------------
    @property
    def is_time_filtered(self) -> bool:
        """True when the caller supplied an intra-day time window."""
        return _has_time_component(self.start_date) or _has_time_component(self.end_date)

    @property
    def start_date_only(self) -> Optional[date]:
        return _to_date(self.start_date)

    @property
    def end_date_only(self) -> Optional[date]:
        return _to_date(self.end_date)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _validate_date_range(self) -> "VehicleLogsRequest":
        start = self.start_date
        end = self.end_date

        # ── 1. end must not be before start ──────────────────────────
        if start is not None and end is not None:
            start_dt = start if isinstance(start, datetime) else datetime.combine(start, _MIDNIGHT)
            end_dt = end if isinstance(end, datetime) else datetime.combine(end, _END_OF_DAY)
            if end_dt < start_dt:
                raise ValueError("end_date must be greater than or equal to start_date.")

        # ── 2. Time-filtering rules ───────────────────────────────────
        if self.is_time_filtered:
            # Both bounds must be present when time is involved so that the
            # window is unambiguous.
            if start is None or end is None:
                raise ValueError(
                    "Both start_date and end_date are required when specifying a time component."
                )

            start_day = self.start_date_only
            end_day = self.end_date_only

            if start_day != end_day:
                raise ValueError(
                    "Time filtering is only allowed within a single calendar date. "
                    "start_date and end_date must fall on the same day when a time "
                    "component is provided."
                )

        # ── 3. Scope-specific date-range caps ─────────────────────────
        if start is not None and end is not None:
            delta_days = (self.end_date_only - self.start_date_only).days  # type: ignore[operator]
            max_days = 30 if self.scope == ScopeEnum.dashboard else 90
            scope_label = "Dashboard" if self.scope == ScopeEnum.dashboard else "Report"

            if delta_days > max_days:
                raise ValueError(
                    f"{scope_label} scope supports a maximum date range of {max_days} days. "
                    f"Requested range spans {delta_days} days."
                )

        return self

class FixVehicleNumberRequest(BaseModel):
    record_id: int = Field(..., description="Primary key of the TrnVehicleLog record.")
    old_value: str = Field(..., description="Current (incorrect) plate number.")
    new_value: str = Field(..., description="Corrected plate number.")
    change_reason: str = Field(..., description="Mandatory reason for the correction.")

    @model_validator(mode="after")
    def _old_and_new_must_differ(self) -> "FixVehicleNumberRequest":
        if self.old_value.strip().upper() == self.new_value.strip().upper():
            raise ValueError("old_value and new_value must be different.")
        return self