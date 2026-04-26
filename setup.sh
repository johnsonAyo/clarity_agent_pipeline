#!/bin/bash

# Clarity Bot VPS Setup Script
# Works on Ubuntu 20.04+

echo "🚀 Starting Clarity Bot Setup..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and Node (for PM2)
sudo apt install -y python3-pip nodejs npm

# Install PM2 globally
sudo npm install pm2 -g

# Install Python dependencies
pip3 install -r requirements.txt

echo "✅ Setup complete!"
echo "To start the bot, run: pm2 start ecosystem.config.js"
echo "To view logs, run: pm2 logs clarity-bot"
