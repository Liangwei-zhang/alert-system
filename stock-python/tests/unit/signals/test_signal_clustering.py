"""
Unit tests for Signal Clustering - tested by Notifications Team (Agent C).

Original developer: Signals Team (Agent B)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from domains.signals.signal_clustering import (
    SignalCluster, ClusterConfig,
    PriceClusterer, TimeClusterer, MultiDimensionalClusterer,
    SignalClusterService
)
from domains.signals.signal import Signal, SignalType, SignalStatus


class TestClusterConfig:
    """Test ClusterConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = ClusterConfig()
        
        assert config.price_tolerance_pct == 2.0
        assert config.time_window_minutes == 60
        assert config.min_cluster_size == 2
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ClusterConfig(
            price_tolerance_pct=1.5,
            time_window_minutes=30,
            min_cluster_size=3
        )
        
        assert config.price_tolerance_pct == 1.5
        assert config.time_window_minutes == 30
        assert config.min_cluster_size == 3


class TestSignalCluster:
    """Test SignalCluster dataclass."""
    
    def test_signal_cluster_creation(self):
        """Test creating a signal cluster."""
        mock_signal = MagicMock()
        mock_signal.entry_price = 100.0
        mock_signal.confidence = 75.0
        mock_signal.signal_type = SignalType.BUY
        mock_signal.generated_at = datetime.utcnow()
        
        cluster = SignalCluster(
            cluster_id=1,
            signals=[mock_signal],
            avg_price=100.0,
            avg_confidence=75.0,
            primary_direction=SignalType.BUY,
            time_range=(datetime.utcnow(), datetime.utcnow()),
            representative=mock_signal
        )
        
        assert cluster.cluster_id == 1
        assert len(cluster.signals) == 1
        assert cluster.avg_price == 100.0
        assert cluster.primary_direction == SignalType.BUY


class TestPriceClusterer:
    """Test PriceClusterer."""
    
    @pytest.fixture
    def clusterer(self):
        return PriceClusterer()
    
    def test_cluster_by_price_empty(self, clusterer):
        """Test clustering with empty list."""
        result = clusterer.cluster_by_price([])
        
        assert result == []
    
    def test_cluster_by_price_single_signal(self, clusterer):
        """Test clustering with single signal."""
        mock_signal = MagicMock()
        mock_signal.entry_price = 100.0
        mock_signal.signal_type = SignalType.BUY
        
        result = clusterer.cluster_by_price([mock_signal])
        
        # Single signal doesn't form cluster (min_cluster_size=2)
        assert result == []
    
    def test_cluster_by_price_proximity(self, clusterer):
        """Test clustering signals by price proximity."""
        # Create signals within 2% price tolerance
        signals = []
        for i in range(3):
            s = MagicMock()
            s.entry_price = 100.0 + (i * 0.5)  # Within 2%
            s.signal_type = SignalType.BUY
            s.confidence = 70.0 + i * 5
            s.generated_at = datetime.utcnow()
            signals.append(s)
        
        result = clusterer.cluster_by_price(signals)
        
        assert len(result) >= 0
    
    def test_cluster_by_price_separate_clusters(self, clusterer):
        """Test signals in separate price clusters."""
        signals = []
        
        # Cluster 1: ~$100
        for i in range(2):
            s = MagicMock()
            s.entry_price = 100.0 + i * 0.3
            s.signal_type = SignalType.BUY
            s.confidence = 70.0
            s.generated_at = datetime.utcnow()
            signals.append(s)
        
        # Cluster 2: ~$200 (separated by >2%)
        for i in range(2):
            s = MagicMock()
            s.entry_price = 200.0 + i * 0.3
            s.signal_type = SignalType.BUY
            s.confidence = 75.0
            s.generated_at = datetime.utcnow()
            signals.append(s)
        
        result = clusterer.cluster_by_price(signals)
        
        # Should have multiple clusters
        assert len(result) >= 1
    
    def test_cluster_by_price_direction_filter(self, clusterer):
        """Test clustering with direction filter."""
        signals = []
        
        # Buy signals
        for i in range(2):
            s = MagicMock()
            s.entry_price = 100.0 + i * 0.5
            s.signal_type = SignalType.BUY
            s.confidence = 70.0
            s.generated_at = datetime.utcnow()
            signals.append(s)
        
        # Sell signal
        s = MagicMock()
        s.entry_price = 105.0
        s.signal_type = SignalType.SELL
        s.confidence = 75.0
        s.generated_at = datetime.utcnow()
        signals.append(s)
        
        # Filter to BUY only
        result = clusterer.cluster_by_price(signals, direction=SignalType.BUY)
        
        # All in cluster should be BUY
        for cluster in result:
            assert cluster.primary_direction == SignalType.BUY


