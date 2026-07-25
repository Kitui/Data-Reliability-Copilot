import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase_6_delivery_files_exist():
    expected = [
        ROOT / "Dockerfile",
        ROOT / ".dockerignore",
        ROOT / "requirements-dev.txt",
        ROOT / "pyproject.toml",
        ROOT / "package.json",
        ROOT / "playwright.config.js",
        ROOT / ".github/workflows/ci.yml",
        ROOT / ".github/workflows/e2e.yml",
        ROOT / ".github/workflows/deploy.yml",
        ROOT / "tests/e2e/core-workflow.spec.js",
    ]
    assert all(path.exists() for path in expected)


def test_package_scripts_expose_playwright():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test:e2e"] == "playwright test"
    assert "@playwright/test" in package["devDependencies"]


def test_ci_validates_migrations_tests_security_and_container():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for marker in ("alembic upgrade head", "coverage run -m pytest", "pip-audit", "bandit", "docker/build-push-action"):
        assert marker in workflow


def test_deployment_uses_immutable_sha_and_controlled_migrations():
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "${GITHUB_SHA}" in workflow
    assert "jobs execute" in workflow
    assert "--no-traffic" in workflow
