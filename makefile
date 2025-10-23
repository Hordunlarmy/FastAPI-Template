ALLOWED_ENV_NAMES = dev staging prod local
PROJECT_NAME := $(shell echo $(notdir $(CURDIR)) | tr '[:upper:]' '[:lower:]')
ENV_NAME ?= $(if $(env),$(env),$(if $(ENV),$(ENV),local))
ATLAS_CONFIG=file://config/atlas/atlas.hcl

define COMPOSE_UP
	set -a; \
	ENV_NAME=$(1); \
	DUMP_ENV=$$( [ "$$ENV_NAME" = "staging" ] && echo "dev" || echo "$$ENV_NAME" ); \
	PROJECT_NAME=$(PROJECT_NAME); \
	export DUMP_ENV; \
	echo "🔐 Checking ownership for specific directories..."; \
	for f in .envs/$$ENV_NAME/.env.*; do \
		if [ -f "$$f" ]; then \
			echo "📥 Loading env file: $$f"; \
			while IFS= read -r line; do \
				case "$$line" in \
					\#*|'') continue ;; \
					[A-Za-z_]*=*) eval "export $$line" ;; \
				esac; \
			done < "$$f"; \
		fi; \
	done; \
	set +a; \
	if [ "$$ENV_NAME" = "prod" ] || [ "$$ENV_NAME" = "staging" ]; then \
		docker compose -p $(PROJECT_NAME)-$$ENV_NAME --profile prod up --build -d; \
	else \
		docker compose -p $(PROJECT_NAME)-$$ENV_NAME up --build -d; \
	fi; \
	docker image prune -f
endef

.PHONY: $(ALLOWED_ENV_NAMES) stop help logs logs-% migration migrate diff init-migration \
        k8s-describe k8s-logs k8s-exec k8s-restart k8s-events \
        grpc-generate test-inference

$(ALLOWED_ENV_NAMES):
	@echo "🔧 Starting environment: $@"
	@$(call COMPOSE_UP,$@)

%:
	$(MAKE) --no-print-directory help

up:
	@ENV_NAME=$(ENV_NAME); \
	echo "🔧 Starting environment: $$ENV_NAME"; \
	$(call COMPOSE_UP,$(ENV_NAME))

down:
	@ENV_NAME=$(ENV_NAME); \
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
	@ENV_NAME=$(ENV_NAME); \
	TAIL=$${tail:-100}; \
	docker compose -p $(PROJECT_NAME)-$$ENV_NAME logs --tail=$$TAIL -f

logs-%:
	@ENV_NAME=$(ENV_NAME); \
	TAIL=$${tail:-100}; \
	docker compose -p $(PROJECT_NAME)-$$ENV_NAME logs --tail=$$TAIL -f $*

exec-%:
	@ENV_NAME=$(ENV_NAME); \
	CONTAINER_NAME=$$(docker compose -p $(PROJECT_NAME)-$$ENV_NAME ps -q $*); \
	if [ -z "$$CONTAINER_NAME" ]; then \
		echo "❌ No container found for service: $*"; \
	else \
		echo "💻 Executing into container $$CONTAINER_NAME..."; \
		docker exec -it $$CONTAINER_NAME bash || docker exec -it $$CONTAINER_NAME /bin/bash || docker exec -it $$CONTAINER_NAME /bin/sh; \
	fi

restart-%:
	@ENV_NAME=$(ENV_NAME); \
	CONTAINER_NAME=$$(docker compose -p $(PROJECT_NAME)-$$ENV_NAME ps -q $*); \
	if [ -z "$$CONTAINER_NAME" ]; then \
		echo "❌ No container found for service: $*"; \
	else \
		echo "🔄 Restarting service $* (container $$CONTAINER_NAME)..."; \
		docker compose -p $(PROJECT_NAME)-$$ENV_NAME restart $*; \
	fi
start-%:
	@ENV_NAME=$(ENV_NAME); \
	echo "▶️ Starting service $*..."; \
	docker compose -p $(PROJECT_NAME)-$$ENV_NAME start $*

stop-%:
	@ENV_NAME=$(ENV_NAME); \
	CONTAINER_NAME=$$(docker compose -p $(PROJECT_NAME)-$$ENV_NAME ps -q $*); \
	if [ -z "$$CONTAINER_NAME" ]; then \
		echo "❌ No container found for service: $*"; \
	else \
		echo "🛑 Stopping service $* (container $$CONTAINER_NAME)..."; \
		docker compose -p $(PROJECT_NAME)-$$ENV_NAME stop $*; \
	fi

