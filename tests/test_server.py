"""
Tests for cluster-execution-mcp server module.

Tests cover:
- ClusterExecutionServer class
  - Load detection (is_overloaded)
  - Offload decision logic
  - Local execution
  - Cluster bash execution
  - Offload to specific node
  - Parallel execution
- MCP tool functions
"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


class TestClusterExecutionServer:
    """Test ClusterExecutionServer class."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def server(self, mock_db_path):
        """Create a server with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer
            server = ClusterExecutionServer()
            yield server


class TestLoadDetection:
    """Test load detection logic."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_is_overloaded_low_load(self, mock_db_path):
        """Test not overloaded when metrics are low."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=20.0), \
                 patch("psutil.getloadavg", return_value=(1.0, 1.0, 1.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=50.0)
                assert server.is_overloaded() is False

    def test_is_overloaded_high_cpu(self, mock_db_path):
        """Test overloaded when CPU is high."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=95.0), \
                 patch("psutil.getloadavg", return_value=(1.0, 1.0, 1.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=50.0)
                assert server.is_overloaded() is True

    def test_is_overloaded_high_memory(self, mock_db_path):
        """Test overloaded when memory is high."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=20.0), \
                 patch("psutil.getloadavg", return_value=(1.0, 1.0, 1.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=95.0)
                assert server.is_overloaded() is True

    def test_is_overloaded_high_load(self, mock_db_path):
        """Test overloaded when load average is high."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=20.0), \
                 patch("psutil.getloadavg", return_value=(10.0, 8.0, 6.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=50.0)
                assert server.is_overloaded() is True


class TestOffloadDecision:
    """Test offload decision logic."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_should_offload_heavy_command(self, mock_db_path):
        """Test heavy commands trigger offloading."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            # Heavy commands should offload regardless of load
            with patch("psutil.cpu_percent", return_value=10.0), \
                 patch("psutil.getloadavg", return_value=(0.5, 0.5, 0.5)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=30.0)
                assert server.should_offload("make build") is True
                assert server.should_offload("cargo test") is True
                assert server.should_offload("docker build .") is True

    def test_should_offload_simple_command(self, mock_db_path):
        """Test simple commands run locally when not overloaded."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=10.0), \
                 patch("psutil.getloadavg", return_value=(0.5, 0.5, 0.5)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=30.0)
                assert server.should_offload("ls -la") is False
                assert server.should_offload("pwd") is False
                assert server.should_offload("echo hello") is False

    def test_should_offload_when_overloaded(self, mock_db_path):
        """Test any command offloads when overloaded."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=95.0), \
                 patch("psutil.getloadavg", return_value=(10.0, 8.0, 6.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=90.0)
                # Even simple commands should offload when overloaded
                assert server.should_offload("unknown_command") is True