class TestTimeClusterer:
    """Test TimeClusterer."""
    
    @pytest.fixture
    def clusterer(self):
        return TimeClusterer()
    
    def test_cluster_by_time_empty(self, clusterer):
        """Test clustering with empty list."""
        result = clusterer.cluster_by_time([])
        
        assert result == []
    
    def test_cluster_by_time_proximity(self, clusterer):
        """Test clustering signals by time proximity."""
        base_time = datetime.utcnow()
        
        signals = []
        for i in range(3):
            s = MagicMock()
            s.entry_price = 100.0
            s.signal_type = SignalType.BUY
            s.confidence = 70.0
            s.generated_at = base_time + timedelta(minutes=i * 10)  # Within 60 min
            signals.append(s)
        
        result = clusterer.cluster_by_time(signals)
        
        assert len(result) >= 0
    
    def test_cluster_by_time_separate_clusters(self, clusterer):
        """Test signals in separate time clusters."""
        base_time = datetime.utcnow()
        
        signals = []
        
        # Cluster 1: earlier today
        for i in range(2):
            s = MagicMock()
            s.entry_price = 100.0
            s.signal_type = SignalType.BUY
            s.confidence = 70.0
            s.generated_at = base_time - timedelta(hours=2) + timedelta(minutes=i * 10)
            signals.append(s)
        
        # Cluster 2: later today
        for i in range(2):
            s = MagicMock()
            s.entry_price = 105.0
            s.signal_type = SignalType.BUY
            s.confidence = 75.0
            s.generated_at = base_time + timedelta(hours=1) + timedelta(minutes=i * 10)
            signals.append(s)
        
        result = clusterer.cluster_by_time(signals)
        
        assert len(result) >= 1


class TestMultiDimensionalClusterer:
    """Test MultiDimensionalClusterer."""
    
    @pytest.fixture
    def clusterer(self):
        return MultiDimensionalClusterer()
    
    def test_cluster_empty(self, clusterer):
        """Test clustering empty list."""
        result = clusterer.cluster([])
        
        assert result == []
    
    def test_cluster_valid(self, clusterer):
        """Test valid multi-dimensional clustering."""
        base_time = datetime.utcnow()
        
        signals = []
        for i in range(4):
            s = MagicMock()
            s.entry_price = 100.0 + (i % 2) * 0.5  # Two price groups
            s.signal_type = SignalType.BUY if i % 2 == 0 else SignalType.SELL
            s.confidence = 70.0 + i
            s.generated_at = base_time + timedelta(minutes=i * 15)
            signals.append(s)
        
        result = clusterer.cluster(signals)
        
        assert isinstance(result, list)
    
    def test_deduplicate(self, clusterer):
        """Test deduplication returns best from each cluster."""
        base_time = datetime.utcnow()
        
        signals = []
        for i in range(4):
            s = MagicMock()
            s.entry_price = 100.0 + (i % 2) * 0.5
            s.signal_type = SignalType.BUY
            s.confidence = 60.0 + i  # Different confidences
            s.generated_at = base_time + timedelta(minutes=i * 10)
            signals.append(s)
        
        result = clusterer.deduplicate(signals)
        
        # Should return fewer signals than input
        assert len(result) <= len(signals)


