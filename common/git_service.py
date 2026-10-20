"""配置目录的 Git 版本管理（提交、推送、历史、回退）。"""
import os
import shutil
import subprocess
from dataclasses import dataclass, field

from common.paths import APP_ROOT

GIT_TIMEOUT = 120
NETWORK_TIMEOUT = 90
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CONFIG_PATHSPEC = "config"


class GitError(RuntimeError):
    pass


@dataclass
class ConfigStatus:
    branch: str = ""
    changes: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    has_upstream: bool = False
    remote: str = ""


@dataclass
class GitCommit:
    short_hash: str
    full_hash: str
    date: str
    author: str
    subject: str


def _git(args: list[str], timeout: int = GIT_TIMEOUT, check: bool = True) -> subprocess.CompletedProcess:
    if shutil.which("git") is None:
        raise GitError("未找到 git 命令，请确认已安装 Git 并加入 PATH。")

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_PAGER"] = "cat"

    command = ["git", "-c", "core.quotepath=false", *args]
    try:
        result = subprocess.run(
            command,
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise GitError("未找到 git 命令，请确认已安装 Git 并加入 PATH。") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git 操作超时，请检查网络或凭据设置。") from exc

    if check and result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise GitError(message or f"git {' '.join(args)} 执行失败")
    return result


def is_repo() -> bool:
    try:
        result = _git(["rev-parse", "--is-inside-work-tree"], check=False)
    except GitError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def status() -> ConfigStatus:
    branch_result = _git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""

    status_result = _git(["status", "--porcelain=v1", "--", CONFIG_PATHSPEC])
    changes = [line for line in status_result.stdout.splitlines() if line.strip()]

    upstream = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False)
    has_upstream = upstream.returncode == 0 and bool(upstream.stdout.strip())

    ahead = behind = 0
    if has_upstream:
        counts = _git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], check=False).stdout.split()
        if len(counts) == 2:
            try:
                behind, ahead = int(counts[0]), int(counts[1])
            except ValueError:
                ahead = behind = 0

    remote_result = _git(["remote", "get-url", "origin"], check=False)
    remote = remote_result.stdout.strip() if remote_result.returncode == 0 else ""

    return ConfigStatus(
        branch=branch,
        changes=changes,
        ahead=ahead,
        behind=behind,
        has_upstream=has_upstream,
        remote=remote,
    )


def log_config(limit: int = 50) -> list[GitCommit]:
    pretty = "%h%x1f%H%x1f%ad%x1f%an%x1f%s"
    result = _git(
        [
            "log",
            f"-n{limit}",
            "--date=format:%Y-%m-%d %H:%M",
            f"--pretty=format:{pretty}",
            "--",
            CONFIG_PATHSPEC,
        ],
        check=False,
    )
    if result.returncode != 0:
        return []

    commits: list[GitCommit] = []
    for line in result.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) < 5:
            continue
        commits.append(
            GitCommit(
                short_hash=parts[0],
                full_hash=parts[1],
                date=parts[2],
                author=parts[3],
                subject=parts[4],
            )
        )
    return commits


def _has_upstream() -> bool:
    result = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def _push() -> bool:
    if not _has_upstream():
        return False
    _git(["push"], timeout=NETWORK_TIMEOUT)
    return True


def commit_and_push(message: str) -> str:
    message = message.strip()
    if not message:
        raise GitError("提交说明不能为空。")
    if not is_repo():
        raise GitError("当前目录不是 Git 仓库，无法上传配置。")

    if not status().changes:
        return "没有需要上传的配置改动。"

    _git(["add", "-A", "--", CONFIG_PATHSPEC])
    staged = [line for line in _git(["diff", "--cached", "--name-only", "--", CONFIG_PATHSPEC]).stdout.splitlines() if line.strip()]
    if not staged:
        return "没有需要上传的配置改动。"

    _git(["commit", "-m", message])

    try:
        pushed = _push()
    except GitError as exc:
        raise GitError(f"配置已提交到本地，但推送失败：{exc}") from exc

    if pushed:
        return f"已提交并推送 {len(staged)} 个配置文件。"
    return f"已提交 {len(staged)} 个配置文件（当前分支未设置远程跟踪分支，未推送）。"


def rollback_to(commit_hash: str) -> str:
    if not commit_hash:
        raise GitError("未选择要回退的版本。")
    if not is_repo():
        raise GitError("当前目录不是 Git 仓库，无法回退配置。")

    verify = _git(["cat-file", "-e", f"{commit_hash}^{{commit}}"], check=False)
    if verify.returncode != 0:
        raise GitError("找不到指定的提交，可能已被清理。")

    subject_result = _git(["log", "-1", "--pretty=format:%s", commit_hash], check=False)
    subject = subject_result.stdout.strip()
    short = commit_hash[:7]

    _git(["checkout", commit_hash, "--", CONFIG_PATHSPEC])

    target_files = {
        line
        for line in _git(["ls-tree", "-r", "--name-only", commit_hash, "--", CONFIG_PATHSPEC]).stdout.splitlines()
        if line.strip()
    }
    current_files = {
        line for line in _git(["ls-files", "--", CONFIG_PATHSPEC]).stdout.splitlines() if line.strip()
    }
    extra_files = sorted(current_files - target_files)
    if extra_files:
        _git(["rm", "-f", "--", *extra_files])

    pending = [line for line in _git(["status", "--porcelain", "--", CONFIG_PATHSPEC]).stdout.splitlines() if line.strip()]
    if not pending:
        return f"配置已经与版本 {short} 一致，无需回退。"

    message = f"回滚配置到 {short}：{subject}" if subject else f"回滚配置到 {short}"
    _git(["commit", "-m", message])

    try:
        pushed = _push()
    except GitError as exc:
        raise GitError(f"配置已回退并提交到本地，但推送失败：{exc}") from exc

    if pushed:
        return f"已回退到版本 {short} 并推送成功。"
    return f"已回退到版本 {short}（已提交到本地，未推送）。"


def discard_changes() -> str:
    if not is_repo():
        raise GitError("当前目录不是 Git 仓库。")

    head = _git(["rev-parse", "--verify", "HEAD"], check=False)
    if head.returncode != 0:
        raise GitError("仓库还没有任何提交，无法撤销修改。")

    _git(["checkout", "HEAD", "--", CONFIG_PATHSPEC])
    return "已撤销 config 目录中未提交的修改（未跟踪的新文件不受影响）。"


def pull_latest() -> str:
    if not is_repo():
        raise GitError("当前目录不是 Git 仓库。")
    if not _has_upstream():
        raise GitError("当前分支没有远程跟踪分支，无法拉取。")

    _git(["pull", "--ff-only"], timeout=NETWORK_TIMEOUT)
    return "已拉取仓库最新内容。"
