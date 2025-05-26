ALLOWED_ENV_NAMES = dev staging prod
PROJECT_NAME := $(notdir $(CURDIR))

define COMPOSE_UP
	@set -a; \
	ENV_NAME=$(1); \
	DUMP_ENV=$$( [ "$$ENV_NAME" = "staging" ] && echo "dev" || echo "$$ENV_NAME" ); \
	PROJECT_NAME=$$(echo "$(PROJECT_NAME)-$(1)" | tr '[:upper:]' '[:lower:]'); \
	export DUMP_ENV; \
	for f in profiles/$(1)/.env.*; do \
		. $$f; \
	done; \
	set +a; \
	mkdir -p ./docker/liquibase/changelog && chmod -R 777 ./docker/liquibase/changelog; \
	chmod +x ./docker/liquibase/migrate.sh; \
	docker compose -p $$PROJECT_NAME up --build -d; \
	docker image prune -f
endef

.PHONY: $(ALLOWED_ENV_NAMES) stop help

$(ALLOWED_ENV_NAMES):
	@echo "🔧 Starting environment: $@"
	$(call COMPOSE_UP,$@)

%:
	$(MAKE) --no-print-directory help

stop:
	@ENV_NAME=$${env:-dev}; \
	if [ "$$ENV_NAME" = "dev" ]; then \
		VOLUME_FLAG=$${v:-v}; \
	else \
		VOLUME_FLAG=$${v:-}; \
	fi; \
	if [ "$$VOLUME_FLAG" = "v" ]; then \
		echo "🛑 Stopping environment: $$ENV_NAME (with volumes)"; \
		docker compose -p $(PROJECT_NAME)-$$ENV_NAME down -v; \
	else \
		echo "🛑 Stopping environment: $$ENV_NAME"; \
		docker compose -p $(PROJECT_NAME)-$$ENV_NAME down; \
	fi

logs:
	@ENV_NAME=$${env:-dev}; \
	docker compose -p $(PROJECT_NAME)-$$ENV_NAME logs -f;


help:
	@echo "Available commands:"
	@echo "  make dev       – start dev environment"
	@echo "  make staging   – start staging environment"
	@echo "  make prod      – start prod environment"
	@echo "  make stop env=dev|staging|prod [v=v] – stop environment with optional volumes"
	@echo "  make logs env=dev|staging|prod – show logs for the specified environment"