migrate:
	@ENV_NAME=$(ENV_NAME); \
	PROJECT_NAME=$(PROJECT_NAME); \
	ENV=$$ENV_NAME docker compose -p $(PROJECT_NAME)-$$ENV_NAME run --rm atlas

migration:
	@ENV_NAME=$(ENV_NAME); \
	atlas migrate diff --config $(ATLAS_CONFIG) --env $$ENV_NAME

migrate-init:
	@ENV_NAME=$(ENV_NAME); \
	atlas migrate hash --config $(ATLAS_CONFIG) --env $$ENV_NAME && \
	atlas migrate new initial --config $(ATLAS_CONFIG) --env $$ENV_NAME

diff:
	@ENV_NAME=$(ENV_NAME); \
	atlas migrate diff --config $(ATLAS_CONFIG) --env $$ENV_NAME

k8s-prep:
	@set -e; \
	ENV_NAME=$(ENV_NAME); \
	if [ -z "$(REGISTRY_TYPE)" ]; then \
	  echo "⚠️ REGISTRY_TYPE is not set. Please export REGISTRY_TYPE=NULL if you want to skip generating image pull secret else set to appropriate registry e.g ghcr or ecr"; \
	  exit 1; \
	elif [ "$(REGISTRY_TYPE)" != "NULL" ]; then \
	  infra/scripts/k8s/generate-image-pull-secret.sh $(REGISTRY_TYPE) $$ENV_NAME; \
	else \
	  echo "Skipping image pull secret generation because REGISTRY_TYPE is set to NULL."; \
	fi; \
	infra/scripts/k8s/generate-secrets.sh $$ENV_NAME; \
	infra/scripts/k8s/generate-configmaps.sh $$ENV_NAME; \
	infra/scripts/k8s/generate-templates.sh $$ENV_NAME

k8s-apply:
	@echo "DEBUG: Running kubectl with config: $$KUBECONFIG"
	kubectl get ns
	@ENV_NAME=$(ENV_NAME); \
	echo "🚀 Deploying Kubernetes manifests for environment: $$ENV_NAME"; \
	infra/scripts/k8s/apply-manifests.sh $$ENV_NAME

k8s-describe-%:
	@APP_INPUT=$*; \
	ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	APP_NAME=$$(echo "$$APP_INPUT" | sed -E 's/[0-9]+$$//'); \
	INDEX_STR=$$(echo "$$APP_INPUT" | grep -oE '[0-9]+$$'); \
	PODS_LINE=$$(kubectl get pods -n $$NAMESPACE -l app=$$APP_NAME -o jsonpath='{.items[*].metadata.name}'); \
	set -- $$PODS_LINE; \
	if [ -z "$$INDEX_STR" ]; then \
		for POD in "$$@"; do \
			echo "🔍 Describing pod $$POD in namespace $$NAMESPACE..."; \
			kubectl describe pod -n $$NAMESPACE $$POD || true; \
			echo ""; \
		done; \
	else \
		INDEX=$$((INDEX_STR)); \
		POD=$$(eval "echo \$$$$(($$INDEX + 1))"); \
		if [ -z "$$POD" ]; then \
			echo "❌ No pod at index $$INDEX_STR for app=$$APP_NAME"; \
		else \
			echo "🔍 Describing pod $$POD (index $$INDEX_STR) in namespace $$NAMESPACE..."; \
			kubectl describe pod -n $$NAMESPACE $$POD; \
		fi; \
	fi

k8s-logs-%:
	@APP_INPUT=$*; \
	ENV_NAME=$(ENV_NAME); \
	TAIL=$${tail:-100}; \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	APP_NAME=$$(echo "$$APP_INPUT" | sed -E 's/[0-9]+$$//'); \
	INDEX_STR=$$(echo "$$APP_INPUT" | grep -oE '[0-9]+$$'); \
	PODS_LINE=$$(kubectl get pods -n $$NAMESPACE -l app=$$APP_NAME -o jsonpath='{.items[*].metadata.name}'); \
	set -- $$PODS_LINE; \
	if [ -z "$$INDEX_STR" ]; then \
		echo "📦 Merged logs from all $$APP_NAME pods in $$NAMESPACE (color-coded)..."; \
		( \
			trap 'echo ""; echo "🛑 Stopping logs..."; pkill -9 -f "kubectl logs" 2>/dev/null; exit 0' INT TERM; \
			( \
				INDEX=0; \
				for POD in "$$@"; do \
					COLOR=$$(expr 31 + $$INDEX % 7); \
					kubectl logs -n $$NAMESPACE $$POD --tail=$$TAIL -f 2>/dev/null | \
					awk -v c="$$COLOR" -v p="[$$POD]" 'NF { printf "\033[%sm%s\033[0m %s\n", c, p, $$0; fflush(); }' & \
					INDEX=$$(expr $$INDEX + 1); \
				done; \
				wait \
			) & \
			wait \
		); \
	else \
		INDEX=$$INDEX_STR; \
		POD=$$(eval "echo \$$$$(($$INDEX + 1))"); \
		if [ -z "$$POD" ]; then \
			echo "❌ No pod at index $$INDEX_STR for app=$$APP_NAME"; \
		else \
			echo "📦 Logs from $$POD (index $$INDEX_STR):"; \
			kubectl logs -n $$NAMESPACE $$POD --tail=$$TAIL -f; \
		fi; \
	fi


