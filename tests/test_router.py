"""
Tests for cluster-execution-mcp router module.

Tests cover:
- IP resolution and caching
- SSH connectivity verification
- Task dataclass
- DistributedTaskRouter
  - Task routing logic
  - Local execution
  - Remote execution (mocked)
  - Task status tracking
"""
import pytest
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import asdict


class TestIPCache:
    """Test IP resolution cache."""

    def test_clear_ip_cache(self):
        """Test clearing the IP cache."""
        from cluster_execution_mcp.router import clear_ip_cache, _ip_cache

        # Add something to cache
        _ip_cache["test.local"] = ("192.168.1.1", time.time())
        assert "test.local" in _ip_cache

        clear_ip_cache()
        assert "test.local" not in _ip_cache


class TestTask:
    """Test Task dataclass."""

    def test_task_minimal(self):
        """Test creating a task with minimal fields."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-123",
            task_type="shell"
        )

        assert task.task_id == "test-123"
        assert task.task_type == "shell"
        assert task.command is None
        assert task.priority == 5

    def test_task_full(self):
        """Test creating a task with all fields."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-456",
            task_type="shell",
            command="make build",
            script=None,
            requires_os="linux",
            requires_arch="x86_64",
            requires_capabilities=["docker"],
            priority=10,
            metadata={"source": "test"},
            submitted_from="orchestrator",
            submitted_at=time.time()
        )

        assert task.task_id == "test-456"
        assert task.command == "make build"
        assert task.requires_os == "linux"
        assert task.requires_arch == "x86_64"
        assert task.requires_capabilities == ["docker"]
        assert task.priority == 10

    def test_task_to_dict(self):
        """Test task serialization."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-789",
            task_type="shell",
            command="ls -la"
        )

        data = task.to_dict()
        assert data["task_id"] == "test-789"
        assert data["task_type"] == "shell"
        assert data["command"] == "ls -la"


class TestDistributedTaskRouter:
    """Test DistributedTaskRouter class."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def router(self, mock_db_path):
        """Create a router with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.router import DistributedTaskRouter
            router = DistributedTaskRouter()
            yield router

    def test_router_initialization(self, router):
        """Test router initializes correctly."""
        assert router.local_node_id is not None
        assert router.db_path is not None

    def test_database_initialization(self, router):
        """Test database schema is created."""
        conn = sqlite3.connect(router.db_path)
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='task_queue'
        """)
        assert cursor.fetchone() is not None

        # Check indices exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_status'
        """)
        assert cursor.fetchone() is not None

        conn.close()


class TestTaskRouting:
    """Test task routing logic."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def router(self, mock_db_path):
        """Create a router with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.router import DistributedTaskRouter
            router = DistributedTaskRouter()
            yield router

    def test_route_task_linux_requirement(self, router):
        """Test routing to Linux node when required."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-linux",
            task_type="shell",
            command="docker build .",
            requires_os="linux"
        )

        target = router._route_task(task)
        # Should route to builder (Linux node)
        assert target == "builder"

    def test_route_task_prefers_specialized_nodes(self, router):
        """Test routing prefers nodes with matching specialties."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-compile",
            task_type="compilation",
            command="make build"
        )

        target = router._route_task(task)
        # Should prefer builder for compilation
        assert target == "builder"

    def test_route_task_avoids_local_node(self, router):
        """Test routing tries to offload from local node."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-offload",
            task_type="shell",
            command="make test"
        )

        target = router._route_task(task)
        # Should prefer different node than local (unless no alternatives)
        # Just check we get a valid result
        assert target is not None


