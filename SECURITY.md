# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in cluster-execution-mcp, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email security concerns to the repository owner via GitHub
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You can expect:
- Acknowledgment within 48 hours
- Status update within 7 days
- Fix timeline based on severity

## Security Model

### Trust Boundaries

```
┌─────────────────────────────────────────────────────┐
│                    User (Human)                      │
│              Initiates commands via Claude           │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│              Claude Code (MCP Client)                │
│         Validates user intent, calls tools           │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│            cluster-execution-mcp Server              │
│    Command validation, routing, SSH execution        │
└─────────────────────┬───────────────────────────────┘
                      │ SSH
┌─────────────────────▼───────────────────────────────┐
│              Cluster Nodes (SSH targets)             │
│     builder, orchestrator, researcher, inference     │
└─────────────────────────────────────────────────────┘
```

### Security Features

#### Shell Injection Prevention

All remote commands use `subprocess.run()` with explicit argument lists:

```python
# Commands are passed as single strings to SSH
subprocess.run(
    ["ssh", "-o", "ConnectTimeout=5", f"{user}@{ip}", command],
    capture_output=True,
    timeout=timeout
)
```

#### Command Validation

Dangerous command patterns are blocked before execution:

- `rm -rf /` - Root filesystem deletion
- `rm -rf /*` - Root-level wildcard deletion
- `> /dev/sda` - Direct disk writes
- `:(){ :|:& };:` - Fork bombs
- Commands containing `\x00` null bytes

#### IP Address Validation

The router validates IP addresses and rejects:

- Loopback addresses (127.x.x.x)
- Docker bridge networks (172.17.x.x)
- Link-local addresses (169.254.x.x)
- Invalid format addresses

#### SSH Hardening

SSH connections use security-focused options:

```bash
-o ConnectTimeout=5          # Prevent hanging connections
-o StrictHostKeyChecking=accept-new  # Accept new hosts, verify returning
-o BatchMode=yes             # Non-interactive, fail on prompts
-o ServerAliveInterval=30    # Detect dead connections
```

### Configuration Security

All sensitive configuration is via environment variables:

| Variable | Purpose | Security Note |
|----------|---------|---------------|
| `CLUSTER_SSH_USER` | SSH username | Keep restricted |
| `CLUSTER_*_IP` | Node IPs | Internal network only |
| `CLUSTER_*_HOST` | Hostnames | Internal DNS only |

**Never commit actual IPs or hostnames to version control.**

### Network Security Requirements

1. **SSH Key Authentication**: Configure SSH keys, not passwords
2. **Network Isolation**: Cluster should be on isolated network
3. **Firewall Rules**: Limit SSH access to known sources
4. **No Public Exposure**: Never expose MCP servers to internet

### Known Limitations

1. **Command Visibility**: Commands are logged and may appear in process lists
2. **SSH Agent**: Relies on SSH agent for key management
3. **Output Capture**: Command output is captured and returned to client

### Hardening Recommendations

```bash
# 1. Use dedicated SSH key for cluster
ssh-keygen -t ed25519 -f ~/.ssh/cluster_key -C "cluster-execution"

# 2. Restrict key usage in authorized_keys
# On each node, add to ~/.ssh/authorized_keys:
# restrict,command="/usr/local/bin/cluster-shell" ssh-ed25519 ...

# 3. Set restrictive file permissions
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/cluster_key

# 4. Use firewall rules
# Allow SSH only from known cluster nodes
```

### Audit Logging

The server logs:
- Command execution requests
- Routing decisions
- SSH connection attempts
- Validation failures

Review logs regularly for anomalies.

## Security Updates

Security updates are released as patch versions (0.2.x).

Subscribe to GitHub releases to receive security notifications.
