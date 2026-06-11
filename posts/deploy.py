import logging
import os
import shutil
import tempfile

from django.conf import settings

logger = logging.getLogger(__name__)


def deploy_to_gh_pages(site_dir):
    deploy_key = settings.GITHUB_DEPLOY_KEY
    if not deploy_key:
        logger.warning("GITHUB_DEPLOY_KEY not configured, skipping deploy")
        return False

    repo_url = settings.GITHUB_REPO_URL
    tmpdir = tempfile.mkdtemp(prefix="comitatus_deploy_")

    ssh_key_path = os.path.join(tmpdir, "deploy_key")
    with open(ssh_key_path, "w") as f:
        f.write(deploy_key)
    os.chmod(ssh_key_path, 0o600)

    ssh_cmd = f"ssh -i {ssh_key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

    try:
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = ssh_cmd
        env["GIT_DIR"] = os.path.join(tmpdir, "repo", ".git")
        env["GIT_WORK_TREE"] = os.path.join(tmpdir, "repo")

        repo_dir = os.path.join(tmpdir, "repo")
        os.makedirs(repo_dir, exist_ok=True)

        import subprocess

        subprocess.run(
            ["git", "init"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", repo_url],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "fetch", "origin", "gh-pages"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
        )
        try:
            subprocess.run(
                ["git", "checkout", "gh-pages"],
                cwd=repo_dir,
                env=env,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            subprocess.run(
                ["git", "checkout", "--orphan", "gh-pages"],
                cwd=repo_dir,
                env=env,
                capture_output=True,
                check=True,
            )

        existing = set(os.listdir(repo_dir))
        existing.discard(".git")
        for item in existing:
            item_path = os.path.join(repo_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

        for item in os.listdir(site_dir):
            src = os.path.join(site_dir, item)
            dst = os.path.join(repo_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)

        with open(os.path.join(repo_dir, ".nojekyll"), "w") as f:
            f.write("")

        subprocess.run(
            ["git", "add", "--all"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            check=True,
        )

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
        )
        if result.returncode == 0:
            logger.info("No changes to deploy")
            shutil.rmtree(tmpdir)
            return True

        subprocess.run(
            ["git", "commit", "-m", "Deploy updated site [automated]"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            check=True,
        )

        subprocess.run(
            ["git", "push", "origin", "gh-pages"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            check=True,
        )

        logger.info("Deployed to gh-pages successfully")
        shutil.rmtree(tmpdir)
        return True

    except Exception as e:
        logger.error("Deploy failed: %s", e)
        shutil.rmtree(tmpdir)
        return False
