#!/bin/bash
# setup_laptop.sh  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
# ติดตั้งสภาพแวดล้อมเทรน YOLO26 บน Ubuntu + NVIDIA GPU   ใช้: bash setup_laptop.sh
set -e
sudo apt update
sudo apt install -y python3-venv python3-pip git build-essential openssh-client
if ! command -v nvidia-smi > /dev/null; then
  echo "== ติดตั้ง NVIDIA driver (ครั้งแรกเท่านั้น) =="
  sudo ubuntu-drivers install
  echo ">>> รีบูตเครื่อง (sudo reboot) แล้วรัน bash setup_laptop.sh อีกครั้ง <<<"
  exit 0
fi
nvidia-smi
echo "== venv สำหรับเทรน =="
python3 -m venv ~/tgr-venv
source ~/tgr-venv/bin/activate
pip install -U pip
# PyTorch แบบ CUDA (ถ้า pytorch.org แนะนำเวอร์ชันใหม่กว่า ให้เปลี่ยน cu128 ตามหน้าเว็บ)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install ultralytics jupyterlab ipykernel ipywidgets matplotlib pandas paho-mqtt
python -m ipykernel install --user --name tgr --display-name "Python (tgr)"
python -c "import torch,ultralytics;print('torch',torch.__version__,'| CUDA',torch.cuda.is_available(),'|',torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-','| ultralytics',ultralytics.__version__)"
echo "== venv แยกสำหรับ X-AnyLabeling (กันไลบรารีชนกับชุดเทรน) =="
python3 -m venv ~/xal-venv
~/xal-venv/bin/pip install -U pip
~/xal-venv/bin/pip install x-anylabeling-cvhub
echo "เสร็จแล้ว: เปิด Jupyter ด้วย  source ~/tgr-venv/bin/activate && jupyter lab"
echo "           เปิด X-AnyLabeling ด้วย  ~/xal-venv/bin/xanylabeling"
