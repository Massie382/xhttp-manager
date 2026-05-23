[Unit]
Description=XHTTP Manager API Server
After=network.target xray.service
Wants=xray.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/xhttp-manager/addon
Environment=PYTHONPATH=/opt/xhttp-manager/addon
ExecStart=/opt/xhttp-manager/venv/bin/python /opt/xhttp-manager/addon/run.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
