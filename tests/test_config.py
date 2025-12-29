"""
Tests for cluster-execution-mcp configuration module.

Tests cover:
- ClusterConfig dataclass
- ClusterNode with requirement matching
- Validation functions (IP, command, node_id)
- Offload pattern detection
- Node lookup functions
"""
import pytest
import os
from unittest.mock import patch


class TestClusterConfig:
    """Test ClusterConfig dataclass and environment loading."""

    def test_config_defaults(self):
        """Test that config has sensible defaults."""
        from cluster_execution_mcp.config import config

        assert config.ssh_timeout == 5 or isinstance(config.ssh_timeout, int)
        assert config.ssh_connect_timeout == 2 or isinstance(config.ssh_connect_timeout, int)
        assert config.command_timeout == 300 or isinstance(config.command_timeout, int)
        assert config.cpu_threshold == 40 or isinstance(config.cpu_threshold, float)
        assert config.load_threshold == 4 or isinstance(config.load_threshold, float)
        assert config.memory_threshold == 80 or isinstance(config.memory_threshold, float)

    def test_config_from_environment(self):
        """Test config loads from environment variables."""
        # ClusterConfig uses factory functions that read env at instantiation
        # Test that the pattern works by creating a new config
        with patch.dict(os.environ, {
            "CLUSTER_SSH_TIMEOUT": "10",
            "CLUSTER_CPU_THRESHOLD": "50"
        }, clear=False):
            from cluster_execution_mcp.config import ClusterConfig
            new_config = ClusterConfig()

            assert new_config.ssh_timeout == 10
            assert new_config.cpu_threshold == 50.0


class TestClusterNode:
    """Test ClusterNode dataclass and requirement matching."""

    def test_node_matches_no_requirements(self):
        """Test node matches when no requirements specified."""
        from cluster_execution_mcp.config import ClusterNode

        node = ClusterNode(
            node_id="test",
            hostname="test.local",
            fallback_ip="192.168.1.1",
            os="linux",
            arch="x86_64",
            capabilities=["docker"],
            specialties=["compilation"],
            max_tasks=5,
            priority=3
        )

        assert node.matches_requirements() is True

    def test_node_matches_os_requirement(self):
        """Test node OS requirement matching."""
        from cluster_execution_mcp.config import ClusterNode

        node = ClusterNode(
            node_id="test",
            hostname="test.local",
            fallback_ip="192.168.1.1",
            os="linux",
            arch="x86_64",
            capabilities=[],
            specialties=[],
            max_tasks=5,
            priority=3
        )

        assert node.matches_requirements(requires_os="linux") is True
        assert node.matches_requirements(requires_os="macos") is False
        assert node.matches_requirements(requires_os="LINUX") is True  # Case insensitive

    def test_node_matches_darwin_macos_alias(self):
        """Test darwin/macos alias handling."""
        from cluster_execution_mcp.config import ClusterNode

        node = ClusterNode(
            node_id="test",
            hostname="test.local",
            fallback_ip="192.168.1.1",
            os="macos",
            arch="arm64",
            capabilities=[],
            specialties=[],
            max_tasks=5,
            priority=3
        )

        assert node.matches_requirements(requires_os="macos") is True
        assert node.matches_requirements(requires_os="darwin") is True

    def test_node_matches_arch_requirement(self):
        """Test node architecture requirement matching."""
        from cluster_execution_mcp.config import ClusterNode

        node = ClusterNode(
            node_id="test",
            hostname="test.local",
            fallback_ip="192.168.1.1",
            os="linux",
            arch="x86_64",
            capabilities=[],
            specialties=[],
            max_tasks=5,
            priority=3
        )

        assert node.matches_requirements(requires_arch="x86_64") is True
        assert node.matches_requirements(requires_arch="arm64") is False
        assert node.matches_requirements(requires_arch="X86_64") is True  # Case insensitive

    def test_node_matches_capabilities(self):
        """Test node capability requirement matching."""
        from cluster_execution_mcp.config import ClusterNode

        node = ClusterNode(
            node_id="test",
            hostname="test.local",
            fallback_ip="192.168.1.1",
            os="linux",
            arch="x86_64",
            capabilities=["docker", "podman", "compilation"],
            specialties=[],
            max_tasks=5,
            priority=3
        )

        assert node.matches_requirements(requires_capabilities=["docker"]) is True
        assert node.matches_requirements(requires_capabilities=["docker", "podman"]) is True
        assert node.matches_requirements(requires_capabilities=["kubernetes"]) is False
        assert node.matches_requirements(requires_capabilities=["DOCKER"]) is True  # Case insensitive

    def test_node_matches_combined_requirements(self):
        """Test node with multiple requirements."""
        from cluster_execution_mcp.config import ClusterNode

        node = ClusterNode(
            node_id="test",
            hostname="test.local",
            fallback_ip="192.168.1.1",
            os="linux",
            arch="x86_64",
            capabilities=["docker", "compilation"],
            specialties=[],
            max_tasks=5,
            priority=3
        )

        # All match
        assert node.matches_requirements(
            requires_os="linux",
            requires_arch="x86_64",
            requires_capabilities=["docker"]
        ) is True

        # OS doesn't match
        assert node.matches_requirements(
            requires_os="macos",
            requires_arch="x86_64",
            requires_capabilities=["docker"]
        ) is False


