# Kryten systemd Service Configuration

This directory contains systemd service files for running Kryten as a system service.

## Files

- **kryten.service** - Main Kryten connector service
- **nats.service** - NATS server with JetStream enabled

## Prerequisites

### 1. Install NATS Server

```bash
# Download and install NATS server
curl -L https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.tar.gz -o nats-server.tar.gz
tar -xzf nats-server.tar.gz
sudo cp nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/
sudo chmod +x /usr/local/bin/nats-server

# Verify installation
nats-server --version
```

### 2. Create System Users

```bash
# Create NATS user
sudo useradd -r -s /bin/false -d /var/lib/nats nats

# Create Kryten user
sudo useradd -r -s /bin/false -d /opt/kryten kryten
```

### 3. Create Directories

```bash
# NATS directories
sudo mkdir -p /var/lib/nats
sudo chown nats:nats /var/lib/nats

# Kryten directories
sudo mkdir -p /opt/kryten/{logs,venv}
sudo chown -R kryten:kryten /opt/kryten
```

### 4. Create NATS Configuration

```bash
sudo mkdir -p /etc/nats
sudo tee /etc/nats/nats-server.conf << 'EOF'
# NATS Server Configuration
port: 4222

# Enable JetStream
jetstream {
    store_dir: /var/lib/nats
    max_memory_store: 512MB
    max_file_store: 10GB
}

# Logging
log_file: "/var/log/nats/nats.log"
log_size_limit: 100MB
debug: false
trace: false

# Limits
max_payload: 10MB
max_connections: 1000
EOF
```

### 5. Install Kryten

```bash
# Clone repository (or copy files)
cd /opt/kryten
sudo -u kryten git clone https://github.com/yourusername/kryten-robot .

# Create virtual environment
sudo -u kryten python3 -m venv venv
sudo -u kryten venv/bin/pip install --upgrade pip
sudo -u kryten venv/bin/pip install -e .

# Copy and configure config file
sudo -u kryten cp kryten/config.example.json config.json
sudo -u kryten nano config.json  # Edit with your settings
```

## Installation

### 1. Install Service Files

```bash
# Copy service files
sudo cp systemd/nats.service /etc/systemd/system/
sudo cp systemd/kryten.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload
```

### 2. Enable Services

```bash
# Enable NATS to start on boot
sudo systemctl enable nats.service

# Enable Kryten to start on boot
sudo systemctl enable kryten.service
```

### 3. Start Services

```bash
# Start NATS first
sudo systemctl start nats.service

# Verify NATS is running
sudo systemctl status nats.service

# Start Kryten
sudo systemctl start kryten.service

# Verify Kryten is running
sudo systemctl status kryten.service
```

## Management Commands

### Check Status

```bash
# Check service status
sudo systemctl status kryten.service
sudo systemctl status nats.service

# View recent logs
sudo journalctl -u kryten.service -n 50 -f
sudo journalctl -u nats.service -n 50 -f
```

### Start/Stop/Restart

```bash
# Kryten
sudo systemctl start kryten.service
sudo systemctl stop kryten.service
sudo systemctl restart kryten.service

# NATS
sudo systemctl start nats.service
sudo systemctl stop nats.service
sudo systemctl restart nats.service
```

### View Logs

```bash
# Follow Kryten logs
sudo journalctl -u kryten.service -f

# View last 100 lines
sudo journalctl -u kryten.service -n 100

# View logs since today
sudo journalctl -u kryten.service --since today

# View logs with timestamps
sudo journalctl -u kryten.service -o short-iso

# Filter by priority (error and above)
sudo journalctl -u kryten.service -p err
```

### Enable/Disable Auto-start

```bash
# Enable auto-start on boot
sudo systemctl enable kryten.service

# Disable auto-start
sudo systemctl disable kryten.service
```

## Configuration

### Update Configuration

```bash
# Edit config file
sudo -u kryten nano /opt/kryten/config.json

# Restart service to apply changes
sudo systemctl restart kryten.service
```

### Update Kryten Code

```bash
# Stop service
sudo systemctl stop kryten.service

# Update code
cd /opt/kryten
sudo -u kryten git pull

# Reinstall if dependencies changed
sudo -u kryten venv/bin/pip install -e .

# Start service
sudo systemctl start kryten.service
```

## Monitoring

### Check Health Endpoint