k8s-exec-%:
	@APP_INPUT=$*; \
	ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	APP_NAME=$$(echo "$$APP_INPUT" | sed -E 's/[0-9]+$$//'); \
	INDEX_STR=$$(echo "$$APP_INPUT" | grep -oE '[0-9]+$$'); \
	PODS_LINE=$$(kubectl get pods -n $$NAMESPACE -l app=$$APP_NAME -o jsonpath='{.items[*].metadata.name}'); \
	set -- $$PODS_LINE; \
	INDEX=$$(if [ -z "$$INDEX_STR" ]; then echo 0; else echo $$INDEX_STR; fi); \
	POD=$$(eval "echo \$$$$(($$INDEX + 1))"); \
	if [ -z "$$POD" ]; then \
		echo "❌ No pod at index $$INDEX for app=$$APP_NAME"; \
	else \
		echo "💻 Executing into pod $$POD (index $$INDEX)..."; \
		kubectl exec -n $$NAMESPACE -it $$POD -- bash 2>/dev/null || \
		kubectl exec -n $$NAMESPACE -it $$POD -- /bin/bash 2>/dev/null || \
		kubectl exec -n $$NAMESPACE -it $$POD -- /bin/sh; \
	fi


k8s-restart-%:
	@APP_INPUT=$*; \
	ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	APP_NAME=$$(echo "$$APP_INPUT" | sed -E 's/[0-9]+$$//'); \
	INDEX_STR=$$(echo "$$APP_INPUT" | grep -oE '[0-9]+$$'); \
	PODS_LINE=$$(kubectl get pods -n $$NAMESPACE -l app=$$APP_NAME -o jsonpath='{.items[*].metadata.name}'); \
	set -- $$PODS_LINE; \
	if [ -z "$$INDEX_STR" ]; then \
		echo "🔁 Restarting ALL pods for app=$$APP_NAME in $$NAMESPACE..."; \
		kubectl delete pod -n $$NAMESPACE "$$@"; \
	else \
		INDEX=$$((INDEX_STR)); \
		POD=$$(eval "echo \$$$$(($$INDEX + 1))"); \
		if [ -z "$$POD" ]; then \
			echo "❌ No pod at index $$INDEX for app=$$APP_NAME"; \
		else \
			echo "🔁 Restarting pod $$POD (index $$INDEX) for app=$$APP_NAME in $$NAMESPACE..."; \
			kubectl delete pod -n $$NAMESPACE $$POD; \
		fi; \
	fi

k8s-rollout-%:
	@APP_INPUT=$*; \
	ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	APP_NAME=$$(echo "$$APP_INPUT" | sed -E 's/[0-9]+$$//'); \
	INDEX_STR=$$(echo "$$APP_INPUT" | grep -oE '[0-9]+$$'); \
	if [ -z "$$INDEX_STR" ]; then \
		echo "🔁 Rolling restart of deployment $$APP_NAME in $$NAMESPACE..."; \
		kubectl rollout restart deployment $$APP_NAME -n $$NAMESPACE; \
	else \
		echo "⚠️  Cannot restart a single pod with rollout restart. Restarting entire deployment $$APP_NAME instead..."; \
		kubectl rollout restart deployment $$APP_NAME -n $$NAMESPACE; \
	fi


