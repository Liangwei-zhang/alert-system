"""
Signal clustering for similar signals.

Features:
- Cluster signals by price level proximity
- Cluster by time similarity
- Cluster by indicator patterns
- Deduplicate similar signals
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from domains.signals.signal import Signal, SignalType, SignalStatus


@dataclass
class SignalCluster:
    """Group of similar signals."""
    cluster_id: int
    signals: list[Signal]
    avg_price: float
    avg_confidence: float
    primary_direction: SignalType
    time_range: tuple[datetime, datetime]
    representative: Signal  # Best signal in cluster


@dataclass  
class ClusterConfig:
    """Configuration for signal clustering."""
    price_tolerance_pct: float = 2.0  # 2% price proximity
    time_window_minutes: int = 60  # Within 1 hour
    min_cluster_size: int = 2  # Minimum signals to form cluster


class PriceClusterer:
    """Cluster signals by price level proximity."""
    
    def __init__(self, config: ClusterConfig = None):
        self.config = config or ClusterConfig()
    
    def cluster_by_price(
        self,
        signals: list[Signal],
        direction: Optional[SignalType] = None
    ) -> list[SignalCluster]:
        """
        Cluster signals by price proximity.
        
        Args:
            signals: List of signals to cluster
            direction: Optional filter by signal type
            
        Returns:
            List of signal clusters
        """
        if not signals:
            return []
        
        # Filter by direction if specified
        if direction:
            filtered = [s for s in signals if s.signal_type == direction]
        else:
            filtered = signals
        
        if len(filtered) < self.config.min_cluster_size:
            return []
        
        # Sort by entry price
        sorted_signals = sorted(filtered, key=lambda s: float(s.entry_price))
        
        clusters = []
        current_cluster = [sorted_signals[0]]
        
        for i in range(1, len(sorted_signals)):
            current = sorted_signals[i]
            previous = current_cluster[-1]
            
            # Check price proximity
            price_diff_pct = abs(
                float(current.entry_price) - float(previous.entry_price)
            ) / float(previous.entry_price) * 100
            
            if price_diff_pct <= self.config.price_tolerance_pct:
                current_cluster.append(current)
            else:
                # Close current cluster and start new one
                if len(current_cluster) >= self.config.min_cluster_size:
                    clusters.append(self._create_cluster(current_cluster, len(clusters)))
                current_cluster = [current]
        
        # Don't forget last cluster
        if len(current_cluster) >= self.config.min_cluster_size:
            clusters.append(self._create_cluster(current_cluster, len(clusters)))
        
        return clusters
    
    def _create_cluster(
        self,
        signals: list[Signal],
        cluster_id: int
    ) -> SignalCluster:
        """Create a signal cluster from signals."""
        prices = [float(s.entry_price) for s in signals]
        confidences = [s.confidence for s in signals]
        
        # Determine primary direction (mode)
        buy_count = sum(1 for s in signals if s.signal_type == SignalType.BUY)
        sell_count = sum(1 for s in signals if s.signal_type == SignalType.SELL)
        primary_direction = SignalType.BUY if buy_count >= sell_count else SignalType.SELL
        
        # Get representative (highest confidence)
        representative = max(signals, key=lambda s: s.confidence)
        
        # Time range
        times = [s.generated_at for s in signals]
        
        return SignalCluster(
            cluster_id=cluster_id,
            signals=signals,
            avg_price=np.mean(prices),
            avg_confidence=np.mean(confidences),
            primary_direction=primary_direction,
            time_range=(min(times), max(times)),
            representative=representative
        )


class TimeClusterer:
    """Cluster signals by time proximity."""
    
    def __init__(self, config: ClusterConfig = None):
        self.config = config or ClusterConfig()
    
    def cluster_by_time(
        self,
        signals: list[Signal]
    ) -> list[SignalCluster]:
        """
        Cluster signals by time proximity.
        
        Args:
            signals: List of signals to cluster
            
        Returns:
            List of signal clusters
        """
        if not signals:
            return []
        
        # Sort by time
        sorted_signals = sorted(signals, key=lambda s: s.generated_at)
        
        clusters = []
        current_cluster = [sorted_signals[0]]
        
        window = timedelta(minutes=self.config.time_window_minutes)
        
        for i in range(1, len(sorted_signals)):
            current = sorted_signals[i]
            previous = current_cluster[-1]
            
            # Check time proximity
            time_diff = current.generated_at - previous.generated_at
            
            if time_diff <= window:
                current_cluster.append(current)
            else:
                if len(current_cluster) >= self.config.min_cluster_size:
                    clusters.append(self._create_cluster(current_cluster, len(clusters)))
                current_cluster = [current]
        
        if len(current_cluster) >= self.config.min_cluster_size:
            clusters.append(self._create_cluster(current_cluster, len(clusters)))
        
        return clusters
    
    def _create_cluster(
        self,
        signals: list[Signal],
        cluster_id: int
    ) -> SignalCluster:
        """Create a signal cluster from time-grouped signals."""
        prices = [float(s.entry_price) for s in signals]
        confidences = [s.confidence for s in signals]
        
        buy_count = sum(1 for s in signals if s.signal_type == SignalType.BUY)
        sell_count = sum(1 for s in signals if s.signal_type == SignalType.SELL)
        primary_direction = SignalType.BUY if buy_count >= sell_count else SignalType.SELL
        
        representative = max(signals, key=lambda s: s.confidence)
        
        times = [s.generated_at for s in signals]
        
        return SignalCluster(
            cluster_id=cluster_id,
            signals=signals,
            avg_price=np.mean(prices),
            avg_confidence=np.mean(confidences),
            primary_direction=primary_direction,
            time_range=(min(times), max(times)),
            representative=representative
        )


class MultiDimensionalClusterer:
    """Cluster signals by multiple dimensions (price + time + indicators)."""
    
    def __init__(self, config: ClusterConfig = None):
        self.config = config or ClusterConfig()
        self.price_clusterer = PriceClusterer(config)
        self.time_clusterer = TimeClusterer(config)
    
    def cluster(
        self,
        signals: list[Signal]
    ) -> list[SignalCluster]:
        """
        Cluster signals using both price and time proximity.
        
        Args:
            signals: List of signals to cluster
            
        Returns:
            List of consolidated clusters
        """
        if not signals:
            return []
        
        # First cluster by price
        price_clusters = self.price_clusterer.cluster_by_price(signals)
        
        # Then refine by time within each price cluster
        all_clusters = []
        
        for price_cluster in price_clusters:
            # Cluster signals within this price cluster by time
            time_clusters = self.time_clusterer.cluster_by_time(
                price_cluster.signals
            )
            
            for tc in time_clusters:
                tc.cluster_id = len(all_clusters)
                all_clusters.append(tc)
        
        return all_clusters
    
    def deduplicate(
        self,
        signals: list[Signal]
    ) -> list[Signal]:
        """
        Deduplicate signals - keep best from each cluster.
        
        Args:
            signals: List of signals to deduplicate
            
        Returns:
            List of deduplicated signals (best from each cluster)
        """
        clusters = self.cluster(signals)
        
        # Keep representative from each cluster
        deduplicated = []
        for cluster in clusters:
            deduplicated.append(cluster.representative)
        
        # Sort by generated_at
        deduplicated.sort(key=lambda s: s.generated_at, reverse=True)
        
        return deduplicated


class SignalClusterService:
    """Service for managing signal clusters."""
    
    def __init__(self, db: Session, config: ClusterConfig = None):
        self.db = db
        self.config = config or ClusterConfig()
        self.clusterer = MultiDimensionalClusterer(config)
    
    def cluster_pending_signals(
        self,
        symbol: Optional[str] = None
    ) -> list[SignalCluster]:
        """
        Cluster pending signals.
        
        Args:
            symbol: Optional filter by symbol
            
        Returns:
            List of signal clusters
        """
        query = self.db.query(Signal).filter(
            Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
        )
        
        if symbol:
            query = query.filter(Signal.symbol == symbol.upper())
        
        signals = query.all()
        
        return self.clusterer.cluster(signals)
    
    def get_cluster_summary(
        self,
        symbol: Optional[str] = None
    ) -> dict:
        """
        Get summary of signal clusters.
        
        Args:
            symbol: Optional filter by symbol
            
        Returns:
            Dict with cluster summary
        """
        clusters = self.cluster_pending_signals(symbol)
        
        if not clusters:
            return {
                "total_clusters": 0,
                "total_signals": 0,
                "avg_confidence": 0,
                "bullish_clusters": 0,
                "bearish_clusters": 0
            }
        
        total_signals = sum(len(c.signals) for c in clusters)
        avg_confidence = np.mean([c.avg_confidence for c in clusters])
        
        bullish = sum(1 for c in clusters 
                    if c.primary_direction == SignalType.BUY)
        bearish = sum(1 for c in clusters 
                   if c.primary_direction == SignalType.SELL)
        
        return {
            "total_clusters": len(clusters),
            "total_signals": total_signals,
            "avg_confidence": round(avg_confidence, 1),
            "bullish_clusters": bullish,
            "bearish_clusters": bearish,
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "symbol": c.representative.symbol,
                    "size": len(c.signals),
                    "avg_price": round(c.avg_price, 2),
                    "avg_confidence": round(c.avg_confidence, 1),
                    "direction": c.primary_direction.value,
                    "representative_id": c.representative.id
                }
                for c in clusters[:10]  # Top 10
            ]
        }
    
    def get_consolidated_signals(
        self,
        symbol: Optional[str] = None
    ) -> list[Signal]:
        """
        Get consolidated (deduplicated) signals.
        
        Args:
            symbol: Optional filter by symbol
            
        Returns:
            List of best signals from each cluster
        """
        clusters = self.cluster_pending_signals(symbol)
        
        # Get representative from each cluster
        signals = [c.representative for c in clusters]
        
        # Sort by confidence descending
        signals.sort(key=lambda s: s.confidence, reverse=True)
        
        return signals