#!/bin/bash
cd /home/ec2-user/projects/Plexus

echo "Installing package in editable mode..."
conda activate py311
pip install .

echo "Restarting Plexus Command Worker..."
sudo systemctl restart plexus-command-worker

echo "Restarting FastAPI service..."
sudo systemctl restart fastapi

echo "Deployment completed successfully!" 