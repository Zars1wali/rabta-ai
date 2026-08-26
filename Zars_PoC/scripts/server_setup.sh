#!/usr/bin/env bash
# ==============================================================================
# Rabta AI — Vultr Server Hardening & Docker Setup Script
# Target OS: Ubuntu 24.04 LTS / 22.04 LTS (x86_64)
# Run as root: curl -sSL https://raw.githubusercontent.com/.../server_setup.sh | bash
# OR: bash scripts/server_setup.sh
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "🚀 RABTA AI — Production Server Hardening & Docker Setup"
echo "================================================================="

# 1. Update system packages
echo "📦 Updating APT packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

# 2. Install essential system utilities
echo "🛠️ Installing essential tools..."
apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    ufw \
    unattended-upgrades \
    ca-certificates \
    gnupg \
    lsb-release \
    htop \
    fail2ban \
    rclone

# 3. Create non-root deploy user 'rabta' with sudo privileges
if id "rabta" &>/dev/null; then
    echo "👤 User 'rabta' already exists."
else
    echo "👤 Creating dedicated sudo user 'rabta'..."
    useradd -m -s /bin/bash -g sudo rabta
    # Set passwordless sudo for automation
    echo "rabta ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/rabta
    chmod 0440 /etc/sudoers.d/rabta

    # Copy root authorized_keys if available
    if [ -f /root/.ssh/authorized_keys ]; then
        mkdir -p /home/rabta/.ssh
        cp /root/.ssh/authorized_keys /home/rabta/.ssh/
        chown -R rabta:sudo /home/rabta/.ssh
        chmod 700 /home/rabta/.ssh
        chmod 600 /home/rabta/.ssh/authorized_keys
        echo "🔑 Copied SSH keys to /home/rabta/.ssh/authorized_keys"
    fi
fi

# 4. SSH Hardening (Disable password authentication & root direct login)
echo "🔒 Hardening SSH configuration..."
SSH_CONFIG="/etc/ssh/sshd_config"
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' "$SSH_CONFIG"
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' "$SSH_CONFIG"
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' "$SSH_CONFIG"
systemctl reload ssh || systemctl reload sshd || true

# 5. Configure Firewall (UFW)
echo "🛡️ Configuring UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP (Caddy LetEncrypt)'
ufw allow 443/tcp comment 'HTTPS (Caddy)'
# Force enable without interactive prompt
echo "y" | ufw enable
ufw status verbose

# 6. Install Docker & Docker Compose Plugin
echo "🐳 Installing Docker & Docker Compose..."
if ! command -v docker &> /dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# Add rabta user to docker group
usermod -aG docker rabta
systemctl enable docker
systemctl start docker

# 7. Configure Unattended Security Upgrades (Auto-patching)
echo "🔄 Configuring automatic unattended security updates..."
cat << 'EOF' > /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::InstallOnShutdown "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

cat << 'EOF' > /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# 8. Setup Application Directory Structure
echo "📁 Initializing /opt/rabta application directory..."
mkdir -p /opt/rabta
mkdir -p /opt/rabta/backups
chown -R rabta:sudo /opt/rabta

echo "================================================================="
echo "✅ SERVER HARDENING COMPLETE!"
echo ""
echo "Next Steps for the Founder:"
echo "1. Switch to user 'rabta': su - rabta"
echo "2. Clone repo into /opt/rabta: git clone <your-repo-url> /opt/rabta"
echo "3. Copy your .env file into /opt/rabta/.env"
echo "4. Run: cd /opt/rabta && bash scripts/deploy.sh"
echo "================================================================="