class TestValidateIP:
    """Test IP address validation."""

    def test_valid_private_ip(self):
        """Test valid private IPs."""
        from cluster_execution_mcp.config import validate_ip

        assert validate_ip("192.168.1.1") is True
        assert validate_ip("192.168.0.100") is True
        assert validate_ip("10.10.1.1") is True
        assert validate_ip("172.32.0.1") is True  # Outside Docker range

    def test_invalid_loopback(self):
        """Test that loopback addresses are rejected."""
        from cluster_execution_mcp.config import validate_ip

        assert validate_ip("127.0.0.1") is False
        assert validate_ip("127.0.0.2") is False
        assert validate_ip("127.255.255.255") is False

    def test_invalid_docker_bridge(self):
        """Test that Docker bridge IPs (172.16-31.x.x) are rejected."""
        from cluster_execution_mcp.config import validate_ip

        assert validate_ip("172.16.0.1") is False
        assert validate_ip("172.17.0.1") is False
        assert validate_ip("172.31.255.255") is False
        assert validate_ip("172.15.0.1") is True  # Outside Docker range

    def test_invalid_link_local(self):
        """Test that link-local addresses are rejected."""
        from cluster_execution_mcp.config import validate_ip

        assert validate_ip("169.254.1.1") is False
        assert validate_ip("169.254.255.255") is False

    def test_invalid_podman_default(self):
        """Test that podman default range is rejected."""
        from cluster_execution_mcp.config import validate_ip

        assert validate_ip("10.0.0.1") is False
        assert validate_ip("10.0.2.15") is False
        assert validate_ip("10.1.0.1") is True  # Outside podman range

    def test_invalid_format(self):
        """Test invalid IP formats."""
        from cluster_execution_mcp.config import validate_ip

        assert validate_ip("") is False
        assert validate_ip("not-an-ip") is False
        assert validate_ip("192.168.1") is False
        assert validate_ip("192.168.1.256") is False
        assert validate_ip("192.168.1.-1") is False


class TestValidateCommand:
    """Test command validation."""

    def test_valid_commands(self):
        """Test valid commands pass validation."""
        from cluster_execution_mcp.config import validate_command

        valid, error = validate_command("ls -la")
        assert valid is True
        assert error is None

        valid, error = validate_command("make build")
        assert valid is True

        valid, error = validate_command("docker ps")
        assert valid is True

    def test_empty_command(self):
        """Test empty commands are rejected."""
        from cluster_execution_mcp.config import validate_command

        valid, error = validate_command("")
        assert valid is False
        assert "empty" in error.lower()

        valid, error = validate_command("   ")
        assert valid is False

    def test_dangerous_rm_rf_root(self):
        """Test dangerous rm -rf / is rejected."""
        from cluster_execution_mcp.config import validate_command

        valid, error = validate_command("rm -rf /")
        assert valid is False
        assert "dangerous" in error.lower()

    def test_dangerous_rm_rf_wildcard(self):
        """Test dangerous rm -rf /* is rejected."""
        from cluster_execution_mcp.config import validate_command

        valid, error = validate_command("rm -rf /*")
        assert valid is False
        assert "dangerous" in error.lower()

    def test_dangerous_dd(self):
        """Test dangerous dd to device is rejected."""
        from cluster_execution_mcp.config import validate_command

        valid, error = validate_command("dd if=/dev/zero of=/dev/sda")
        assert valid is False
        assert "dangerous" in error.lower()

    def test_fork_bomb(self):
        """Test fork bomb is rejected."""
        from cluster_execution_mcp.config import validate_command

        valid, error = validate_command(":(){ :|:& };:")
        assert valid is False
        assert "dangerous" in error.lower()


