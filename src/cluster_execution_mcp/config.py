#!/usr/bin/env python3
"""
Configuration module for Cluster Execution MCP Server.

Centralizes all configuration, environment variables, and cluster topology.
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

# =============================================================================
# Logging Setup
# =============================================================================

LOG_LEVEL = os.getenv("CLUSTER_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("cluster-execution-mcp")


# =============================================================================
# Environment Configuration
# =============================================================================

@dataclass(frozen=True)
class ClusterConfig:
    """Centralized cluster configuration from environment variables."""

    # SSH Configuration
    ssh_user: str = field(default_factory=lambda: os.getenv("CLUSTER_SSH_USER", "marc"))
    ssh_timeout: int = field(default_factory=lambda: int(os.getenv("CLUSTER_SSH_TIMEOUT", "5")))
    ssh_connect_timeout: int = field(default_factory=lambda: int(os.getenv("CLUSTER_SSH_CONNECT_TIMEOUT", "2")))
    ssh_retries: int = field(default_factory=lambda: int(os.getenv("CLUSTER_SSH_RETRIES", "2")))

    # Load Thresholds
    cpu_threshold: float = field(default_factory=lambda: float(os.getenv("CLUSTER_CPU_THRESHOLD", "40")))
    load_threshold: float = field(default_factory=lambda: float(os.getenv("CLUSTER_LOAD_THRESHOLD", "4")))
    memory_threshold: float = field(default_factory=lambda: float(os.getenv("CLUSTER_MEMORY_THRESHOLD", "80")))

    # Timeouts
    command_timeout: int = field(default_factory=lambda: int(os.getenv("CLUSTER_CMD_TIMEOUT", "300")))
    status_timeout: int = field(default_factory=lambda: int(os.getenv("CLUSTER_STATUS_TIMEOUT", "5")))

    # Cache Settings
    ip_cache_ttl: int = field(default_factory=lambda: int(os.getenv("CLUSTER_IP_CACHE_TTL", "300")))

    # Network
    gateway_ip: str = field(default_factory=lambda: os.getenv("CLUSTER_GATEWAY", "192.0.2.102"))
    dns_server: str = field(default_factory=lambda: os.getenv("CLUSTER_DNS", "8.8.8.8"))

    # Paths
    agentic_system_path: str = field(
        default_factory=lambda: os.getenv("AGENTIC_SYSTEM_PATH", "${AGENTIC_SYSTEM_PATH:-/opt/agentic}")
    )


# Global config instance
config = ClusterConfig()


# =============================================================================
# Path Configuration
# =============================================================================

def get_data_dir() -> Path:
    """Get data directory for cluster execution."""
    data_dir = Path(config.agentic_system_path) / "databases" / "cluster"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Get path to task queue database."""
    return get_data_dir() / "task_queue.db"


# =============================================================================
# Cluster Node Definitions
# =============================================================================

class NodeOS(Enum):
    """Operating system types."""
    LINUX = "linux"
    MACOS = "macos"
    DARWIN = "darwin"  # Alias for macos


class NodeArch(Enum):
    """Architecture types."""
    X86_64 = "x86_64"
    ARM64 = "arm64"


@dataclass
class ClusterNode:
    """Definition of a cluster node."""
    node_id: str
    hostname: str
    fallback_ip: str
    os: str
    arch: str
    capabilities: List[str]
    specialties: List[str]
    max_tasks: int
    priority: int  # Lower = higher priority for offloading

    def matches_requirements(
        self,
        requires_os: Optional[str] = None,
        requires_arch: Optional[str] = None,
        requires_capabilities: Optional[List[str]] = None
    ) -> bool:
        """Check if node matches task requirements."""
        # Check OS
        if requires_os:
            # Handle darwin/macos alias
            node_os = self.os.lower()
            required = requires_os.lower()
            if required == "darwin":
                required = "macos"
            if node_os != required:
                return False

        # Check architecture
        if requires_arch and self.arch.lower() != requires_arch.lower():
            return False

        # Check capabilities
        if requires_capabilities:
            node_caps = set(c.lower() for c in self.capabilities)
            required_caps = set(c.lower() for c in requires_capabilities)
            if not required_caps.issubset(node_caps):
                return False

        return True


