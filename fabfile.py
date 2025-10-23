#!/usr/bin/env python3
import logging
import os
from pathlib import Path

from fabric import Connection
from invoke import Responder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

"""""" """""" """""" """""" """""" """""" """""" """""" """""" """""" """"""
"""""" """""" """""" """"" CONFIGURATIONS """ """""" """""" """""" """"""
"""""" """""" """""" """""" """""" """""" """""" """""" """""" """""" """"""
GIT_URL = os.getenv("GIT_URL", "")
GIT_TOKEN = os.getenv("GIT_TOKEN", "")
GIT_USER = os.getenv("GIT_USER", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
DEPLOYMENT = os.getenv("DEPLOYMENT", "make")
REMOTE_USER = os.getenv("REMOTE_USER", "root")
REMOTE_HOST = os.getenv("REMOTE_HOST", "127.0.0.1")
REMOTE_DIR = (
    os.getenv("REMOTE_DIR", f"/{REMOTE_USER}") or f"/home/{REMOTE_USER}"
)
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
REMOTE_PASSWORD = os.getenv("REMOTE_PASSWORD")

prefix = f"https://{GIT_USER}:{GIT_TOKEN}@"
suffix = GIT_URL.split("https://")[-1]
AUTH_GIT_URL = prefix + suffix

PROJECT_NAME = GIT_URL.split("/")[-1].split(".")[0]
GIT_DIR = os.path.join(REMOTE_DIR, PROJECT_NAME)
GIT_SUBDIR = os.path.join(GIT_DIR, "")
COMPOSE_BAKE = os.getenv("COMPOSE_BAKE", "true")
REGISTRY_TYPE = os.getenv("REGISTRY_TYPE", "ghcr")

"""""" """""" """""" """""" """""" """""" """""" """""" """""" """""" """"""


def ping_remote_host():
    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    try:
        result = conn.run("hostname", hide=True)
        print(f"Connected to {REMOTE_HOST}, hostname: {result.stdout.strip()}")
    except Exception as e:
        print(f"Failed to connect to {REMOTE_HOST}: {e}")


def push_env_files():
    project_root = Path.cwd()
    project_name = project_root.name
    remote_base = f"/etc/{project_name}/profile"

    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    print(
        f"============== Syncing .env* files to {remote_base} =============="
    )
    conn.run(f"sudo mkdir -p {remote_base}")
    conn.run(f"sudo chown -R $(whoami) {remote_base}")

    for env_file in project_root.rglob("*"):
        if env_file.is_file() and env_file.name.startswith(".env"):
            relative_path = env_file.parent.relative_to(project_root)
            remote_dir = Path(remote_base) / relative_path

            conn.run(f"mkdir -p {remote_dir}")
            print(f"=== Pushing {env_file} to {remote_dir}/{env_file.name}")
            conn.put(str(env_file), remote=f"{remote_dir}/{env_file.name}")

    print("================= Env files pushed successfully =================")


def push_cert_files():
    project_root = Path.cwd()
    project_name = project_root.name
    remote_base = f"/etc/{project_name}/certs"

    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    print(f"============== Syncing cert files to {remote_base} ==============")
    conn.run(f"sudo mkdir -p {remote_base}")
    conn.run(f"sudo chown -R $(whoami) {remote_base}")

    for cert_file in project_root.rglob("*"):
        if cert_file.is_file() and cert_file.suffix in [
            ".crt",
            ".key",
            ".pem",
            ".p12",
        ]:
            relative_path = cert_file.parent.relative_to(project_root)
            remote_dir = Path(remote_base) / relative_path

            conn.run(f"mkdir -p {remote_dir}")
            print(f"=== Pushing {cert_file} to {remote_dir}/{cert_file.name}")
            conn.put(str(cert_file), remote=f"{remote_dir}/{cert_file.name}")

    print("================= Cert files pushed successfully =================")


def pull_cert_files():
    project_root = Path.cwd()
    project_name = project_root.name
    remote_base = f"/etc/{project_name}/certs"

    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    print(
        f"============== Pulling cert files from {remote_base} =============="
    )

def pull_cert_file(remote_cert_path: str, local_path: Path):
    print(f"======= Pulling {remote_cert_path} to {local_path}")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    conn.get(remote=remote_cert_path, local=str(local_path))

# Find all .crt, .key, .pem files recursively
find_command = (
    f"find {remote_base} -type f "
    "\\( "
    "-name '*.crt' "
    "-o -name '*.key' "
    "-o -name '*.pem' "
    "-o -name '*.p12' "
    "\\)"
)

result = conn.run(find_command, hide=True, warn=True)

for line in result.stdout.strip().splitlines():
    remote_path = Path(line.strip())
    relative_path = remote_path.relative_to(remote_base)
    local_path = project_root / relative_path
    pull_cert_file(str(remote_path), local_path)

print("================= Cert files pulled successfully =================")


def pull_env_files():
    project_root = Path.cwd()
    project_name = project_root.name
    remote_base = f"/etc/{project_name}/profile"

    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    print(
        f"============== Pulling env files from {remote_base} =============="
    )

def pull_env_file(remote_env_path: str, local_path: Path):
    print(f"======= Pulling {remote_env_path} to {local_path}")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    conn.get(remote=remote_env_path, local=str(local_path))

# Find all files named .env or starting with .env. recursively on remote
find_command = f"find {remote_base} -type f -name '.env*' "

result = conn.run(find_command, hide=True, warn=True)

for line in result.stdout.strip().splitlines():
    remote_path = Path(line.strip())
    relative_path = remote_path.relative_to(remote_base)
    local_path = project_root / relative_path
    pull_env_file(str(remote_path), local_path)

print("================= Env files pulled successfully =================")


def install_dependencies(conn):
    deps = [
        "git",
        "python3-pip",
        "python3-dev",
        "build-essential",
        "libssl-dev",
        "libffi-dev",
        "make",
    ]
    missing = []
    for dep in deps:
        result = conn.run(f"which {dep}", warn=True, hide=True)
        if not result.stdout.strip():
            missing.append(dep)

    if missing:
        print(f"======= Installing dependencies: {', '.join(missing)} =======")
        conn.run("sudo apt-get update")
        conn.run(f"sudo apt-get install -y {' '.join(missing)}")
        print("======= Dependencies installed =======")
    else:
        print("======= All dependencies already installed =======")

    # Install kubectl
    kubectl_check = conn.run("which kubectl", warn=True, hide=True)
    if kubectl_check.stdout.strip():
        print("======= kubectl already installed =======")
    else:
        print("======= Installing kubectl =======")
        version_result = conn.run(
            "curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt",
            hide=True,
        )
        latest_version = version_result.stdout.strip()

        conn.run(
            f"curl -LO https://storage.googleapis.com/kubernetes-release/release/{latest_version}/bin/linux/amd64/kubectl"
        )
        conn.run("chmod +x ./kubectl")
        conn.run("sudo mv ./kubectl /usr/local/bin/kubectl")
        print("======= kubectl installed =======")

    # Install Helm
    helm_check = conn.run("which helm", warn=True, hide=True)
    if helm_check.stdout.strip():
        print("======= helm already installed =======")
    else:
        print("======= Installing helm =======")
        conn.run(
            "curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
        )
        print("======= helm installed =======")


def append_shell_lines_to_rc(conn):
    lines_to_add = [
        "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml",
        "",
        "make_with_env() {",
        '\tlocal env="$1"',
        "\tshift",
        '\tENV="$env" make "$@"',
        "}",
        "",
        'prod() { make_with_env prod "$@"; }',
        'staging() { make_with_env staging "$@"; }',
        'dev() { make_with_env dev "$@"; }',
        "",
    ]

    detect_shell_cmd = "echo $SHELL || getent passwd $(whoami) | cut -d: -f7"
    shell_path = conn.run(
        detect_shell_cmd, hide=True, warn=True
    ).stdout.strip()

    if not shell_path:
        print("⚠️ Could not detect user shell, falling back to ~/.profile")
        rc_file = "~/.profile"
    else:
        shell_name = shell_path.split("/")[-1].lower()
        if shell_name == "bash":
            rc_file = "~/.bashrc"
        elif shell_name == "zsh":
            rc_file = "~/.zshrc"
        else:
            print(
                f"⚠️ Detected shell '{shell_name}' is not explicitly "
                f"supported, falling back to ~/.profile"
            )
            rc_file = "~/.profile"

    for line in lines_to_add:
        # Escape single quotes for safe grep and echo usage
        escaped_line = line.replace("'", "'\"'\"'")
        check_cmd = (
            f"grep -Fxq '{escaped_line}' {rc_file} || "
            f"echo '{line}' >> {rc_file}"
        )
        result = conn.run(check_cmd, warn=True)
        if result.failed:
            print(f"⚠️ Warning: Failed to append line to {rc_file}: {line}")

    print(f"✅ Appended lines to {rc_file} if not already present.")


def install_docker(conn):
    result = conn.run("which docker", warn=True, hide=True)
    if result.stdout.strip():
        print("======= Docker already installed =======")
        return

    INSTALL = "sudo apt-get install -y"
    UPDATE = "sudo apt-get update"

    conn.run(f"{UPDATE}")
    conn.run(
        f"{INSTALL} apt-transport-https ca-certificates curl "
        f"software-properties-common"
    )

    conn.run(
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | "
        "sudo apt-key add -"
    )
    conn.run(
        'sudo add-apt-repository "deb [arch=amd64] '
        'https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"'
    )
    conn.run(f"{UPDATE}")
    conn.run(f"{INSTALL} docker-ce")

    conn.run(
        "sudo curl -L "
        '"https://github.com/docker/compose/releases/download/1.29.2/'
        'docker-compose-$(uname -s)-$(uname -m)" '
        "-o /usr/local/bin/docker-compose"
    )
    conn.run("sudo chmod +x /usr/local/bin/docker-compose")
    conn.run("sudo usermod -aG docker ${USER}")
    conn.run("sudo systemctl enable docker")
    conn.run("sudo systemctl start docker")
    print("======= Docker installed =======")


def install_k3s(conn):
    result = conn.run("which k3s", warn=True, hide=True)
    if result.stdout.strip():
        print("======= k3s already installed =======")
        return

    print("======= Installing k3s =======")
    conn.run(
        'curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -',
        pty=True,
    )
    conn.run("sudo systemctl enable k3s")
    conn.run("sudo systemctl start k3s")
    conn.run("echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc")

    version_result = conn.run("k3s --version", hide=True)
    print(f"Installed k3s version: {version_result.stdout.strip()}")
    print("======= k3s installed =======")


def clone_repo(conn):
    promptpass = Responder(
        pattern=r"Are you sure you want to continue connecting "
        r"\(yes/no/\[fingerprint\]\)\?",
        response="yes\n",
    )

    result = conn.run(
        f'test -d {GIT_DIR} && echo "exists" || echo "not exists"',
        hide=True,
    )

    if "not exists" in result.stdout:
        print("======= Cloning the repository =======")
        conn.run(f"git clone {AUTH_GIT_URL}", pty=True, watchers=[promptpass])

    conn.run(f"git config --global --add safe.directory {GIT_DIR}")
    conn.run(f"sudo chown -R $(whoami) {GIT_DIR}")

    with conn.cd(GIT_SUBDIR):
        if ENVIRONMENT in ["prod", "production"]:
            result = conn.run("git branch -r", hide=True)
            remote_branches = [
                line.strip() for line in result.stdout.strip().splitlines()
            ]

            print(f"=== Remote branches: {remote_branches} ===")

            if "origin/main" in remote_branches:
                branch_name = "main"
            elif "origin/master" in remote_branches:
                branch_name = "master"
            else:
                raise Exception(
                    "Neither 'origin/main' nor 'origin/master' found in repo"
                )
        else:
            branch_name = ENVIRONMENT

        current_branch = conn.run(
            "git rev-parse --abbrev-ref HEAD", hide=True
        ).stdout.strip()
        print(f"=== Current branch: {current_branch} ==")

        if current_branch != branch_name:
            print(f"=== Stashing changes on branch {current_branch} ===")
            conn.run("git stash", warn=True)
            print(f"Switching to branch {branch_name}...")
            conn.run(f"git checkout {branch_name}")

        conn.run(f"git fetch origin && git reset --hard origin/{branch_name}")

    print(
        f"=== Repository cloned & checked out to {branch_name} branch ======="
    )


def copy_env_files(conn):
    project_name = PROJECT_NAME
    remote_base = f"/etc/{project_name}/profile"

    print(f"=====Copying env files from {remote_base} to {GIT_SUBDIR} =======")

    result = conn.run(
        f"find {remote_base} -type f -name '*.env.*'",
        hide=True,
    )
    env_files = result.stdout.strip().splitlines()

    for env_file in env_files:
        remote_path = Path(env_file)
        relative_path = remote_path.relative_to(remote_base)

        # local target path: GIT_SUBDIR / relative_path
        local_target_path = Path(GIT_SUBDIR) / relative_path

        print(f"Copying {env_file} → {local_target_path}")

        conn.run(f"mkdir -p {local_target_path.parent}")
        conn.run(f"cp {env_file} {local_target_path}")

    print("======= Env files copied successfully =======")


def copy_cert_files(conn):
    project_name = PROJECT_NAME
    remote_base = f"/etc/{project_name}/certs"

    print(
        f"=====Copying cert files from {remote_base} to {GIT_SUBDIR} ======="
    )

    result = conn.run(
        f"find {remote_base} -type f \\( -name '*.crt' -o -name '*.key' "
        f"-o -name '*.pem' -o -name '*.p12' \\)",
        hide=True,
    )
    cert_files = result.stdout.strip().splitlines()

    for cert_file in cert_files:
        remote_path = Path(cert_file)
        relative_path = remote_path.relative_to(remote_base)

        local_target_path = Path(GIT_SUBDIR) / relative_path

        print(f"Copying {cert_file} → {local_target_path}")

        conn.run(f"mkdir -p {local_target_path.parent}")
        conn.run(f"cp {cert_file} {local_target_path}")

    print("======= Cert files copied successfully =======")


def docker_login(conn, registry_type=None):
    if not registry_type:
        print("No registry type provided, skipping Docker login.")
        return

    registry_type = registry_type.lower()

    if registry_type == "ghcr":
        username = GIT_USER
        password = GIT_TOKEN
        if not username or not password:
            raise ValueError(
                "REGISTRY_USERNAME and REGISTRY_PASSWORD must be set"
            )
        print("Logging in to GHCR...")
        conn.run(
            f"echo '{password}' | docker login ghcr.io -u {username} --password-stdin"
        )

    elif registry_type == "dockerhub":
        username = os.getenv("REGISTRY_USERNAME")
        password = os.getenv("REGISTRY_PASSWORD")
        if not username or not password:
            raise ValueError(
                "REGISTRY_USERNAME and REGISTRY_PASSWORD must be set"
            )
        print("Logging in to Docker Hub...")
        conn.run(
            f"echo '{password}' | docker login -u {username} --password-stdin"
        )

    elif registry_type == "ecr":
        aws_region = os.getenv("AWS_REGION")
        aws_account_id = os.getenv("AWS_ACCOUNT_ID")
        if not aws_region or not aws_account_id:
            raise ValueError(
                "AWS_REGION and AWS_ACCOUNT_ID must be set for ECR login."
            )
        print("Logging in to AWS ECR...")
        cmd = (
            f"aws ecr get-login-password --region {aws_region} | "
            f"docker login --username AWS --password-stdin {aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com"
        )
        conn.run(cmd)

    else:
        raise ValueError(f"Unsupported registry_type: {registry_type}")


def deploy(conn, profile=None):
    with conn.cd(GIT_SUBDIR):
        docker_login(conn, registry_type=REGISTRY_TYPE)

        if DEPLOYMENT == "make":
            if ENVIRONMENT in ("prod"):
                print("======= Deploying with kubernetes  =======")
                conn.run(
                    f"""
                    sudo bash -c '
                        export KUBECONFIG=/etc/rancher/k3s/k3s.yaml &&
                        export ENV={ENVIRONMENT} &&
                        export REGISTRY_TYPE={REGISTRY_TYPE} &&
                        export GITHUB_USERNAME={GIT_USER} &&
                        export GITHUB_TOKEN={GIT_TOKEN} &&
                        export GITHUB_EMAIL={GIT_USER}.gmail.com &&
                        make k8s-prep &&
                        make k8s-apply
                    '
                    """
                )

            else:
                conn.run(f"sudo make {ENVIRONMENT}")
        elif DEPLOYMENT == "profile":
            if profile:
                conn.run(
                    f"sudo docker compose --profile {profile} up --build -d"
                )
            else:
                conn.run("sudo docker compose up --build -d")
            conn.run("sudo docker image prune -f")
        else:
            conn.run("sudo docker compose up --build -d")

    print("======= Application deployed =======")


def handle_connection():
    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    result = conn.run("hostname", hide=True)
    print(
        f"======= Connected to {conn_kwargs.get('host')}, "
        f"hostname: {result.stdout.strip()} ======="
    )
    install_dependencies(conn)
    append_shell_lines_to_rc(conn)
    install_docker(conn)
    install_k3s(conn)
    clone_repo(conn)
    copy_env_files(conn)
    copy_cert_files(conn)
    deploy(conn, profile="prod")


if __name__ == "__main__":
    import sys

    if "push-env" in sys.argv:
        push_env_files()
    elif "push-cert" in sys.argv:
        push_cert_files()
    elif "pull-env" in sys.argv:
        pull_env_files()
    elif "pull-cert" in sys.argv:
        pull_cert_files()
    elif "ping" in sys.argv:
        ping_remote_host()
    else:
        handle_connection()