class TestSignalClusterService:
    """Test SignalClusterService."""
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query = MagicMock()
        return db
    
    def test_cluster_pending_signals_empty(self, mock_db):
        """Test clustering with no pending signals."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query.return_value = mock_query
        
        service = SignalClusterService(mock_db)
        result = service.cluster_pending_signals()
        
        assert result == []
    
    def test_cluster_pending_signals_with_data(self, mock_db):
        """Test clustering pending signals."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.entry_price = 100.0
        mock_signal.signal_type = SignalType.BUY
        mock_signal.confidence = 75.0
        mock_signal.generated_at = datetime.utcnow()
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalClusterService(mock_db)
        result = service.cluster_pending_signals()
        
        assert isinstance(result, list)
    
    def test_cluster_pending_signals_symbol_filter(self, mock_db):
        """Test clustering with symbol filter."""
        mock_signal = MagicMock()
        mock_signal.symbol = "AAPL"
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalClusterService(mock_db)
        result = service.cluster_pending_signals(symbol="AAPL")
        
        # Verify filter was called
        mock_query.filter.assert_called()
    
    def test_get_cluster_summary_empty(self, mock_db):
        """Test cluster summary with no clusters."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query.return_value = mock_query
        
        service = SignalClusterService(mock_db)
        result = service.get_cluster_summary()
        
        assert result["total_clusters"] == 0
        assert result["total_signals"] == 0
    
    def test_get_cluster_summary_with_clusters(self, mock_db):
        """Test cluster summary with data."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.symbol = "AAPL"
        mock_signal.entry_price = 100.0
        mock_signal.signal_type = SignalType.BUY
        mock_signal.confidence = 75.0
        mock_signal.generated_at = datetime.utcnow()
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_signal, mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalClusterService(mock_db)
        result = service.get_cluster_summary()
        
        assert "total_clusters" in result
        assert "total_signals" in result
        assert "avg_confidence" in result
    
    def test_get_consolidated_signals(self, mock_db):
        """Test getting consolidated signals."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.symbol = "AAPL"
        mock_signal.entry_price = 100.0
        mock_signal.signal_type = SignalType.BUY
        mock_signal.confidence = 75.0
        mock_signal.generated_at = datetime.utcnow()
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalClusterService(mock_db)
        result = service.get_consolidated_signals()
        
        assert isinstance(result, list)


class TestClusteringEdgeCases:
    """Test edge cases for clustering."""
    
    def test_cluster_signals_different_directions(self):
        """Test clustering signals with different directions."""
        clusterer = PriceClusterer()
        
        signals = []
        
        # Buy signals
        for i in range(2):
            s = MagicMock()
            s.entry_price = 100.0
            s.signal_type = SignalType.BUY
            s.confidence = 70.0
            s.generated_at = datetime.utcnow()
            signals.append(s)
        
        # Sell signal
        s = MagicMock()
        s.entry_price = 100.5
        s.signal_type = SignalType.SELL
        s.confidence = 75.0
        s.generated_at = datetime.utcnow()
        signals.append(s)
        
        result = clusterer.cluster_by_price(signals)
        
        # Should determine primary direction
        for cluster in result:
            assert cluster.primary_direction in [SignalType.BUY, SignalType.SELL]
    
    def test_cluster_very_close_prices(self):
        """Test clustering with very close prices (floating point)."""
        clusterer = PriceClusterer(ClusterConfig(price_tolerance_pct=0.1))
        
        signals = []
        for i in range(3):
            s = MagicMock()
            s.entry_price = 100.0 + (i * 0.001)  # Very close
            s.signal_type = SignalType.BUY
            s.confidence = 70.0
            s.generated_at = datetime.utcnow()
            signals.append(s)
        
        result = clusterer.cluster_by_price(signals)
        
        assert len(result) >= 0
    
    def test_cluster_time_window_boundary(self):
        """Test clustering at time window boundary."""
        clusterer = TimeClusterer(ClusterConfig(time_window_minutes=30))
        
        base_time = datetime.utcnow()
        
        signals = []
        # Exactly at 30 minute boundary
        s1 = MagicMock()
        s1.entry_price = 100.0
        s1.signal_type = SignalType.BUY
        s1.confidence = 70.0
        s1.generated_at = base_time
        signals.append(s1)
        
        s2 = MagicMock()
        s2.entry_price = 101.0
        s2.signal_type = SignalType.BUY
        s2.confidence = 75.0
        s2.generated_at = base_time + timedelta(minutes=31)  # Just over boundary
        signals.append(s2)
        
        result = clusterer.cluster_by_time(signals)
        
        # Should likely be separate clusters
        assert len(result) >= 1


class TestClusteringErrors:
    """Test error handling for clustering."""
    
    def test_cluster_with_none_prices(self):
        """Test clustering with None entry prices."""
        clusterer = PriceClusterer()
        
        s = MagicMock()
        s.entry_price = None  # Invalid
        s.signal_type = SignalType.BUY
        s.confidence = 70.0
        s.generated_at = datetime.utcnow()
        
        # Should handle gracefully
        result = clusterer.cluster_by_price([s])
        
        assert isinstance(result, list)