# Cluster topology - loaded from environment or defaults
CLUSTER_NODES: Dict[str, ClusterNode] = {
    "builder": ClusterNode(
        node_id="builder",
        hostname=os.getenv("CLUSTER_MACPRO51_HOST", "builder.example.local"),
        fallback_ip=os.getenv("CLUSTER_MACPRO51_IP", "192.0.2.237"),
        os="linux",
        arch="x86_64",
        capabilities=["docker", "podman", "raid", "nvme", "compilation", "testing", "tpu"],
        specialties=["compilation", "testing", "containerization", "benchmarking"],
        max_tasks=10,
        priority=3
    ),
    "orchestrator": ClusterNode(
        node_id="orchestrator",
        hostname=os.getenv("CLUSTER_MACSTUDIO_HOST", "Marcs-orchestrator.example.local"),
        fallback_ip=os.getenv("CLUSTER_MACSTUDIO_IP", "192.0.2.5"),
        os="macos",
        arch="arm64",
        capabilities=["orchestration", "coordination", "temporal", "mlx-gpu", "arduino"],
        specialties=["orchestration", "coordination", "monitoring", "temporal-workflows"],
        max_tasks=5,
        priority=1  # Keep free - orchestrator
    ),
    "researcher": ClusterNode(
        node_id="researcher",
        hostname=os.getenv("CLUSTER_MACBOOKAIR_HOST", "Marcs-researcher.example.local"),
        fallback_ip=os.getenv("CLUSTER_MACBOOKAIR_IP", "192.0.2.65"),
        os="macos",
        arch="arm64",
        capabilities=["research", "documentation", "analysis"],
        specialties=["research", "documentation", "analysis", "mobile-operations"],
        max_tasks=3,
        priority=2
    ),
    "inference": ClusterNode(
        node_id="inference",
        hostname=os.getenv("CLUSTER_INFERENCE_HOST", "inference.example.local"),
        fallback_ip=os.getenv("CLUSTER_INFERENCE_IP", "192.0.2.130"),
        os="macos",
        arch="arm64",
        capabilities=["ollama", "inference", "model-serving", "llm-api"],
        specialties=["ollama-inference", "model-serving", "api-endpoints"],
        max_tasks=8,
        priority=2
    ),
}


def get_node(node_id: str) -> Optional[ClusterNode]:
    """Get node by ID."""
    return CLUSTER_NODES.get(node_id)


def get_available_nodes() -> List[str]:
    """Get list of available node IDs."""
    return list(CLUSTER_NODES.keys())


def get_nodes_by_capability(capability: str) -> List[ClusterNode]:
    """Get nodes that have a specific capability."""
    return [
        node for node in CLUSTER_NODES.values()
        if capability.lower() in [c.lower() for c in node.capabilities]
    ]


def get_nodes_by_os(os_type: str) -> List[ClusterNode]:
    """Get nodes running specific OS."""
    os_type = os_type.lower()
    if os_type == "darwin":
        os_type = "macos"
    return [node for node in CLUSTER_NODES.values() if node.os.lower() == os_type]


# =============================================================================
# Offload Patterns
# =============================================================================

# Commands that should be offloaded
OFFLOAD_PATTERNS = [
    "make", "cargo", "npm", "yarn", "pnpm",
    "pytest", "jest", "mocha", "test",
    "build", "compile", "gcc", "g++", "clang",
    "docker", "podman", "kubectl",
    "rsync", "scp", "tar", "zip", "unzip",
    "find", "grep -r", "rg"
]

# Commands that should run locally (simple/quick)
LOCAL_PATTERNS = ["ls", "pwd", "cd", "echo", "cat", "head", "tail", "which", "type"]


def should_offload_command(command: str) -> bool:
    """Determine if command should be offloaded to another node."""
    cmd_lower = command.lower()

    # Check simple patterns first
    for pattern in LOCAL_PATTERNS:
        if cmd_lower.startswith(pattern):
            return False

    # Check offload patterns
    for pattern in OFFLOAD_PATTERNS:
        if pattern in cmd_lower:
            return True

    return False


# =============================================================================
# Task Status Enum
# =============================================================================

class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# =============================================================================
# Validation Functions
# =============================================================================

def validate_node_id(node_id: str) -> tuple[bool, Optional[str]]:
    """Validate that node_id is known."""
    if node_id in CLUSTER_NODES:
        return True, None
    available = ", ".join(CLUSTER_NODES.keys())
    return False, f"Unknown node: {node_id}. Available: {available}"


def validate_command(command: str) -> tuple[bool, Optional[str]]:
    """Basic command validation."""
    if not command or not command.strip():
        return False, "Command cannot be empty"

    # Check for dangerous patterns (basic protection)
    dangerous_patterns = [
        "rm -rf /",
        "rm -rf /*",
        "> /dev/sda",
        "dd if=/dev/zero of=/dev/",
        ":(){ :|:& };:",  # Fork bomb
    ]

    cmd_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in cmd_lower:
            return False, f"Command contains dangerous pattern: {pattern}"

    return True, None


def validate_ip(ip: str) -> bool:
    """Validate IP address format."""
    if not ip:
        return False

    # Reject loopback
    if ip.startswith("127."):
        return False

    # Reject Docker/container bridge IPs (172.16-31.x.x)
    if ip.startswith("172."):
        try:
            second_octet = int(ip.split('.')[1])
            if 16 <= second_octet <= 31:
                return False
        except (IndexError, ValueError):
            return False

    # Reject link-local
    if ip.startswith("169.254."):
        return False

    # Reject podman default
    if ip.startswith("10.0."):
        return False

    # Basic format check
    parts = ip.split('.')
    if len(parts) != 4:
        return False

    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
    except ValueError:
        return False

    return True


# =============================================================================
# Export All
# =============================================================================

__all__ = [
    # Configuration
    "config",
    "ClusterConfig",
    "logger",
    # Paths
    "get_data_dir",
    "get_db_path",
    # Nodes
    "CLUSTER_NODES",
    "ClusterNode",
    "NodeOS",
    "NodeArch",
    "get_node",
    "get_available_nodes",
    "get_nodes_by_capability",
    "get_nodes_by_os",
    # Patterns
    "OFFLOAD_PATTERNS",
    "LOCAL_PATTERNS",
    "should_offload_command",
    # Status
    "TaskStatus",
    # Validation
    "validate_node_id",
    "validate_command",
    "validate_ip",
]