If health monitoring is enabled in your config:

```bash
# Check health
curl http://localhost:8080/health

# Pretty print
curl -s http://localhost:8080/health | python3 -m json.tool

# Check metrics
curl http://localhost:8080/metrics
```

### System Resource Usage

```bash
# Check memory and CPU usage
systemctl status kryten.service

# Detailed resource info
systemd-cgtop -m
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status and logs
sudo systemctl status kryten.service
sudo journalctl -u kryten.service -n 50

# Common issues:
# 1. Config file permissions
sudo chmod 644 /opt/kryten/config.json
sudo chown kryten:kryten /opt/kryten/config.json

# 2. NATS not running
sudo systemctl status nats.service
sudo systemctl start nats.service

# 3. Missing dependencies
sudo -u kryten /opt/kryten/venv/bin/pip install -e /opt/kryten

# 4. Invalid config
sudo -u kryten /opt/kryten/venv/bin/python -m kryten /opt/kryten/config.json
```

### JetStream Not Available

```bash
# Verify NATS is running with JetStream
nats-server --version
curl http://localhost:8222/jsz

# Check NATS config
cat /etc/nats/nats-server.conf

# Restart NATS with JetStream
sudo systemctl restart nats.service
```

### Service Keeps Restarting

```bash
# View all restart attempts
sudo journalctl -u kryten.service | grep -i restart

# Check for crash loops
sudo systemctl status kryten.service

# Increase restart delay if needed
sudo systemctl edit kryten.service
# Add:
# [Service]
# RestartSec=30s
```

### Logs Not Appearing

```bash
# Check journal is working
sudo journalctl -u kryten.service --since "5 minutes ago"

# Verify service is running
sudo systemctl status kryten.service

# Check log_level in config.json
sudo -u kryten cat /opt/kryten/config.json | grep log_level
```

## Security Considerations

### Protect Sensitive Configuration

```bash
# Ensure config file is not world-readable (contains passwords)
sudo chmod 600 /opt/kryten/config.json
sudo chown kryten:kryten /opt/kryten/config.json

# Use environment variables for secrets (alternative)
sudo systemctl edit kryten.service
# Add:
# [Service]
# Environment="CYTUBE_PASSWORD=secret"
```

### Firewall Configuration

```bash
# If allowing remote NATS connections
sudo firewall-cmd --permanent --add-port=4222/tcp
sudo firewall-cmd --reload

# If allowing remote health checks
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

### SELinux

If using SELinux, you may need to adjust policies:

```bash
# Check for denials
sudo ausearch -m avc -ts recent | grep kryten

# Generate and apply policy (if needed)
sudo ausearch -m avc -ts recent | audit2allow -M kryten
sudo semodule -i kryten.pp
```

## Uninstallation

```bash
# Stop and disable services
sudo systemctl stop kryten.service nats.service
sudo systemctl disable kryten.service nats.service

# Remove service files
sudo rm /etc/systemd/system/kryten.service
sudo rm /etc/systemd/system/nats.service
sudo systemctl daemon-reload

# Remove directories (optional)
sudo rm -rf /opt/kryten
sudo rm -rf /var/lib/nats
sudo rm -rf /etc/nats

# Remove users (optional)
sudo userdel kryten
sudo userdel nats
```

## Advanced Configuration

### Running Multiple Instances

To run multiple Kryten instances for different channels:

```bash
# Copy and modify service file
sudo cp /etc/systemd/system/kryten.service /etc/systemd/system/kryten-channel2.service
sudo nano /etc/systemd/system/kryten-channel2.service

# Update:
# - Description
# - WorkingDirectory=/opt/kryten-channel2
# - ExecStart config path

# Create separate directory
sudo mkdir /opt/kryten-channel2
sudo cp -r /opt/kryten/* /opt/kryten-channel2/
sudo chown -R kryten:kryten /opt/kryten-channel2

# Enable and start
sudo systemctl enable kryten-channel2.service
sudo systemctl start kryten-channel2.service
```

### Log Rotation

systemd journal handles rotation automatically, but for custom log files:

```bash
sudo tee /etc/logrotate.d/kryten << 'EOF'
/opt/kryten/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 kryten kryten
}
EOF
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/kryten-robot/issues
- Documentation: See main README.md
- NATS Documentation: https://docs.nats.io
- systemd Manual: `man systemd.service`