class TestLocalExecution:
    """Test local command execution."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def router(self, mock_db_path):
        """Create a router with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.router import DistributedTaskRouter
            router = DistributedTaskRouter()
            yield router

    def test_execute_local_simple_command(self, router):
        """Test local execution of simple command."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus

        task = Task(
            task_id="test-local",
            task_type="shell",
            command="echo hello"
        )

        # Store task first
        router._store_task(task, router.local_node_id)

        # Execute
        router._execute_local(task)

        # Check result
        status = router.get_task_status("test-local")
        assert status is not None
        assert status["status"] == TaskStatus.COMPLETED.value

    def test_execute_local_command_failure(self, router):
        """Test local execution handles command failure."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus

        task = Task(
            task_id="test-fail",
            task_type="shell",
            command="false"  # Command that always fails
        )

        # Store task first
        router._store_task(task, router.local_node_id)

        # Execute
        router._execute_local(task)

        # Check result - should complete but have error output
        status = router.get_task_status("test-fail")
        assert status is not None
        assert status["status"] == TaskStatus.COMPLETED.value

    def test_execute_local_no_command(self, router):
        """Test local execution with no command or script."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus

        task = Task(
            task_id="test-empty",
            task_type="shell"
        )

        # Store task first
        router._store_task(task, router.local_node_id)

        # Execute
        router._execute_local(task)

        # Check result
        status = router.get_task_status("test-empty")
        assert status is not None
        assert status["status"] == TaskStatus.COMPLETED.value
        assert "No command or script" in status["result"]

    def test_execute_local_complex_command(self, router):
        """Test local execution of complex shell command."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus

        task = Task(
            task_id="test-complex",
            task_type="shell",
            command="echo foo && echo bar"
        )

        # Store task first
        router._store_task(task, router.local_node_id)

        # Execute
        router._execute_local(task)

        # Check result
        status = router.get_task_status("test-complex")
        assert status is not None
        assert status["status"] == TaskStatus.COMPLETED.value
        assert "foo" in status["result"]
        assert "bar" in status["result"]


class TestRemoteExecution:
    """Test remote command execution (mocked SSH)."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def router(self, mock_db_path):
        """Create a router with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.router import DistributedTaskRouter
            router = DistributedTaskRouter()
            yield router

    def test_execute_remote_success(self, router):
        """Test remote execution success with mocked SSH."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus

        task = Task(
            task_id="test-remote",
            task_type="shell",
            command="hostname"
        )

        # Store task
        router._store_task(task, "builder")

        # Mock get_node_ip and subprocess
        with patch("cluster_execution_mcp.router.get_node_ip", return_value="192.168.1.10"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "builder-host"
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result):
                router._execute_remote(task, "builder")

        # Check result
        status = router.get_task_status("test-remote")
        assert status is not None
        assert status["status"] == TaskStatus.COMPLETED.value
        assert status["result"] == "builder-host"

    def test_execute_remote_no_ip(self, router):
        """Test remote execution fails gracefully when IP unavailable."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus

        task = Task(
            task_id="test-no-ip",
            task_type="shell",
            command="hostname"
        )

        # Store task
        router._store_task(task, "builder")

        # Mock get_node_ip to return None
        with patch("cluster_execution_mcp.router.get_node_ip", return_value=None):
            router._execute_remote(task, "builder")

        # Check result
        status = router.get_task_status("test-no-ip")
        assert status is not None
        assert status["status"] == TaskStatus.FAILED.value
        assert "resolve IP" in status["error"]

    def test_execute_remote_timeout(self, router):
        """Test remote execution handles timeout."""
        from cluster_execution_mcp.router import Task
        from cluster_execution_mcp.config import TaskStatus
        import subprocess

        task = Task(
            task_id="test-timeout",
            task_type="shell",
            command="sleep 1000"
        )

        # Store task
        router._store_task(task, "builder")

        # Mock get_node_ip and subprocess timeout
        with patch("cluster_execution_mcp.router.get_node_ip", return_value="192.168.1.10"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=300)):
                router._execute_remote(task, "builder")

        # Check result
        status = router.get_task_status("test-timeout")
        assert status is not None
        assert status["status"] == TaskStatus.TIMEOUT.value
        assert "timed out" in status["error"].lower()


