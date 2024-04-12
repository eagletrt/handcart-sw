# Use this script to start the backend
# Telemetry will be stopped, CLI will allow to use commands

echo "Enabling handcart service..."
sudo systemctl enable handcart-backend.service
echo "Done"

echo -n "Starting handcart service..."
sudo systemctl start handcart-backend.service
echo "Done"

echo "Enabling telemetry service..."
sudo systemctl enable telemetry.service
echo "Done"

echo -n "Starting telemetry service..."
sudo systemctl start telemetry.service
echo "Done"

echo "Running python script with CLI"

python3 src/run.py