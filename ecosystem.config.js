module.exports = {
  apps : [{
    name: "clarity-bot",
    script: "python3",
    args: "main.py",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: "production",
    }
  }]
}
