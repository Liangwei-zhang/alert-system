"""
OHLCV data quality service - detect and report data quality issues.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domains.market_data.repository import (
    SymbolRepository,
    OhlcvRepository,
    OhlcvAnomalyRepository,
)
from domains.market_data.schemas import AnomalyType, AnomalySeverity

logger = logging.getLogger(__name__)


class OhlcvQualityService:
    """Service for checking and maintaining OHLCV data quality."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.symbol_repo = SymbolRepository(session)
        self.ohlcv_repo = OhlcvRepository(session)
        self.anomaly_repo = OhlcvAnomalyRepository(session)

    async def check_symbol_quality(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
    ) -> Dict[str, Any]:
        """
        Run quality checks on OHLCV data for a symbol.
        
        Returns quality report with anomalies and score.
        """
        symbol_obj = await self.symbol_repo.get_by_symbol(symbol)
        if not symbol_obj:
            return {"success": False, "error": f"Symbol {symbol} not found"}

        # Get OHLCV data
        ohlcv_data = await self.ohlcv_repo.get_by_symbol_timeframe(
            symbol_obj.id,
            timeframe,
            start_date,
            end_date,
        )

        if not ohlcv_data:
            return {
                "success": True,
                "symbol": symbol,
                "total_records": 0,
                "anomalies_count": 0,
                "quality_score": 100.0,
                "anomalies": [],
            }

        # Run quality checks
        anomalies = await self._run_quality_checks(ohlcv_data, symbol_obj.id)

        # Calculate quality score
        quality_score = self._calculate_quality_score(len(ohlcv_data), len(anomalies))

        return {
            "success": True,
            "symbol": symbol,
            "symbol_id": symbol_obj.id,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "total_records": len(ohlcv_data),
            "anomalies_count": len(anomalies),
            "quality_score": quality_score,
            "anomalies": [
                {
                    "id": a.id,
                    "anomaly_type": a.anomaly_type.value,
                    "severity": a.severity,
                    "field_name": a.field_name,
                    "expected_value": a.expected_value,
                    "actual_value": a.actual_value,
                    "description": a.description,
                    "detected_at": a.detected_at,
                }
                for a in anomalies
            ],
        }

    async def _run_quality_checks(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Run all quality checks and create anomaly records."""
        anomalies = []
        
        # Check 1: Price validation
        price_anomalies = await self._check_price_validity(ohlcv_data, symbol_id)
        anomalies.extend(price_anomalies)
        
        # Check 2: Volume validation
        volume_anomalies = await self._check_volume_validity(ohlcv_data, symbol_id)
        anomalies.extend(volume_anomalies)
        
        # Check 3: High/Low relationship
        hl_anomalies = await self._check_high_low_relationship(ohlcv_data, symbol_id)
        anomalies.extend(hl_anomalies)
        
        # Check 4: Open/Close relationship
        oc_anomalies = await self._check_open_close_relationship(ohlcv_data, symbol_id)
        anomalies.extend(oc_anomalies)
        
        # Check 5: Duplicate timestamps
        dup_anomalies = await self._check_duplicates(ohlcv_data, symbol_id)
        anomalies.extend(dup_anomalies)
        
        # Check 6: Missing data gaps
        gap_anomalies = await self._check_gaps(ohlcv_data, symbol_id)
        anomalies.extend(gap_anomalies)
        
        # Check 7: Price spikes
        spike_anomalies = await self._check_price_spikes(ohlcv_data, symbol_id)
        anomalies.extend(spike_anomalies)
        
        # Check 8: Volume spikes
        vol_spike_anomalies = await self._check_volume_spikes(ohlcv_data, symbol_id)
        anomalies.extend(vol_spike_anomalies)
        
        return anomalies

    async def _check_price_validity(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check for invalid or negative prices."""
        anomalies = []
        
        for record in ohlcv_data:
            issues = []
            
            for field in ["open", "high", "low", "close"]:
                value = getattr(record, field)
                if value is None:
                    issues.append(f"{field} is None")
                elif value < 0:
                    issues.append(f"{field} is negative: {value}")
                elif value == 0:
                    issues.append(f"{field} is zero")
            
            if issues:
                anomaly = await self.anomaly_repo.create({
                    "ohlcv_id": record.id,
                    "symbol_id": symbol_id,
                    "anomaly_type": AnomalyType.INVALID_PRICE,
                    "severity": "high",
                    "field_name": ", ".join(issues),
                    "expected_value": "> 0",
                    "actual_value": str(issues),
                    "description": f"Invalid price values: {', '.join(issues)}",
                })
                anomalies.append(anomaly)
        
        return anomalies

    async def _check_volume_validity(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check for zero or negative volume."""
        anomalies = []
        
        for record in ohlcv_data:
            if record.volume is None or record.volume < 0:
                anomaly = await self.anomaly_repo.create({
                    "ohlcv_id": record.id,
                    "symbol_id": symbol_id,
                    "anomaly_type": AnomalyType.ZERO_VOLUME,
                    "severity": "medium",
                    "field_name": "volume",
                    "expected_value": "> 0",
                    "actual_value": str(record.volume),
                    "description": f"Invalid volume: {record.volume}",
                })
                anomalies.append(anomaly)
        
        return anomalies

    async def _check_high_low_relationship(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check that high >= low."""
        anomalies = []
        
        for record in ohlcv_data:
            if record.high is not None and record.low is not None:
                if record.high < record.low:
                    anomaly = await self.anomaly_repo.create({
                        "ohlcv_id": record.id,
                        "symbol_id": symbol_id,
                        "anomaly_type": AnomalyType.INVALID_PRICE,
                        "severity": "high",
                        "field_name": "high, low",
                        "expected_value": "high >= low",
                        "actual_value": f"high={record.high}, low={record.low}",
                        "description": f"High ({record.high}) is less than low ({record.low})",
                    })
                    anomalies.append(anomaly)
        
        return anomalies

    async def _check_open_close_relationship(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check that open and close are within high-low range."""
        anomalies = []
        
        for record in ohlcv_data:
            if all(v is not None for v in [record.open, record.close, record.high, record.low]):
                if record.open > record.high or record.open < record.low:
                    anomaly = await self.anomaly_repo.create({
                        "ohlcv_id": record.id,
                        "symbol_id": symbol_id,
                        "anomaly_type": AnomalyType.INVALID_PRICE,
                        "severity": "medium",
                        "field_name": "open",
                        "expected_value": f"between {record.low} and {record.high}",
                        "actual_value": str(record.open),
                        "description": f"Open ({record.open}) is outside high-low range",
                    })
                    anomalies.append(anomaly)
                
                if record.close > record.high or record.close < record.low:
                    anomaly = await self.anomaly_repo.create({
                        "ohlcv_id": record.id,
                        "symbol_id": symbol_id,
                        "anomaly_type": AnomalyType.INVALID_PRICE,
                        "severity": "medium",
                        "field_name": "close",
                        "expected_value": f"between {record.low} and {record.high}",
                        "actual_value": str(record.close),
                        "description": f"Close ({record.close}) is outside high-low range",
                    })
                    anomalies.append(anomaly)
        
        return anomalies

    async def _check_duplicates(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check for duplicate timestamps."""
        timestamps = {}
        anomalies = []
        
        for record in ohlcv_data:
            ts_key = (record.timestamp, record.timeframe)
            if ts_key in timestamps:
                anomaly = await self.anomaly_repo.create({
                    "ohlcv_id": record.id,
                    "symbol_id": symbol_id,
                    "anomaly_type": AnomalyType.DUPLICATE_TIMESTAMP,
                    "severity": "high",
                    "field_name": "timestamp",
                    "expected_value": "unique",
                    "actual_value": str(record.timestamp),
                    "description": f"Duplicate timestamp found: {record.timestamp}",
                })
                anomalies.append(anomaly)
            else:
                timestamps[ts_key] = record.id
        
        return anomalies

    async def _check_gaps(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check for missing data gaps (for daily data)."""
        anomalies = []
        
        if not ohlcv_data:
            return anomalies
        
        # Sort by timestamp
        sorted_data = sorted(ohlcv_data, key=lambda x: x.timestamp)
        
        # Check for gaps > 2 days for daily data
        for i in range(1, len(sorted_data)):
            prev_ts = sorted_data[i - 1].timestamp
            curr_ts = sorted_data[i].timestamp
            gap_days = (curr_ts - prev_ts).days
            
            if gap_days > 2:  # More than 2 days gap (skip weekends)
                anomaly = await self.anomaly_repo.create({
                    "symbol_id": symbol_id,
                    "anomaly_type": AnomalyType.GAP,
                    "severity": "low",
                    "field_name": "timestamp",
                    "expected_value": f"consecutive or 1-2 day gap",
                    "actual_value": f"{gap_days} days gap",
                    "description": f"Missing data gap: {prev_ts} to {curr_ts} ({gap_days} days)",
                })
                anomalies.append(anomaly)
        
        return anomalies

    async def _check_price_spikes(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check for abnormal price changes (>50% day-over-day)."""
        anomalies = []
        
        sorted_data = sorted(ohlcv_data, key=lambda x: x.timestamp)
        
        for i in range(1, len(sorted_data)):
            prev_close = sorted_data[i - 1].close
            curr_close = sorted_data[i].close
            
            if prev_close and curr_close and prev_close > 0:
                pct_change = abs(curr_close - prev_close) / prev_close
                
                if pct_change > 0.5:  # > 50% change
                    anomaly = await self.anomaly_repo.create({
                        "ohlcv_id": sorted_data[i].id,
                        "symbol_id": symbol_id,
                        "anomaly_type": AnomalyType.PRICE_SPIKE,
                        "severity": "high",
                        "field_name": "close",
                        "expected_value": "< 50% change",
                        "actual_value": f"{pct_change*100:.1f}% change",
                        "description": f"Price spike detected: {pct_change*100:.1f}% change",
                    })
                    anomalies.append(anomaly)
        
        return anomalies

    async def _check_volume_spikes(
        self,
        ohlcv_data: List[Any],
        symbol_id: int,
    ) -> List[Any]:
        """Check for abnormal volume (>5x average)."""
        anomalies = []
        
        if len(ohlcv_data) < 5:
            return anomalies
        
        # Calculate average volume
        volumes = [r.volume for r in ohlcv_data if r.volume]
        if not volumes:
            return anomalies
            
        avg_volume = sum(volumes) / len(volumes)
        
        for record in ohlcv_data:
            if record.volume and avg_volume > 0:
                vol_ratio = record.volume / avg_volume
                
                if vol_ratio > 5:  # > 5x average
                    anomaly = await self.anomaly_repo.create({
                        "ohlcv_id": record.id,
                        "symbol_id": symbol_id,
                        "anomaly_type": AnomalyType.VOLUME_SPIKE,
                        "severity": "medium",
                        "field_name": "volume",
                        "expected_value": f"< 5x avg ({avg_volume:.0f})",
                        "actual_value": f"{vol_ratio:.1f}x avg ({record.volume})",
                        "description": f"Volume spike: {vol_ratio:.1f}x average",
                    })
                    anomalies.append(anomaly)
        
        return anomalies

    def _calculate_quality_score(self, total_records: int, anomaly_count: int) -> float:
        """Calculate quality score (0-100)."""
        if total_records == 0:
            return 100.0
        
        # Base score
        score = 100.0
        
        # Deduct points based on anomaly severity
        # This is a simplified scoring - could be enhanced
        if anomaly_count > 0:
            # Deduct 5 points per anomaly, max 100 points
            deduction = min(anomaly_count * 5, 100)
            score = max(0, score - deduction)
        
        return round(score, 2)

    async def resolve_anomaly(
        self,
        anomaly_id: int,
        notes: Optional[str] = None,
    ) -> bool:
        """Mark an anomaly as resolved."""
        anomaly = await self.anomaly_repo.resolve(anomaly_id, notes)
        return anomaly is not None

    async def get_unresolved_anomalies(
        self,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """Get all unresolved anomalies for a symbol."""
        symbol_obj = await self.symbol_repo.get_by_symbol(symbol)
        if not symbol_obj:
            return []
        
        anomalies = await self.anomaly_repo.get_by_symbol(
            symbol_obj.id,
            resolved=False,
        )
        
        return [
            {
                "id": a.id,
                "ohlcv_id": a.ohlcv_id,
                "anomaly_type": a.anomaly_type.value,
                "severity": a.severity,
                "description": a.description,
                "detected_at": a.detected_at,
            }
            for a in anomalies
        ]