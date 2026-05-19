#!/usr/bin/env bash

set -euo pipefail

PACKAGE_REF="${CODEXPP_WRAPPER_PIP_SPEC:-https://github.com/duanluan/codex-plus-plus-launcher/archive/refs/heads/main.zip}"
USE_UV=0
GITHUB_MIRROR_PREFIXES=(
  "https://gh-proxy.com/"
  "https://ghproxy.net/"
  "https://ghfast.top/"
  "https://fastgit.cc/"
)

language() {
  local raw="${CODEXPP_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}"
  case "${raw%%.*}" in
    zh*|ZH*)
      printf 'zh'
      ;;
    *)
      printf 'en'
      ;;
  esac
}

text() {
  local lang
  lang="$(language)"
  case "${lang}:$1" in
    zh:using_uv) printf '使用 uv tool install' ;;
    zh:using_pip) printf '使用 pip install' ;;
    zh:installed_try) printf '安装完成，下一步：cxpp install-app' ;;
    zh:missing_python) printf '缺少命令：python3 或 python' ;;
    zh:missing_installer) printf '缺少安装器：pip' ;;
    zh:uv_requires_opt_in) printf 'uv 安装默认关闭，请显式传入 --use-uv' ;;
    zh:retrying_mirror) printf '直连失败，正在尝试 GitHub 镜像' ;;
    zh:retrying_force_reinstall) printf '检测到损坏的 pip 安装记录，正在尝试跳过卸载直接覆盖安装' ;;
    en:using_uv) printf 'using uv tool install' ;;
    en:using_pip) printf 'using pip install' ;;
    en:installed_try) printf 'installed successfully, next: cxpp install-app' ;;
    en:missing_python) printf 'missing command: python3 or python' ;;
    en:missing_installer) printf 'missing installer: pip' ;;
    en:uv_requires_opt_in) printf 'uv install is disabled by default; pass --use-uv explicitly' ;;
    en:retrying_mirror) printf 'direct GitHub download failed, retrying with mirrors' ;;
    en:retrying_force_reinstall) printf 'detected a broken pip installation record, retrying without uninstall' ;;
  esac
}

log() {
  printf '%s\n' "$*"
}

ensure_python() {
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
    return
  fi
  log "$(text missing_python)"
  exit 1
}

is_github_spec() {
  [[ "$1" == https://github.com/* || "$1" == https://raw.githubusercontent.com/* ]]
}

should_retry_with_mirror() {
  local output="$1"
  local lowered
  lowered="$(printf '%s' "$output" | tr '[:upper:]' '[:lower:]')"
  [[ "$lowered" == *"github.com"* ]] || [[ "$lowered" == *"raw.githubusercontent.com"* ]] || [[ "$lowered" == *"read timed out"* ]] || [[ "$lowered" == *"connect timeout"* ]] || [[ "$lowered" == *"max retries exceeded"* ]] || [[ "$lowered" == *"failed to establish a new connection"* ]] || [[ "$lowered" == *"temporarily unavailable"* ]] || [[ "$lowered" == *"connection reset"* ]]
}

should_force_reinstall() {
  local output="$1"
  local lowered
  lowered="$(printf '%s' "$output" | tr '[:upper:]' '[:lower:]')"
  [[ "$lowered" == *"uninstall-no-record-file"* ]] || [[ "$lowered" == *"no record file was found"* ]]
}

pip_install_once() {
  local candidate="$1"
  shift
  "${PYTHON_BIN}" -m pip install "$@" "${candidate}" 2>&1
}

pip_install_with_fallback() {
  local -a candidates
  local candidate
  local output

  candidates=("${PACKAGE_REF}")
  if [[ "${CODEXPP_DISABLE_GITHUB_MIRROR:-0}" != "1" ]] && is_github_spec "${PACKAGE_REF}"; then
    for prefix in "${GITHUB_MIRROR_PREFIXES[@]}"; do
      candidates+=("${prefix}${PACKAGE_REF}")
    done
  fi

  for ((i=0; i<${#candidates[@]}; i++)); do
    candidate="${candidates[$i]}"
    set +e
    output="$(pip_install_once "${candidate}" --upgrade)"
    status=$?
    set -e
    printf '%s\n' "$output"
    if [[ $status -ne 0 ]] && should_force_reinstall "$output"; then
      log "$(text retrying_force_reinstall)"
      set +e
      output="$(pip_install_once "${candidate}" --ignore-installed --no-deps)"
      status=$?
      set -e
      printf '%s\n' "$output"
    fi
    if [[ $status -eq 0 ]]; then
      return 0
    fi
    if [[ $i -lt $((${#candidates[@]} - 1)) ]] && should_retry_with_mirror "$output"; then
      log "$(text retrying_mirror)"
      continue
    fi
    return $status
  done
}

main() {
  if [[ "${1:-}" == "--use-uv" ]]; then
    USE_UV=1
    shift
  fi

  ensure_python
  if "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
    log "$(text using_pip)"
    pip_install_with_fallback
    log "$(text installed_try)"
    exit 0
  fi

  if [[ "${USE_UV}" == "1" ]] && command -v uv >/dev/null 2>&1; then
    log "$(text using_uv)"
    uv tool install --refresh "${PACKAGE_REF}"
    log "$(text installed_try)"
    exit 0
  fi

  if [[ "${USE_UV}" != "1" ]] && command -v uv >/dev/null 2>&1; then
    log "$(text uv_requires_opt_in)"
    exit 1
  fi

  log "$(text missing_installer)"
  exit 1
}

main "$@"