class TestLocalExecution:
    """Test local command execution."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_execute_local_success(self, mock_db_path):
        """Test successful local execution."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.execute_local("echo hello")

            assert result["success"] is True
            assert "hello" in result["stdout"]
            assert result["return_code"] == 0
            assert result["auto_routed"] is False

    def test_execute_local_failure(self, mock_db_path):
        """Test failed local execution."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.execute_local("false")

            assert result["success"] is False
            assert result["return_code"] != 0

    def test_execute_local_invalid_command(self, mock_db_path):
        """Test local execution rejects invalid commands."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.execute_local("rm -rf /")

            assert result["success"] is False
            assert "error" in result

    def test_execute_local_complex_command(self, mock_db_path):
        """Test local execution of complex shell command."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.execute_local("echo foo && echo bar")

            assert result["success"] is True
            assert "foo" in result["stdout"]
            assert "bar" in result["stdout"]


class TestClusterBashExecution:
    """Test cluster bash command execution."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_cluster_bash_local_simple(self, mock_db_path):
        """Test cluster bash runs simple commands locally."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=10.0), \
                 patch("psutil.getloadavg", return_value=(0.5, 0.5, 0.5)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=30.0)
                result = server.execute_cluster_bash("echo test")

                assert result["success"] is True
                assert "test" in result["stdout"]
                assert result["auto_routed"] is False

    def test_cluster_bash_auto_route_disabled(self, mock_db_path):
        """Test cluster bash respects auto_route=False."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            # Even heavy command should run locally when auto_route=False
            result = server.execute_cluster_bash(
                "echo make build",  # "make" is in command but just echoing
                auto_route=False
            )

            assert result["success"] is True
            assert result["auto_routed"] is False

    def test_cluster_bash_invalid_command(self, mock_db_path):
        """Test cluster bash rejects invalid commands."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.execute_cluster_bash("")

            assert result["success"] is False
            assert "error" in result


class TestOffloadToNode:
    """Test explicit node offloading."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_offload_to_invalid_node(self, mock_db_path):
        """Test offload to invalid node fails."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.offload_to_node("echo test", "nonexistent-node")

            assert result["success"] is False
            assert "Unknown node" in result["error"]

    def test_offload_to_invalid_command(self, mock_db_path):
        """Test offload with invalid command fails."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            result = server.offload_to_node("rm -rf /", "builder")

            assert result["success"] is False
            assert "dangerous" in result["error"].lower()

    def test_offload_to_no_ip(self, mock_db_path):
        """Test offload fails when IP unavailable."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("cluster_execution_mcp.server.get_node_ip", return_value=None):
                result = server.offload_to_node("echo test", "builder")

                assert result["success"] is False
                assert "resolve IP" in result["error"]

    def test_offload_to_success(self, mock_db_path):
        """Test successful offload with mocked SSH."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "remote-output"
            mock_result.stderr = ""

            with patch("cluster_execution_mcp.server.get_node_ip", return_value="192.168.1.10"), \
                 patch("subprocess.run", return_value=mock_result):
                result = server.offload_to_node("echo test", "builder")

                assert result["success"] is True
                assert result["executed_on"] == "builder"
                assert result["stdout"] == "remote-output"


class TestParallelExecution:
    """Test parallel command execution."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_parallel_execute_invalid_command(self, mock_db_path):
        """Test parallel execution rejects invalid commands."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()
            results = asyncio.run(server.parallel_execute(["rm -rf /"]))

            assert len(results) == 1
            assert results[0]["success"] is False
            assert "Invalid command" in results[0]["error"]


class TestGetClusterStatus:
    """Test cluster status retrieval."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    def test_get_cluster_status_local(self, mock_db_path):
        """Test getting cluster status includes local node."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import ClusterExecutionServer

            server = ClusterExecutionServer()

            with patch("psutil.cpu_percent", return_value=25.0), \
                 patch("psutil.getloadavg", return_value=(1.0, 1.0, 1.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=50.0)

                status = server.get_cluster_status()

                assert "local_node" in status
                assert "nodes" in status
                assert server.local_node_id in status["nodes"]
                assert status["nodes"][server.local_node_id]["reachable"] is True


class TestMCPTools:
    """Test MCP tool functions."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.mark.asyncio
    async def test_cluster_bash_tool(self, mock_db_path):
        """Test cluster_bash MCP tool."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import cluster_bash

            with patch("psutil.cpu_percent", return_value=10.0), \
                 patch("psutil.getloadavg", return_value=(0.5, 0.5, 0.5)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=30.0)

                result = await cluster_bash("echo test")
                assert "success" in result
                assert "true" in result.lower()

    @pytest.mark.asyncio
    async def test_cluster_status_tool(self, mock_db_path):
        """Test cluster_status MCP tool."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import cluster_status

            with patch("psutil.cpu_percent", return_value=25.0), \
                 patch("psutil.getloadavg", return_value=(1.0, 1.0, 1.0)), \
                 patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=50.0)

                result = await cluster_status()
                assert "local_node" in result
                assert "nodes" in result

    @pytest.mark.asyncio
    async def test_offload_to_tool(self, mock_db_path):
        """Test offload_to MCP tool."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import offload_to

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "output"
            mock_result.stderr = ""

            with patch("cluster_execution_mcp.server.get_node_ip", return_value="192.168.1.10"), \
                 patch("subprocess.run", return_value=mock_result):
                result = await offload_to("echo test", "builder")
                assert "success" in result

    @pytest.mark.asyncio
    async def test_parallel_execute_tool(self, mock_db_path):
        """Test parallel_execute MCP tool."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.server import parallel_execute

            # Test with invalid command to ensure it returns results
            result = await parallel_execute(["rm -rf /"])
            assert "Invalid command" in result
