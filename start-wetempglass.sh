#!/bin/bash
# wetempglass 启动脚本 - 端口 6060

cd /home/nico/.openclaw/workspace-enya/wetempglass
nohup python3 -m http.server 6060 > /tmp/wetempglass.log 2>&1 &

echo "wetempglass 已启动 (port 6060)"
echo "PID: $(pgrep -f 'http.server 6060')"
echo "访问: http://<IP>:6060/index.html"