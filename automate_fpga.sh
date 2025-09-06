#!/bin/bash

# ========================================
#   Stable FPGA MQTT Automation Script
# ========================================

echo "========================================"
echo "   Stable FPGA MQTT Setup"
echo "========================================"
echo

# 清理函数
cleanup() {
    echo "🛑 Cleaning up previous processes..."
    pkill -f "sshpass" 2>/dev/null
    pkill -f "python3 laptop_FB_mqtt.py" 2>/dev/null
    pkill -f "ultra96_mqtt.py" 2>/dev/null
    sudo fuser -k 8888/tcp 2>/dev/null
    sudo fuser -k 8889/tcp 2>/dev/null
    sleep 2
    echo "✅ Cleanup completed"
}

# 设置退出时自动清理
trap cleanup EXIT

# 步骤1: 预先清理
echo "[1/8] Performing pre-run cleanup..."
cleanup

# 步骤2: 检查端口状态
echo "[2/8] Checking port availability..."
if lsof -i :8888 >/dev/null 2>&1; then
    echo "❌ Port 8888 is occupied, forcing cleanup..."
    sudo fuser -k 8888/tcp
    sleep 3
fi

# 步骤3: 安装sshpass
echo "[3/8] Checking/Installing sshpass..."
if ! command -v sshpass &> /dev/null; then
    echo "Installing sshpass..."
    sudo apt update
    sudo apt install -y sshpass
else
    echo "sshpass is already installed"
fi

# 步骤4: 自动SSH连接到FPGA并清理文件
echo "[4/8] Launching SSH to FPGA with file cleanup..."
cd /mnt/d/y4sem1/CG4002/comms

sshpass -p 'xilinx' ssh -o StrictHostKeyChecking=no xilinx@makerslab-fpga-53.ddns.comp.nus.edu.sg '
    echo "=== Remote FPGA Setup ==="
    echo "Changing to CG4002 directory..."
    cd CG4002
    
    echo "Checking for existing imu_data.csv..."
    if [ -f "imu_data.csv" ]; then
        echo "Clearing imu_data.csv content..."
        > imu_data.csv
        echo "✅ imu_data.csv cleared"
    else
        echo "Creating new imu_data.csv..."
        touch imu_data.csv
    fi
    
    echo "Current directory files:"
    ls -la
    
    echo "Starting ultra96_mqtt.py..."
    echo "========================================"
    python3 ultra96_mqtt.py
' &
SSH_PID1=$!
echo "Ultra96 MQTT script started (PID: $SSH_PID1)"

# 步骤5: 等待SSH连接建立
echo "[5/8] Waiting for SSH connection to establish..."
sleep 8

# 步骤6: 自动SSH端口转发
echo "[6/8] Setting up SSH port forwarding..."
if lsof -i :8888 >/dev/null 2>&1; then
    echo "⚠️ Port 8888 occupied, using alternative port 8889..."
    sshpass -p 'xilinx' ssh -o StrictHostKeyChecking=no -L 8889:localhost:8889 -N xilinx@makerslab-fpga-53.ddns.comp.nus.edu.sg &
else
    sshpass -p 'xilinx' ssh -o StrictHostKeyChecking=no -L 8888:localhost:8889 -N xilinx@makerslab-fpga-53.ddns.comp.nus.edu.sg &
fi
SSH_PID2=$!
echo "Port forwarding established (PID: $SSH_PID2)"
sleep 3

# 步骤7: 本地MQTT监听器
echo "[7/8] Starting local MQTT listener..."
cd /mnt/d/y4sem1/CG4002/comms
python3 laptop_FB_mqtt.py &
MQTT_PID=$!
echo "Local MQTT listener started (PID: $MQTT_PID)"
sleep 3

# 步骤8: 打开VS Code
echo "[8/8] Opening VS Code..."
cd /mnt/d/y4sem1/CG4002
cmd.exe /c "code hardware_mqtt.py" 2>/dev/null &

echo "========================================"
echo "          Setup Complete!"
echo "========================================"
echo "✅ All services started successfully!"
echo "📊 Process PIDs:"
echo "   - SSH Connection: $SSH_PID1"
echo "   - Port Forwarding: $SSH_PID2" 
echo "   - Local MQTT: $MQTT_PID"
echo ""
echo "🎯 Next step:"
echo "   In VS Code terminal, run: python hardware_mqtt.py"
echo ""
echo "🛑 To stop all services:"
echo "   Press Ctrl+C or run: pkill -f sshpass; pkill -f python3"
echo "========================================"

# 保持脚本运行，直到用户中断
echo "Press Ctrl+C to stop all services..."
wait