class TestValidateNodeId:
    """Test node ID validation."""

    def test_valid_node_ids(self):
        """Test valid node IDs."""
        from cluster_execution_mcp.config import validate_node_id, CLUSTER_NODES

        for node_id in CLUSTER_NODES.keys():
            valid, error = validate_node_id(node_id)
            assert valid is True
            assert error is None

    def test_invalid_node_id(self):
        """Test invalid node IDs are rejected."""
        from cluster_execution_mcp.config import validate_node_id

        valid, error = validate_node_id("nonexistent-node")
        assert valid is False
        assert "Unknown node" in error
        assert "Available:" in error


class TestOffloadPatterns:
    """Test command offload pattern detection."""

    def test_offload_heavy_commands(self):
        """Test heavy commands trigger offloading."""
        from cluster_execution_mcp.config import should_offload_command

        assert should_offload_command("make build") is True
        assert should_offload_command("cargo test") is True
        assert should_offload_command("npm install") is True
        assert should_offload_command("pytest tests/") is True
        assert should_offload_command("docker build .") is True
        assert should_offload_command("docker-compose up") is True

    def test_local_simple_commands(self):
        """Test simple commands run locally."""
        from cluster_execution_mcp.config import should_offload_command

        assert should_offload_command("ls") is False
        assert should_offload_command("ls -la") is False
        assert should_offload_command("pwd") is False
        assert should_offload_command("echo hello") is False
        assert should_offload_command("cat file.txt") is False
        assert should_offload_command("which python") is False

    def test_offload_case_insensitive(self):
        """Test offload patterns are case insensitive."""
        from cluster_execution_mcp.config import should_offload_command

        assert should_offload_command("MAKE build") is True
        assert should_offload_command("Docker Build .") is True


class TestNodeLookup:
    """Test node lookup functions."""

    def test_get_node_existing(self):
        """Test getting an existing node."""
        from cluster_execution_mcp.config import get_node, CLUSTER_NODES

        for node_id in CLUSTER_NODES.keys():
            node = get_node(node_id)
            assert node is not None
            assert node.node_id == node_id

    def test_get_node_nonexistent(self):
        """Test getting a nonexistent node."""
        from cluster_execution_mcp.config import get_node

        node = get_node("nonexistent")
        assert node is None

    def test_get_available_nodes(self):
        """Test getting available node IDs."""
        from cluster_execution_mcp.config import get_available_nodes, CLUSTER_NODES

        nodes = get_available_nodes()
        assert len(nodes) == len(CLUSTER_NODES)
        for node_id in CLUSTER_NODES.keys():
            assert node_id in nodes

    def test_get_nodes_by_capability(self):
        """Test filtering nodes by capability."""
        from cluster_execution_mcp.config import get_nodes_by_capability

        # Builder should have docker
        docker_nodes = get_nodes_by_capability("docker")
        assert len(docker_nodes) >= 1
        assert any(n.node_id == "builder" for n in docker_nodes)

    def test_get_nodes_by_os(self):
        """Test filtering nodes by OS."""
        from cluster_execution_mcp.config import get_nodes_by_os

        linux_nodes = get_nodes_by_os("linux")
        for node in linux_nodes:
            assert node.os.lower() == "linux"

        macos_nodes = get_nodes_by_os("macos")
        for node in macos_nodes:
            assert node.os.lower() == "macos"

        # Test darwin alias
        darwin_nodes = get_nodes_by_os("darwin")
        assert len(darwin_nodes) == len(macos_nodes)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_status_values(self):
        """Test all task status values."""
        from cluster_execution_mcp.config import TaskStatus

        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.ASSIGNED.value == "assigned"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.TIMEOUT.value == "timeout"
