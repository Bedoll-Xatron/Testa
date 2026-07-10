module.exports = {
  apps: [{
    name: 'testa-bot',
    script: 'main.py',
    interpreter: 'python',
    watch: false,
    autorestart: true,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'development'
    },
    env_production: {
      NODE_ENV: 'production'
    }
  }]
};
