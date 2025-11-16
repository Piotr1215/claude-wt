# Architecture Improvement Plan for claude-wt

**Date**: 2025-01-16
**Current Version**: ~2000 LOC Python CLI tool
**Goal**: Make claude-wt more robust, resilient, and maintainable using Hexagonal Architecture + Dependency Injection

---

## Executive Summary

The `claude-wt` CLI tool currently suffers from several architectural brittleness points that make it fragile, hard to test, and difficult to extend. This document provides a comprehensive plan to refactor the codebase using **Hexagonal Architecture** (Ports & Adapters) with **manual Dependency Injection**, improving resilience through retry patterns, circuit breakers, and Result types.

**Key Findings**:
- ❌ **Direct subprocess calls scattered throughout** - no abstraction, hard to test
- ❌ **Silent failures masking issues** - `except: pass` blocks hide errors
- ❌ **No retry logic for transient failures** - network operations fail unnecessarily
- ❌ **Mixed concerns** - CLI, business logic, and infrastructure intertwined
- ❌ **Inconsistent error handling** - mix of exceptions, SystemExit, and None returns
- ❌ **Tight coupling** - modules depend directly on each other
- ❌ **No validation layer** - validation logic duplicated and scattered

**Recommended Approach**:
- ✅ **Hexagonal Architecture** - Clear separation of domain, application, and infrastructure
- ✅ **Manual Dependency Injection** - Lightweight, no framework needed
- ✅ **Resilience patterns** - Retry with exponential backoff, circuit breakers
- ✅ **Result types for validation** - Explicit error handling in type system
- ✅ **Adapters for external systems** - Git, Tmux, GitHub CLI, filesystem

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Brittleness Points Identified](#brittleness-points-identified)
3. [Proposed Architecture](#proposed-architecture)
4. [Migration Strategy](#migration-strategy)
5. [Detailed Refactoring Plan](#detailed-refactoring-plan)
6. [Code Examples](#code-examples)
7. [Testing Strategy](#testing-strategy)
8. [Benefits and Trade-offs](#benefits-and-trade-offs)
9. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Current Architecture Analysis

### 1.1 Current Structure

```
claude_wt/
├── cli.py              # CLI entry point (Cyclopts app)
├── core.py             # Shared utilities
├── worktree.py         # Worktree operations (main logic)
├── repository.py       # Path resolution
├── identifier.py       # ID detection (Linear, PR)
├── github.py           # GitHub PR integration
├── linear.py           # Linear issue integration
├── session.py          # Session name generation
├── tmux.py             # Tmux session management
└── tmux_launcher.py    # Tmux/Claude launcher
```

### 1.2 Current Dependencies Flow

```
┌──────────────────────────────────────────────────────┐
│                     cli.py                           │
│  (Cyclopts commands, console output)                 │
└─────────┬────────────────────────────────────────────┘
          │
          ├──────> worktree.py ──┬──> core.py
          │                      ├──> tmux.py
          │                      └──> subprocess (direct)
          │
          ├──────> github.py ────┬──> core.py
          │                      ├──> repository.py
          │                      ├──> tmux_launcher.py
          │                      └──> subprocess (direct)
          │
          └──────> linear.py ────┬──> core.py
                                 ├──> session.py
                                 └──> subprocess (direct)
```

**Problems**:
- 🔴 **Circular dependencies**: Multiple modules import each other
- 🔴 **Tight coupling**: Changes ripple across multiple files
- 🔴 **No clear layers**: Business logic mixed with infrastructure
- 🔴 **Hard to test**: Direct subprocess calls, no injection points

---

## 2. Brittleness Points Identified

### 2.1 Critical Issues

#### ❌ Issue #1: Direct Subprocess Calls Everywhere

**Location**: `worktree.py:172-242`, `github.py:87-149`, `linear.py`, `tmux.py`

**Example**:
```python
# worktree.py:176-199 - Direct git calls
subprocess.run(
    ["git", "-C", str(repo_root), "worktree", "add", str(wt_path), branch_name],
    check=True,
    env=env,
)
```

**Problems**:
- Cannot mock for testing without `@patch` decorators
- No retry logic for transient failures
- Timeouts not handled consistently
- Command availability not checked upfront
- Error context lost (just stderr)

**Impact**: **HIGH** - Core functionality is brittle and untestable

---

#### ❌ Issue #2: Silent Failures

**Location**: `core.py:157-160`, `core.py:189-206`, `core.py:231-265`

**Example**:
```python
# core.py:157-160
def install_branch_protection_hook(wt_path: Path, branch_name: str):
    try:
        # ... 40 lines of logic
    except Exception:
        pass  # Silently fail if hook installation doesn't work
```

**Problems**:
- Errors swallowed without logging
- User unaware of partial failures
- Debug mode doesn't reveal issues
- No way to detect problems in production

**Impact**: **MEDIUM** - Features fail silently, users confused

---

#### ❌ Issue #3: No Retry Logic for Network Operations

**Location**: `worktree.py:281-292`, `github.py:101-104`, `github.py:138-149`

**Example**:
```python
# worktree.py:282 - Single attempt, no retry
subprocess.run(["git", "-C", str(repo_root), "fetch", "origin"], check=True)
```

**Problems**:
- Transient network failures cause immediate failure
- No exponential backoff for rate limits
- GitHub CLI calls fail permanently on timeouts
- User forced to manually retry

**Impact**: **HIGH** - Poor user experience, unreliable in CI/CD

---

#### ❌ Issue #4: Mixed Concerns (Layering Violation)

**Location**: `cli.py:28-77`, `worktree.py:245-371`

**Example**:
```python
# cli.py:28-77 - CLI command with business logic
@app.command
def new(query: str = "", branch: str = "", ...):
    # Reading files (infrastructure)
    prompt_path = Path(prompt_file).expanduser()
    final_query = prompt_path.read_text().strip()

    # Calling business logic directly
    create_new_worktree(final_query, branch, name, pull, print_path)

    # Error handling (presentation)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
```

**Problems**:
- CLI commands know about file I/O
- Business logic mixed with presentation
- Cannot reuse logic in different context (API, tests)
- Hard to change one without affecting others

**Impact**: **MEDIUM** - Low reusability, high change cost

---

#### ❌ Issue #5: Inconsistent Error Handling

**Location**: Throughout codebase

**Example**:
```python
# Pattern 1: Raise SystemExit
def clean_worktrees(...):
    if branch_name and all:
        console.print("[red]Error: Cannot specify both[/red]")
        raise SystemExit(1)

# Pattern 2: Return None
def select_worktree_fzf(...) -> dict | None:
    except subprocess.CalledProcessError:
        return None

# Pattern 3: Raise exception
def resolve_repo_path(...) -> Path:
    raise RepositoryResolutionError("Cannot determine path")

# Pattern 4: Silent failure
try:
    # operation
except Exception:
    pass
```

**Problems**:
- No consistent error handling strategy
- Hard to predict behavior
- Cannot compose functions reliably
- Testing requires different approaches per function

**Impact**: **HIGH** - Unpredictable behavior, poor composability

---

#### ❌ Issue #6: No Validation Layer

**Location**: Validation scattered in `cli.py`, `worktree.py`, `identifier.py`

**Example**:
```python
# Validation mixed in business logic
def create_new_worktree(query: str, branch: str, name: str, ...):
    # No upfront validation
    # Errors discovered during execution
    subprocess.run(["git", "branch", branch_name, source_branch], check=True)
    # ^ May fail here if branch_name is invalid
```

**Problems**:
- Validation logic duplicated
- Errors discovered late (after operations started)
- No reusable validation functions
- Cannot validate upfront in API/CLI

**Impact**: **MEDIUM** - Poor user experience, wasted operations

---

#### ❌ Issue #7: Tight Coupling Between Modules

**Location**: `worktree.py` imports everything

**Example**:
```python
# worktree.py imports
from .core import (copy_gitignored_files, create_worktree_context, ...)
from .tmux import create_tmux_session

# Later: worktree.py:370
create_tmux_session(session_name, wt_path, repo_root, query, resume=False)
```

**Problems**:
- Circular dependencies (core ↔ worktree ↔ tmux)
- Cannot use worktree logic without tmux
- Hard to swap implementations
- Changes cascade across modules

**Impact**: **HIGH** - Hard to maintain, difficult to extend

---

#### ❌ Issue #8: No Interfaces/Protocols

**Location**: No Protocol definitions in codebase

**Problems**:
- No contracts for adapters
- Cannot swap git implementation (e.g., for testing)
- No type checking for dependency injection
- Unclear what methods each component needs

**Impact**: **MEDIUM** - Poor testability, no pluggability

---

#### ❌ Issue #9: Configuration Hardcoded

**Location**: `core.py:10-12`, paths scattered throughout

**Example**:
```python
# core.py:10-12
def get_worktree_base(repo_root: Path) -> Path:
    return Path.home() / "dev" / "claude-wt-worktrees"
    # ^ Hardcoded, cannot customize
```

**Problems**:
- Cannot customize paths
- Hard to test with different configurations
- No environment variable support
- Difficult to adapt for different setups

**Impact**: **LOW** - Limited flexibility

---

#### ❌ Issue #10: No Circuit Breakers for External Services

**Location**: GitHub CLI calls, git operations

**Problems**:
- Repeated failures to GitHub API keep retrying
- No protection against cascading failures
- Rate limits not handled gracefully
- Service degradation not detected

**Impact**: **MEDIUM** - Poor resilience to external failures

---

### 2.2 Brittleness Summary Table

| Issue | Severity | Impact | Effort to Fix |
|-------|----------|--------|---------------|
| Direct subprocess calls | 🔴 HIGH | Untestable, brittle | Medium |
| Silent failures | 🟡 MEDIUM | Hidden bugs | Low |
| No retry logic | 🔴 HIGH | Poor reliability | Medium |
| Mixed concerns | 🟡 MEDIUM | Hard to change | High |
| Inconsistent error handling | 🔴 HIGH | Unpredictable | Medium |
| No validation layer | 🟡 MEDIUM | Late errors | Low |
| Tight coupling | 🔴 HIGH | Fragile | High |
| No interfaces | 🟡 MEDIUM | Not pluggable | Medium |
| Hardcoded config | 🟢 LOW | Inflexible | Low |
| No circuit breakers | 🟡 MEDIUM | Poor resilience | Medium |

---

## 3. Proposed Architecture

### 3.1 Hexagonal Architecture (Ports & Adapters)

**Why Hexagonal over Onion?**
- ✅ **Simpler** - Fewer layers, easier to understand
- ✅ **Better for CLI tools** - claude-wt is primarily I/O heavy, not domain-heavy
- ✅ **Flexible** - Easier to add/swap adapters
- ✅ **Practical** - Less boilerplate than Onion for 2000 LOC

**Architecture Diagram**:

```
┌───────────────────────────────────────────────────────────────┐
│                    PRIMARY ADAPTERS                           │
│         (CLI Commands, Future: Web API, TUI)                  │
│                                                               │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────┐       │
│   │ CLI (Cyclopts)│  │ Future: API  │  │ Future: TUI │       │
│   └──────┬────────┘  └──────┬───────┘  └──────┬──────┘       │
└──────────┼──────────────────┼─────────────────┼──────────────┘
           │                  │                 │
           │                  │                 │
┌──────────▼──────────────────▼─────────────────▼──────────────┐
│                    APPLICATION CORE                           │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │               USE CASES (Business Logic)               │  │
│  │                                                        │  │
│  │  • CreateWorktreeUseCase                              │  │
│  │  • SwitchWorktreeUseCase                              │  │
│  │  • CleanWorktreeUseCase                               │  │
│  │  • CreatePRWorktreeUseCase                            │  │
│  │  • MaterializeBranchUseCase                           │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           PORTS (Interfaces/Protocols)                 │  │
│  │                                                        │  │
│  │  • IGitPort          • ITmuxPort                      │  │
│  │  • IFileSystemPort   • IProcessPort                   │  │
│  │  • IGitHubPort       • IConsolePort                   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │             DOMAIN MODELS                              │  │
│  │                                                        │  │
│  │  • Worktree (entity)                                  │  │
│  │  • BranchName (value object)                          │  │
│  │  • WorktreePath (value object)                        │  │
│  │  • SessionName (value object)                         │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬───────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────┐
│                  SECONDARY ADAPTERS                           │
│               (Infrastructure, External Systems)              │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ GitAdapter   │  │ TmuxAdapter  │  │ GitHubAdapter│       │
│  │              │  │              │  │              │       │
│  │ • run git    │  │ • create     │  │ • fetch PR   │       │
│  │ • fetch      │  │   session    │  │ • list PRs   │       │
│  │ • branch     │  │ • switch     │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │FileSystemAdp │  │ProcessAdapter│  │ConsoleAdapter│       │
│  │              │  │              │  │              │       │
│  │ • read       │  │ • run cmd    │  │ • print      │       │
│  │ • write      │  │ • retry      │  │ • prompt     │       │
│  │ • exists     │  │ • timeout    │  │ • format     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘

CROSS-CUTTING CONCERNS:
┌───────────────────────────────────────────────────────────────┐
│ • Retry Logic (tenacity)                                      │
│ • Circuit Breakers (pybreaker)                                │
│ • Result Types (custom or `result` library)                  │
│ • Logging (structlog)                                         │
└───────────────────────────────────────────────────────────────┘
```

### 3.2 Proposed Directory Structure

```
claude_wt/
├── domain/                      # Domain layer (entities, value objects)
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   └── worktree.py         # Worktree entity
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── branch_name.py      # BranchName value object
│   │   ├── worktree_path.py    # WorktreePath value object
│   │   └── session_name.py     # SessionName value object
│   └── exceptions.py           # Domain exceptions
│
├── application/                 # Application layer (use cases, ports)
│   ├── __init__.py
│   ├── ports/                  # Interfaces (Protocols)
│   │   ├── __init__.py
│   │   ├── git_port.py         # IGitPort
│   │   ├── tmux_port.py        # ITmuxPort
│   │   ├── github_port.py      # IGitHubPort
│   │   ├── filesystem_port.py  # IFileSystemPort
│   │   ├── process_port.py     # IProcessPort
│   │   └── console_port.py     # IConsolePort
│   ├── use_cases/
│   │   ├── __init__.py
│   │   ├── create_worktree.py  # CreateWorktreeUseCase
│   │   ├── switch_worktree.py  # SwitchWorktreeUseCase
│   │   ├── clean_worktree.py   # CleanWorktreeUseCase
│   │   ├── list_worktrees.py   # ListWorktreesUseCase
│   │   ├── create_pr_worktree.py
│   │   └── materialize_branch.py
│   ├── dtos/                   # Data Transfer Objects
│   │   ├── __init__.py
│   │   ├── create_worktree_request.py
│   │   └── worktree_response.py
│   └── validation/             # Validation logic
│       ├── __init__.py
│       ├── validators.py       # Reusable validators
│       └── result.py           # Custom Result type
│
├── infrastructure/              # Infrastructure layer (adapters)
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── git_adapter.py      # Git operations (implements IGitPort)
│   │   ├── tmux_adapter.py     # Tmux operations
│   │   ├── github_adapter.py   # GitHub CLI operations
│   │   ├── filesystem_adapter.py
│   │   ├── process_adapter.py  # Subprocess with retry/timeout
│   │   └── console_adapter.py  # Rich console
│   ├── resilience/             # Resilience patterns
│   │   ├── __init__.py
│   │   ├── retry.py            # Retry decorators
│   │   └── circuit_breaker.py  # Circuit breaker setup
│   └── config/
│       ├── __init__.py
│       └── settings.py         # Configuration management
│
├── presentation/                # Presentation layer (CLI)
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── app.py              # Cyclopts app setup
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── new_command.py
│   │   │   ├── switch_command.py
│   │   │   ├── clean_command.py
│   │   │   ├── list_command.py
│   │   │   └── pr_commands.py
│   │   └── formatters/
│   │       ├── __init__.py
│   │       └── output_formatter.py
│   └── di/                     # Dependency Injection
│       ├── __init__.py
│       └── container.py        # DI container (composition root)
│
├── main.py                      # Entry point
├── pyproject.toml
└── README.md
```

### 3.3 Key Architectural Decisions

#### Decision #1: Use Hexagonal Architecture (not Onion)

**Rationale**:
- Claude-wt is I/O heavy, not domain-heavy
- Simpler than Onion (fewer layers)
- Port/Adapter pattern maps naturally to external tools (git, tmux, gh)

#### Decision #2: Manual Dependency Injection (not a framework)

**Rationale**:
- Zero external dependencies
- Full control and transparency
- Sufficient for ~2000 LOC
- Easy to understand and debug
- Can add framework later if needed

#### Decision #3: Custom Result Type (not `returns` library)

**Rationale**:
- Minimal dependencies
- Simple validation use cases
- Don't need advanced monadic features
- Can upgrade to `returns` later if needed

#### Decision #4: Tenacity for Retry, PyBreaker for Circuit Breakers

**Rationale**:
- Industry-standard libraries (actively maintained)
- Minimal API surface
- Well-tested and documented
- Widely used in production

#### Decision #5: Keep Rich for Console, Add Structlog for Logging

**Rationale**:
- Rich already used for output
- Structlog for structured logging (debug mode)
- Both work well together

---

## 4. Migration Strategy

### 4.1 Migration Principles

1. **Incremental refactoring** - No big-bang rewrite
2. **Feature parity** - Maintain all existing functionality
3. **Backward compatibility** - Users shouldn't notice changes
4. **Test-driven** - Add tests before refactoring
5. **Gradual adoption** - New code uses new architecture, old code migrated over time

### 4.2 Migration Phases

#### Phase 1: Foundation (Week 1)
- ✅ Create directory structure
- ✅ Define Port interfaces (Protocols)
- ✅ Implement basic adapters
- ✅ Create Result type
- ✅ Set up DI container

**Deliverables**:
- `/domain/`, `/application/`, `/infrastructure/`, `/presentation/` directories
- All Port interfaces defined
- Basic GitAdapter, FileSystemAdapter

#### Phase 2: Validation & Resilience (Week 1)
- ✅ Extract validation logic
- ✅ Add retry logic with tenacity
- ✅ Add circuit breakers for external services
- ✅ Replace silent failures with logging

**Deliverables**:
- Validators with Result types
- Retry decorators for git/gh operations
- Circuit breaker for GitHub CLI
- Structured logging setup

#### Phase 3: Use Cases (Week 2)
- ✅ Extract CreateWorktreeUseCase
- ✅ Extract SwitchWorktreeUseCase
- ✅ Extract CleanWorktreeUseCase
- ✅ Wire use cases with DI

**Deliverables**:
- 3-5 use cases implemented
- Use cases tested with stubs
- DI container wiring complete

#### Phase 4: Adapters (Week 2)
- ✅ Complete all adapters (Git, Tmux, GitHub, FileSystem)
- ✅ Add comprehensive tests for adapters
- ✅ Implement timeout handling

**Deliverables**:
- All adapters implemented and tested
- Integration tests with real tools

#### Phase 5: CLI Migration (Week 3)
- ✅ Migrate CLI commands to use DI container
- ✅ Update error handling in commands
- ✅ Add validation to CLI input
- ✅ Update documentation

**Deliverables**:
- All CLI commands use new architecture
- User-facing behavior unchanged
- Internal architecture improved

#### Phase 6: Cleanup & Polish (Week 3)
- ✅ Remove old code
- ✅ Update tests
- ✅ Performance testing
- ✅ Documentation updates

**Deliverables**:
- Clean codebase
- Full test coverage
- Updated README

---

## 5. Detailed Refactoring Plan

### 5.1 Port Definitions (Interfaces)

#### `application/ports/git_port.py`

```python
from typing import Protocol, List
from pathlib import Path
from application.validation.result import Result
from domain.value_objects.branch_name import BranchName

class IGitPort(Protocol):
    """Port for git operations."""

    def get_repo_root(self, cwd: Path | None = None) -> Result[Path, str]:
        """Get repository root directory."""
        ...

    def get_current_branch(self, repo_root: Path) -> Result[BranchName, str]:
        """Get current branch name."""
        ...

    def create_branch(
        self,
        repo_root: Path,
        branch_name: BranchName,
        base_branch: BranchName,
    ) -> Result[None, str]:
        """Create a new branch."""
        ...

    def create_worktree(
        self,
        repo_root: Path,
        worktree_path: Path,
        branch_name: BranchName,
    ) -> Result[None, str]:
        """Create a git worktree."""
        ...

    def remove_worktree(
        self,
        repo_root: Path,
        worktree_path: Path,
    ) -> Result[None, str]:
        """Remove a git worktree."""
        ...

    def fetch_remote(
        self,
        repo_root: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> Result[None, str]:
        """Fetch from remote repository."""
        ...

    def list_worktrees(self, repo_root: Path) -> Result[List[dict], str]:
        """List all worktrees."""
        ...
```

#### `application/ports/tmux_port.py`

```python
from typing import Protocol
from pathlib import Path
from application.validation.result import Result

class ITmuxPort(Protocol):
    """Port for tmux operations."""

    def is_available(self) -> bool:
        """Check if tmux is available."""
        ...

    def create_session(
        self,
        session_name: str,
        working_directory: Path,
    ) -> Result[None, str]:
        """Create a new tmux session."""
        ...

    def session_exists(self, session_name: str) -> Result[bool, str]:
        """Check if session exists."""
        ...

    def switch_to_session(self, session_name: str) -> Result[None, str]:
        """Switch to existing session."""
        ...

    def send_keys(
        self,
        session_name: str,
        keys: str,
    ) -> Result[None, str]:
        """Send keys to session."""
        ...
```

#### `application/ports/process_port.py`

```python
from typing import Protocol, List
from pathlib import Path
from application.validation.result import Result

class IProcessPort(Protocol):
    """Port for subprocess operations with resilience."""

    def run(
        self,
        command: List[str],
        cwd: Path | None = None,
        timeout: int = 30,
        check: bool = True,
        retry: bool = False,
    ) -> Result[tuple[str, str], str]:
        """
        Run command with retry and timeout.

        Returns: Result[(stdout, stderr), error]
        """
        ...

    def command_exists(self, command: str) -> bool:
        """Check if command is available."""
        ...
```

### 5.2 Adapter Implementations

#### `infrastructure/adapters/git_adapter.py`

```python
import subprocess
from pathlib import Path
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

from application.ports.git_port import IGitPort
from application.validation.result import Result, Ok, Err
from domain.value_objects.branch_name import BranchName
from infrastructure.adapters.process_adapter import ProcessAdapter

class GitAdapter:
    """Adapter for git operations with resilience."""

    def __init__(self, process_adapter: ProcessAdapter):
        self._process = process_adapter

    def get_repo_root(self, cwd: Path | None = None) -> Result[Path, str]:
        """Get repository root."""
        result = self._process.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            timeout=5,
        )

        if result.success:
            stdout, _ = result.value
            return Ok(Path(stdout.strip()))
        else:
            return Err(f"Not in a git repository: {result.error}")

    def get_current_branch(self, repo_root: Path) -> Result[BranchName, str]:
        """Get current branch name."""
        result = self._process.run(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            timeout=5,
        )

        if result.success:
            stdout, _ = result.value
            branch_str = stdout.strip()
            if not branch_str:
                return Err("Not on any branch (detached HEAD)")
            return Ok(BranchName(branch_str))
        else:
            return Err(f"Failed to get branch: {result.error}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
    )
    def fetch_remote(
        self,
        repo_root: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> Result[None, str]:
        """Fetch from remote with retry."""
        cmd = ["git", "-C", str(repo_root), "fetch", remote]
        if branch:
            cmd.append(branch)

        result = self._process.run(cmd, timeout=60, retry=True)

        if result.success:
            return Ok(None)
        else:
            return Err(f"Failed to fetch from {remote}: {result.error}")

    def create_worktree(
        self,
        repo_root: Path,
        worktree_path: Path,
        branch_name: BranchName,
    ) -> Result[None, str]:
        """Create git worktree."""
        result = self._process.run(
            [
                "git",
                "-C", str(repo_root),
                "worktree", "add",
                "--quiet",
                str(worktree_path),
                str(branch_name),
            ],
            timeout=30,
        )

        if result.success:
            return Ok(None)
        else:
            _, stderr = result.error
            if "already exists" in stderr:
                return Err(f"Worktree already exists at {worktree_path}")
            elif "not a valid" in stderr:
                return Err(f"Branch '{branch_name}' does not exist")
            else:
                return Err(f"Failed to create worktree: {stderr}")

    def create_branch(
        self,
        repo_root: Path,
        branch_name: BranchName,
        base_branch: BranchName,
    ) -> Result[None, str]:
        """Create a new branch."""
        result = self._process.run(
            [
                "git",
                "-C", str(repo_root),
                "branch",
                str(branch_name),
                str(base_branch),
            ],
            timeout=10,
        )

        if result.success:
            return Ok(None)
        else:
            return Err(f"Failed to create branch: {result.error}")

    def list_worktrees(self, repo_root: Path) -> Result[List[dict], str]:
        """List all worktrees."""
        result = self._process.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            timeout=10,
        )

        if result.success:
            stdout, _ = result.value
            worktrees = self._parse_worktree_list(stdout)
            return Ok(worktrees)
        else:
            return Err(f"Failed to list worktrees: {result.error}")

    def _parse_worktree_list(self, output: str) -> List[dict]:
        """Parse git worktree list output."""
        worktrees = []
        current_wt = {}

        for line in output.split("\n"):
            if line.startswith("worktree "):
                if current_wt:
                    worktrees.append(current_wt)
                current_wt = {"path": line[9:]}
            elif line.startswith("branch "):
                current_wt["branch"] = line[7:]

        if current_wt:
            worktrees.append(current_wt)

        return worktrees
```

#### `infrastructure/adapters/process_adapter.py`

```python
import subprocess
import shutil
from pathlib import Path
from typing import List
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from application.validation.result import Result, Ok, Err

class ProcessAdapter:
    """Adapter for subprocess operations with retry and timeout."""

    def command_exists(self, command: str) -> bool:
        """Check if command is available."""
        return shutil.which(command) is not None

    def run(
        self,
        command: List[str],
        cwd: Path | None = None,
        timeout: int = 30,
        check: bool = True,
        retry_enabled: bool = False,
    ) -> Result[tuple[str, str], str]:
        """Run command with optional retry."""
        if retry_enabled:
            return self._run_with_retry(command, cwd, timeout)
        else:
            return self._run_once(command, cwd, timeout, check)

    def _run_once(
        self,
        command: List[str],
        cwd: Path | None,
        timeout: int,
        check: bool,
    ) -> Result[tuple[str, str], str]:
        """Run command once."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout,
                cwd=cwd,
            )
            return Ok((result.stdout, result.stderr))
        except subprocess.CalledProcessError as e:
            return Err(f"Command failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            return Err(f"Command timed out after {timeout}s")
        except FileNotFoundError:
            return Err(f"Command not found: {command[0]}")

    @retry(
        retry=retry_if_exception_type((subprocess.TimeoutExpired, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=20),
    )
    def _run_with_retry(
        self,
        command: List[str],
        cwd: Path | None,
        timeout: int,
    ) -> Result[tuple[str, str], str]:
        """Run command with retry on transient failures."""
        return self._run_once(command, cwd, timeout, check=True)
```

### 5.3 Use Case Implementation

#### `application/use_cases/create_worktree.py`

```python
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from application.ports.git_port import IGitPort
from application.ports.tmux_port import ITmuxPort
from application.ports.filesystem_port import IFileSystemPort
from application.validation.result import Result, Ok, Err
from application.validation.validators import validate_branch_name, validate_path
from domain.value_objects.branch_name import BranchName
from domain.value_objects.worktree_path import WorktreePath
from domain.value_objects.session_name import SessionName

@dataclass
class CreateWorktreeRequest:
    """Request to create a new worktree."""
    name: str
    base_branch: str = "main"
    query: str = ""
    pull_first: bool = False

@dataclass
class CreateWorktreeResponse:
    """Response from creating a worktree."""
    worktree_path: Path
    branch_name: str
    session_name: str
    message: str

class CreateWorktreeUseCase:
    """Use case: Create a new worktree for parallel work."""

    def __init__(
        self,
        git: IGitPort,
        tmux: ITmuxPort,
        filesystem: IFileSystemPort,
    ):
        self._git = git
        self._tmux = tmux
        self._fs = filesystem

    def execute(
        self,
        request: CreateWorktreeRequest,
    ) -> Result[CreateWorktreeResponse, str]:
        """Execute the use case."""
        # 1. Validate inputs
        validation = self._validate_request(request)
        if validation.failure:
            return validation

        # 2. Get repository root
        repo_root_result = self._git.get_repo_root()
        if repo_root_result.failure:
            return Err(repo_root_result.error)
        repo_root = repo_root_result.value

        # 3. Optionally pull latest
        if request.pull_first:
            pull_result = self._git.fetch_remote(repo_root)
            if pull_result.failure:
                return Err(f"Failed to pull: {pull_result.error}")

        # 4. Generate branch name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = BranchName(f"claude-wt-{request.name or timestamp}")

        # 5. Create branch
        base_branch = BranchName(request.base_branch)
        branch_result = self._git.create_branch(
            repo_root, branch_name, base_branch
        )
        if branch_result.failure:
            return Err(branch_result.error)

        # 6. Determine worktree path
        worktree_base = Path.home() / "dev" / "claude-wt-worktrees"
        worktree_path = worktree_base / f"{repo_root.name}-{branch_name}"

        # 7. Create worktree
        wt_result = self._git.create_worktree(
            repo_root, worktree_path, branch_name
        )
        if wt_result.failure:
            return Err(wt_result.error)

        # 8. Create tmux session if available
        session_name = SessionName(f"wt-{request.name or timestamp}")
        if self._tmux.is_available():
            session_result = self._tmux.create_session(
                str(session_name), worktree_path
            )
            if session_result.failure:
                # Non-critical, continue
                pass

        # 9. Return success response
        return Ok(CreateWorktreeResponse(
            worktree_path=worktree_path,
            branch_name=str(branch_name),
            session_name=str(session_name),
            message=f"Created worktree at {worktree_path}",
        ))

    def _validate_request(
        self,
        request: CreateWorktreeRequest,
    ) -> Result[None, str]:
        """Validate create worktree request."""
        # Validate name if provided
        if request.name:
            name_validation = validate_branch_name(request.name)
            if name_validation.failure:
                return Err(name_validation.error)

        # Validate base branch
        base_validation = validate_branch_name(request.base_branch)
        if base_validation.failure:
            return Err(f"Invalid base branch: {base_validation.error}")

        return Ok(None)
```

### 5.4 CLI Integration with DI

#### `presentation/di/container.py`

```python
from pathlib import Path
from infrastructure.adapters.git_adapter import GitAdapter
from infrastructure.adapters.tmux_adapter import TmuxAdapter
from infrastructure.adapters.process_adapter import ProcessAdapter
from infrastructure.adapters.filesystem_adapter import FileSystemAdapter
from infrastructure.adapters.console_adapter import ConsoleAdapter
from application.use_cases.create_worktree import CreateWorktreeUseCase
from application.use_cases.switch_worktree import SwitchWorktreeUseCase
from application.use_cases.clean_worktree import CleanWorktreeUseCase

class DIContainer:
    """Dependency Injection container (composition root)."""

    def __init__(self):
        self._instances = {}

    # Infrastructure adapters
    def process_adapter(self) -> ProcessAdapter:
        if 'process_adapter' not in self._instances:
            self._instances['process_adapter'] = ProcessAdapter()
        return self._instances['process_adapter']

    def git_adapter(self) -> GitAdapter:
        if 'git_adapter' not in self._instances:
            self._instances['git_adapter'] = GitAdapter(
                process_adapter=self.process_adapter()
            )
        return self._instances['git_adapter']

    def tmux_adapter(self) -> TmuxAdapter:
        if 'tmux_adapter' not in self._instances:
            self._instances['tmux_adapter'] = TmuxAdapter(
                process_adapter=self.process_adapter()
            )
        return self._instances['tmux_adapter']

    def filesystem_adapter(self) -> FileSystemAdapter:
        if 'filesystem_adapter' not in self._instances:
            self._instances['filesystem_adapter'] = FileSystemAdapter()
        return self._instances['filesystem_adapter']

    def console_adapter(self) -> ConsoleAdapter:
        if 'console_adapter' not in self._instances:
            self._instances['console_adapter'] = ConsoleAdapter()
        return self._instances['console_adapter']

    # Use cases
    def create_worktree_use_case(self) -> CreateWorktreeUseCase:
        if 'create_worktree_use_case' not in self._instances:
            self._instances['create_worktree_use_case'] = CreateWorktreeUseCase(
                git=self.git_adapter(),
                tmux=self.tmux_adapter(),
                filesystem=self.filesystem_adapter(),
            )
        return self._instances['create_worktree_use_case']

    def switch_worktree_use_case(self) -> SwitchWorktreeUseCase:
        if 'switch_worktree_use_case' not in self._instances:
            self._instances['switch_worktree_use_case'] = SwitchWorktreeUseCase(
                git=self.git_adapter(),
                tmux=self.tmux_adapter(),
                filesystem=self.filesystem_adapter(),
            )
        return self._instances['switch_worktree_use_case']

    def clean_worktree_use_case(self) -> CleanWorktreeUseCase:
        if 'clean_worktree_use_case' not in self._instances:
            self._instances['clean_worktree_use_case'] = CleanWorktreeUseCase(
                git=self.git_adapter(),
                filesystem=self.filesystem_adapter(),
            )
        return self._instances['clean_worktree_use_case']
```

#### `presentation/cli/commands/new_command.py`

```python
from cyclopts import App
from presentation.di.container import DIContainer
from application.use_cases.create_worktree import CreateWorktreeRequest

def register_new_command(app: App, container: DIContainer):
    """Register 'new' command with DI."""

    @app.command
    def new(
        query: str = "",
        branch: str = "main",
        name: str = "",
        pull: bool = False,
    ):
        """Create new worktree session."""
        # Get use case from container
        use_case = container.create_worktree_use_case()
        console = container.console_adapter()

        # Create request
        request = CreateWorktreeRequest(
            name=name,
            base_branch=branch,
            query=query,
            pull_first=pull,
        )

        # Execute use case
        result = use_case.execute(request)

        # Handle result
        if result.success:
            response = result.value
            console.success(response.message)
            console.info(f"Branch: {response.branch_name}")
            console.info(f"Session: {response.session_name}")
            return 0
        else:
            console.error(f"Failed to create worktree: {result.error}")
            return 1
```

#### `main.py`

```python
from cyclopts import App
from presentation.di.container import DIContainer
from presentation.cli.commands.new_command import register_new_command
from presentation.cli.commands.switch_command import register_switch_command
from presentation.cli.commands.clean_command import register_clean_command
from presentation.cli.commands.list_command import register_list_command

app = App(
    help="Manages isolated git worktrees for parallel Claude Code sessions.",
    version_flags=["--version", "-v"],
)

def main():
    """Main entry point with DI setup."""
    # Create DI container
    container = DIContainer()

    # Register all commands with container
    register_new_command(app, container)
    register_switch_command(app, container)
    register_clean_command(app, container)
    register_list_command(app, container)

    # Run CLI
    app()

if __name__ == "__main__":
    main()
```

---

## 6. Code Examples

See section 5 above for comprehensive code examples of:
- Port definitions
- Adapter implementations
- Use case implementation
- DI container setup
- CLI integration

---

## 7. Testing Strategy

### 7.1 Test Pyramid

```
                    ▲
                   ╱ ╲
                  ╱   ╲
                 ╱ E2E ╲          (10%) - Full integration
                ╱───────╲
               ╱         ╲
              ╱Integration╲       (20%) - Adapters with real tools
             ╱─────────────╲
            ╱               ╲
           ╱   Unit Tests    ╲    (70%) - Use cases, validation, domain
          ╱───────────────────╲
         ╱                     ╲
        ───────────────────────
```

### 7.2 Unit Tests (Use Cases)

```python
# tests/application/test_create_worktree_use_case.py
import pytest
from pathlib import Path
from application.use_cases.create_worktree import (
    CreateWorktreeUseCase,
    CreateWorktreeRequest,
)
from tests.stubs.git_stub import GitStub
from tests.stubs.tmux_stub import TmuxStub
from tests.stubs.filesystem_stub import FileSystemStub

def test_create_worktree_success():
    """Test successful worktree creation."""
    # Arrange
    git_stub = GitStub(repo_root=Path("/repo"))
    tmux_stub = TmuxStub(available=True)
    fs_stub = FileSystemStub()

    use_case = CreateWorktreeUseCase(
        git=git_stub,
        tmux=tmux_stub,
        filesystem=fs_stub,
    )

    request = CreateWorktreeRequest(name="feature-test")

    # Act
    result = use_case.execute(request)

    # Assert
    assert result.success
    assert "feature-test" in result.value.branch_name
    assert git_stub.branches_created == ["claude-wt-feature-test"]
    assert git_stub.worktrees_created == 1
    assert tmux_stub.sessions_created == 1

def test_create_worktree_invalid_name():
    """Test validation of invalid branch name."""
    git_stub = GitStub(repo_root=Path("/repo"))
    tmux_stub = TmuxStub()
    fs_stub = FileSystemStub()

    use_case = CreateWorktreeUseCase(git_stub, tmux_stub, fs_stub)
    request = CreateWorktreeRequest(name="invalid name with spaces")

    result = use_case.execute(request)

    assert result.failure
    assert "spaces" in result.error.lower()
```

### 7.3 Integration Tests (Adapters)

```python
# tests/infrastructure/test_git_adapter_integration.py
import pytest
import tempfile
import subprocess
from pathlib import Path
from infrastructure.adapters.git_adapter import GitAdapter
from infrastructure.adapters.process_adapter import ProcessAdapter

@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
        )
        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
        )
        yield repo_path

def test_git_adapter_get_repo_root(temp_git_repo):
    """Test getting repository root with real git."""
    adapter = GitAdapter(ProcessAdapter())

    result = adapter.get_repo_root(cwd=temp_git_repo)

    assert result.success
    assert result.value == temp_git_repo

def test_git_adapter_create_worktree(temp_git_repo):
    """Test creating worktree with real git."""
    adapter = GitAdapter(ProcessAdapter())

    # Create branch first
    branch_result = adapter.create_branch(
        temp_git_repo,
        BranchName("feature-test"),
        BranchName("main"),
    )
    assert branch_result.success

    # Create worktree
    wt_path = temp_git_repo / "worktrees" / "feature-test"
    wt_result = adapter.create_worktree(
        temp_git_repo,
        wt_path,
        BranchName("feature-test"),
    )

    assert wt_result.success
    assert wt_path.exists()
```

### 7.4 Test Doubles (Stubs)

```python
# tests/stubs/git_stub.py
from pathlib import Path
from typing import List
from application.ports.git_port import IGitPort
from application.validation.result import Result, Ok, Err
from domain.value_objects.branch_name import BranchName

class GitStub:
    """Stub implementation of IGitPort for testing."""

    def __init__(self, repo_root: Path | None = None):
        self._repo_root = repo_root or Path("/fake/repo")
        self.branches_created = []
        self.worktrees_created = 0
        self.fetch_called = 0

    def get_repo_root(self, cwd: Path | None = None) -> Result[Path, str]:
        return Ok(self._repo_root)

    def get_current_branch(self, repo_root: Path) -> Result[BranchName, str]:
        return Ok(BranchName("main"))

    def create_branch(
        self,
        repo_root: Path,
        branch_name: BranchName,
        base_branch: BranchName,
    ) -> Result[None, str]:
        self.branches_created.append(str(branch_name))
        return Ok(None)

    def create_worktree(
        self,
        repo_root: Path,
        worktree_path: Path,
        branch_name: BranchName,
    ) -> Result[None, str]:
        self.worktrees_created += 1
        return Ok(None)

    def fetch_remote(
        self,
        repo_root: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> Result[None, str]:
        self.fetch_called += 1
        return Ok(None)

    def list_worktrees(self, repo_root: Path) -> Result[List[dict], str]:
        return Ok([])
```

---

## 8. Benefits and Trade-offs

### 8.1 Benefits

#### ✅ Improved Testability
- **Before**: Hard to test without mocking subprocess
- **After**: Inject stubs, test use cases in isolation
- **Impact**: ~80% test coverage achievable

#### ✅ Better Error Handling
- **Before**: Mix of exceptions, SystemExit, None
- **After**: Consistent Result types, explicit errors
- **Impact**: Predictable, composable error handling

#### ✅ Increased Resilience
- **Before**: Network failures cause immediate failure
- **After**: Retry with exponential backoff, circuit breakers
- **Impact**: ~90% reduction in transient failures

#### ✅ Clearer Architecture
- **Before**: Circular dependencies, tight coupling
- **After**: Hexagonal architecture, clear layers
- **Impact**: Easier to understand, modify, extend

#### ✅ Easier Debugging
- **Before**: Silent failures, no logging
- **After**: Structured logging, error context
- **Impact**: Faster issue diagnosis

#### ✅ Swappable Implementations
- **Before**: Direct subprocess calls
- **After**: Adapters via ports
- **Impact**: Can swap git for testing, add SSH support

### 8.2 Trade-offs

#### ❌ More Code Initially
- **Cost**: ~30% more LOC initially (interfaces, adapters, DTOs)
- **Benefit**: Pays off after ~6 months (easier maintenance)

#### ❌ Learning Curve
- **Cost**: Team needs to understand Hexagonal, DI, Result types
- **Benefit**: Transferable knowledge, industry patterns

#### ❌ More Files/Directories
- **Cost**: Navigation complexity (more directories)
- **Benefit**: Better organization, easier to find code

#### ❌ Indirection
- **Cost**: More layers (CLI → Use Case → Port → Adapter)
- **Benefit**: Flexibility, testability, clarity

### 8.3 Migration Risk Mitigation

- ✅ **Incremental migration** - No big-bang rewrite
- ✅ **Feature parity** - All existing functionality preserved
- ✅ **Backward compatibility** - User experience unchanged
- ✅ **Parallel development** - Old code works during migration
- ✅ **Rollback strategy** - Can revert individual changes

---

## 9. Implementation Roadmap

### Week 1: Foundation & Validation

**Days 1-2: Setup**
- [ ] Create directory structure
- [ ] Set up pyproject.toml with new dependencies (tenacity, pybreaker)
- [ ] Define all Port interfaces (IGitPort, ITmuxPort, etc.)
- [ ] Create custom Result type

**Days 3-4: Validation & Resilience**
- [ ] Extract validation functions (validate_branch_name, etc.)
- [ ] Add retry decorators (tenacity)
- [ ] Add circuit breaker setup (pybreaker)
- [ ] Replace silent failures with structured logging

**Day 5: Basic Adapters**
- [ ] Implement ProcessAdapter with retry
- [ ] Implement basic GitAdapter
- [ ] Implement basic FileSystemAdapter
- [ ] Write adapter integration tests

### Week 2: Use Cases & Adapters

**Days 1-2: Core Use Cases**
- [ ] Implement CreateWorktreeUseCase
- [ ] Implement SwitchWorktreeUseCase
- [ ] Implement CleanWorktreeUseCase
- [ ] Write use case unit tests with stubs

**Days 3-4: Complete Adapters**
- [ ] Complete GitAdapter (all operations)
- [ ] Implement TmuxAdapter
- [ ] Implement GitHubAdapter
- [ ] Implement ConsoleAdapter
- [ ] Write adapter tests

**Day 5: DI Container**
- [ ] Create DIContainer
- [ ] Wire all dependencies
- [ ] Test container setup

### Week 3: CLI Migration & Cleanup

**Days 1-3: Migrate CLI Commands**
- [ ] Migrate `new` command
- [ ] Migrate `switch` command
- [ ] Migrate `clean` command
- [ ] Migrate `list` command
- [ ] Migrate PR commands
- [ ] Migrate Linear commands

**Days 4-5: Cleanup & Polish**
- [ ] Remove old code (worktree.py, github.py, linear.py)
- [ ] Update documentation
- [ ] Performance testing
- [ ] Final integration testing
- [ ] Tag release (v2.0.0-refactor)

---

## 10. Conclusion

The proposed architectural refactoring will transform `claude-wt` from a brittle, hard-to-test CLI tool into a robust, maintainable, and extensible application using industry-standard patterns:

- **Hexagonal Architecture** for clear separation of concerns
- **Dependency Injection** for testability and flexibility
- **Resilience patterns** for handling transient failures
- **Result types** for explicit error handling
- **Structured logging** for debugging

**Estimated effort**: 3 weeks for complete migration
**Risk**: Low (incremental, backward-compatible)
**ROI**: High (long-term maintainability, extensibility, reliability)

The migration can begin immediately with Phase 1 (Foundation), and be completed incrementally without disrupting existing functionality.

---

## Appendix A: Dependencies to Add

```toml
# pyproject.toml additions
[project]
dependencies = [
    "cyclopts>=3.0.0",
    "rich>=13.0.0",
    "tenacity>=9.0.0",     # Retry logic
    "pybreaker>=1.2.0",    # Circuit breakers
    "structlog>=24.4.0",   # Structured logging
]
```

## Appendix B: References

**Architecture Patterns**:
- Hexagonal Architecture (Alistair Cockburn): https://alistair.cockburn.us/hexagonal-architecture/
- Clean Architecture (Robert Martin): ISBN 978-0134494166
- Cosmic Python: https://www.cosmicpython.com/

**Resilience Patterns**:
- Tenacity Documentation: https://tenacity.readthedocs.io/
- PyBreaker: https://github.com/danielfm/pybreaker
- Release It! (Michael Nygard): ISBN 978-1680502398

**Python Best Practices**:
- Structlog: https://www.structlog.org/
- PEP 544 (Protocols): https://peps.python.org/pep-0544/
- Railway-Oriented Programming: https://fsharpforfunandprofit.com/rop/
