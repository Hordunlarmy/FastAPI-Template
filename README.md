# app-backend

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Atlas CLI (for local development)

### Install Atlas CLI
```bash
# macOS
brew install ariga/tap/atlas

# Linux
curl -sSL https://atlasgo.sh | sh

# Windows
winget install ariga.atlas
```

### Start the Application
```bash
# Start all services (app, database, redis, minio)
make up

# Or start specific environment
make up env=dev
make up env=staging
make up env=prod
```

### Database Migrations
```bash
# Generate new migration (runs locally)
make migration env=dev

# Apply migrations (runs in Docker)
make migrate env=dev

# Show schema diff (runs locally)
make diff env=dev

# Initialize migrations (runs locally)
make migrate-init env=dev
```

### Other Commands
```bash
# View logs
make logs env=dev

# Stop services
make down env=dev

# Get help
make help
```

## Environment Variables
Configure your environment in `.envs/{env}/.env.*` files.
