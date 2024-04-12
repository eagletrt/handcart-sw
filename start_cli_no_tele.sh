# Use this script to start the backend
# Telemetry will be stopped, CLI will allow to use commands

echo -n "Stopping handcart service..."
sudo systemctl stop handcart-backend.service
echo "Done"
echo -n "Stopping telemetry service..."
sudo systemctl stop telemetry.service
echo "Done"

echo "Running python script with CLI"

python3 src/run.py