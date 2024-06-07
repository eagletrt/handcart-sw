# Use this script to start the backend (no settings will be available in the CLI)

echo -n "Stopping handcart service..."
sudo systemctl stop handcart-backend.service
echo "Done"

echo "Running python script with CLI"

bash run.sh