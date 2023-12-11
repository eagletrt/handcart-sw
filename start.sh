# Use this script to start the backend

sudo systemctl stop handcart-backend.service

echo "killed backend service, executing run.py directly"

python3 src/run.py