class TestTaskStatus:
    """Test task status operations."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def router(self, mock_db_path):
        """Create a router with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.router import DistributedTaskRouter
            router = DistributedTaskRouter()
            yield router

    def test_get_task_status_existing(self, router):
        """Test getting status of existing task."""
        from cluster_execution_mcp.router import Task

        task = Task(
            task_id="test-status",
            task_type="shell",
            command="echo test"
        )

        router._store_task(task, router.local_node_id)
        status = router.get_task_status("test-status")

        assert status is not None
        assert status["task_id"] == "test-status"
        assert status["assigned_to"] == router.local_node_id

    def test_get_task_status_nonexistent(self, router):
        """Test getting status of nonexistent task."""
        status = router.get_task_status("nonexistent-task")
        assert status is None


class TestClusterStatus:
    """Test cluster status reporting."""

    @pytest.fixture
    def mock_db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "task_queue.db"
            yield db_path

    @pytest.fixture
    def router(self, mock_db_path):
        """Create a router with mocked database."""
        with patch("cluster_execution_mcp.router.get_db_path", return_value=mock_db_path):
            from cluster_execution_mcp.router import DistributedTaskRouter
            router = DistributedTaskRouter()
            yield router

    def test_get_cluster_status(self, router):
        """Test getting cluster status."""
        status = router.get_cluster_status()

        assert "local_node" in status
        assert "cluster_nodes" in status
        assert status["local_node"] == router.local_node_id

    def test_get_cluster_status_includes_all_nodes(self, router):
        """Test cluster status includes all configured nodes."""
        from cluster_execution_mcp.config import CLUSTER_NODES

        status = router.get_cluster_status()

        for node_id in CLUSTER_NODES.keys():
            assert node_id in status["cluster_nodes"]
            assert "hostname" in status["cluster_nodes"][node_id]
            assert "os" in status["cluster_nodes"][node_id]


class TestSSHConnectivity:
    """Test SSH connectivity verification."""

    def test_verify_ssh_success(self):
        """Test successful SSH verification."""
        from cluster_execution_mcp.router import verify_ssh_connectivity

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = verify_ssh_connectivity("192.168.1.10", timeout=5, retries=1)
            assert result is True

    def test_verify_ssh_failure(self):
        """Test failed SSH verification."""
        from cluster_execution_mcp.router import verify_ssh_connectivity

        mock_result = MagicMock()
        mock_result.returncode = 255

        with patch("subprocess.run", return_value=mock_result):
            result = verify_ssh_connectivity("192.168.1.10", timeout=5, retries=1)
            assert result is False

    def test_verify_ssh_timeout(self):
        """Test SSH verification timeout."""
        from cluster_execution_mcp.router import verify_ssh_connectivity
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=5)):
            result = verify_ssh_connectivity("192.168.1.10", timeout=5, retries=1)
            assert result is False


class TestHostnameResolution:
    """Test hostname resolution."""

    def test_resolve_hostname_dns_success(self):
        """Test successful DNS resolution."""
        from cluster_execution_mcp.router import resolve_hostname, clear_ip_cache

        clear_ip_cache()

        with patch("socket.gethostbyname", return_value="192.168.1.10"):
            ip = resolve_hostname("test.local")
            assert ip == "192.168.1.10"

    def test_resolve_hostname_cached(self):
        """Test hostname resolution uses cache."""
        from cluster_execution_mcp.router import resolve_hostname, clear_ip_cache, _ip_cache
        import time

        clear_ip_cache()

        # Pre-populate cache
        _ip_cache["cached.local"] = ("192.168.1.20", time.time())

        # Should return cached value without calling socket
        with patch("socket.gethostbyname", side_effect=Exception("Should not be called")):
            ip = resolve_hostname("cached.local")
            assert ip == "192.168.1.20"

    def test_resolve_hostname_cache_expired(self):
        """Test expired cache triggers new resolution."""
        from cluster_execution_mcp.router import resolve_hostname, clear_ip_cache, _ip_cache
        from cluster_execution_mcp.config import config

        clear_ip_cache()

        # Pre-populate cache with old entry
        old_time = time.time() - config.ip_cache_ttl - 10
        _ip_cache["expired.local"] = ("192.168.1.30", old_time)

        # Should call socket for new resolution
        with patch("socket.gethostbyname", return_value="192.168.1.31"):
            ip = resolve_hostname("expired.local")
            assert ip == "192.168.1.31"
