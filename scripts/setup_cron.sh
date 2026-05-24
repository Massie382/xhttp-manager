#!/bin/bash
# Setup cron jobs for cumulative accumulator and live enforcer

cat > /etc/cron.d/xhttp-enforcement << 'EOF'
* * * * * root /usr/bin/python3 /opt/xhttp-manager/scripts/cumulative_accumulator.py >> /var/log/cumulative-accumulator.log 2>&1
* * * * * root /usr/bin/python3 /opt/xhttp-manager/scripts/live_enforcer.py >> /var/log/live-enforcer.log 2>&1
EOF

chmod 644 /etc/cron.d/xhttp-enforcement
echo "✅ Cron jobs installed. Logs: /var/log/cumulative-accumulator.log and /var/log/live-enforcer.log"