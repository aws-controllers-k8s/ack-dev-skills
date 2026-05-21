#!/usr/bin/env bash
set -euo pipefail

# Ensures a controller repo (and code-generator) are cloned, forked, and up-to-date.
# Usage: ensure-repo.sh <controller-name> [github-user] [workspace-path]
# Example: ensure-repo.sh ec2-controller

CONTROLLER="$1"
GH_USER="${2:-$(gh api user --jq .login)}"
WORKSPACE="${3:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
ORG="aws-controllers-k8s"

ensure_repo() {
  local repo="$1"
  local repo_path="${WORKSPACE}/${repo}"

  if [[ -d "${repo_path}" ]]; then
    echo "${repo}: exists at ${repo_path}"

    cd "${repo_path}"

    local current_branch
    current_branch=$(git branch --show-current)

    if [[ -n $(git status --porcelain) ]]; then
      echo "${repo}: stashing uncommitted changes on ${current_branch}"
      git stash push --include-untracked -m "resolve-issue: auto-stash before pull"
    fi

    if [[ "${current_branch}" != "main" ]]; then
      echo "${repo}: switching from ${current_branch} to main"
      git checkout main
    fi

    echo "${repo}: pulling latest upstream"
    git pull upstream main --rebase=true --tags

    echo "${repo}: status=ready"
    return 0
  fi

  echo "${repo}: cloning ${ORG}/${repo}..."
  gh repo clone "${ORG}/${repo}" "${repo_path}"

  cd "${repo_path}"
  git remote rename origin upstream

  if gh repo view "${GH_USER}/${repo}" &>/dev/null; then
    echo "${repo}: fork already exists at ${GH_USER}/${repo}"
  else
    echo "${repo}: forking ${ORG}/${repo} to ${GH_USER}..."
    gh repo fork "${ORG}/${repo}" --clone=false
  fi

  git remote add origin "https://github.com/${GH_USER}/${repo}.git"
  echo "${repo}: status=cloned"
}

ensure_repo "${CONTROLLER}"
ensure_repo "code-generator"