k8s-events-%:
	@APP_INPUT=$*; \
	ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	if [ -z "$$APP_INPUT" ]; then \
		echo "📜 Fetching all events from namespace $$NAMESPACE..."; \
		kubectl get events -n $$NAMESPACE --sort-by='.lastTimestamp'; \
	else \
		APP_NAME=$$(echo "$$APP_INPUT" | sed -E 's/[0-9]+$$//'); \
		INDEX_STR=$$(echo "$$APP_INPUT" | grep -oE '[0-9]+$$'); \
		PODS_LINE=$$(kubectl get pods -n $$NAMESPACE -l app=$$APP_NAME -o jsonpath='{.items[*].metadata.name}'); \
		set -- $$PODS_LINE; \
		if [ -z "$$INDEX_STR" ]; then \
			for POD in "$$@"; do \
				echo "📜 Events for pod $$POD:"; \
				kubectl get events -n $$NAMESPACE --field-selector involvedObject.name=$$POD --sort-by='.lastTimestamp' || true; \
				echo ""; \
			done; \
		else \
			INDEX=$$((INDEX_STR)); \
			POD=$$(eval "echo \$$$$(($$INDEX + 1))"); \
			if [ -z "$$POD" ]; then \
				echo "❌ No pod at index $$INDEX for app=$$APP_NAME"; \
			else \
				echo "📜 Events for pod $$POD (index $$INDEX):"; \
				kubectl get events -n $$NAMESPACE --field-selector involvedObject.name=$$POD --sort-by='.lastTimestamp'; \
			fi; \
		fi; \
	fi


k8s-pods:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "📦 Listing pods in namespace $$NAMESPACE..."; \
	kubectl get pods -n $$NAMESPACE

k8s-nodes:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "🖥️ Listing nodes in namespace $$NAMESPACE..."; \
	kubectl get nodes

k8s-services:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "🔌 Listing services in namespace $$NAMESPACE..."; \
	kubectl get services -n $$NAMESPACE

k8s-pvcs:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "📦 Listing persistent volumes in namespace $$NAMESPACE..."; \
	kubectl get pv -n $$NAMESPACE

k8s-secrets:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "🔐 Listing secrets in namespace $$NAMESPACE..."; \
	kubectl get secrets -n $$NAMESPACE

k8s-configmaps:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "🧾 Listing configmaps in namespace $$NAMESPACE..."; \
	kubectl get configmaps -n $$NAMESPACE

k8s-drop:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "🗑️ Deleting namespace..."; \
	kubectl delete namespace $$NAMESPACE

k8s:
	@ENV_NAME=$(ENV_NAME); \
	NAMESPACE=$(PROJECT_NAME)-$$ENV_NAME; \
	echo "🌐 Getting Kubernetes resources in namespace $$NAMESPACE..."; \
	kubectl get all -n $$NAMESPACE -o wide; \

help:
	@echo "Available commands:"
	@echo "  make dev                             – start dev environment"
	@echo "  make staging                         – start staging environment"
	@echo "  make prod                            – start prod environment"
	@echo "  make stop env=dev|staging|prod [v=v] – stop environment with optional volumes"
	@echo "  make logs env=dev|staging|prod       – show logs for the specified environment"
	@echo "  make logs-<pod> env=...              – show logs for a specific service"
	@echo "  make migration env=...               – generate new Atlas migration"
	@echo "  make migrate env=...                 – apply Atlas migrations"
	@echo "  make diff env=...                    – show Atlas schema diff"
	@echo "  make migrate-init env=...          – create initial migration hash"
	@echo "  make k8s-describe pod=<name> [env=dev]     – describe pods by service in k8s"
	@echo "  make k8s-logs pod=<name> [env=dev] [tail=100] – stream logs from matching pods"
	@echo "  make k8s-exec pod=<name> [env=dev]         – open shell in first matching pod"
	@echo "  make k8s-restart pod=<name> [env=dev]      – delete pods to trigger restart"
	@echo "  make k8s-rollout pod=<name> [env=dev]      – rollout restart of deployment"
	@echo "  make k8s-prep env=dev|staging|prod   – prepare Kubernetes manifests and secrets"
	@echo "  make k8s-events env=dev|staging|prod – fetch events from the specified Kubernetes namespace"
	@echo "  make k8s-pods env=dev|staging|prod   – list pods in the specified Kubernetes namespace"
	@echo "  make k8s-nodes env=dev|staging|prod  – list nodes in the specified Kubernetes namespace"
	@echo "  make k8s-services env=dev|staging|prod – list services in the specified Kubernetes namespace"
	@echo "  make k8s-pvcs env=dev|staging|prod   – list persistent volumes in the specified Kubernetes namespace"
	@echo "  make k8s-secrets env=dev|staging|prod – list secrets in the specified Kubernetes namespace"
	@echo "  make k8s-configmaps env=dev|staging|prod – list configmaps in the specified Kubernetes namespace"
	@echo "  make k8s env=dev|staging|prod        – get all Kubernetes resources in the specified namespace"
	@echo "  make grpc-generate                     – generate gRPC Python code from proto file"
	@echo "  make test-inference                    – test inference service functionality"

