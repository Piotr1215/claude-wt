# Dependency Injection Patterns for Python CLI Applications

## Research Summary

**Date**: 2025-11-15
**Focus**: DI patterns for CLI tools using Click, Typer, and Cyclopts
**Context**: claude-wt project using Cyclopts framework

---

## 1. Dependency Injection Principles and Benefits

### What is Dependency Injection?

Dependency Injection (DI) is a design principle where objects receive their dependencies from external sources rather than creating them internally. It's a specific form of Inversion of Control (IoC).

### Core Principles

1. **Separation of Concerns**: Object creation is separated from business logic
2. **Dependency Inversion**: High-level modules don't depend on low-level modules; both depend on abstractions
3. **Explicit Dependencies**: Dependencies are clearly declared in constructors/functions
4. **Single Responsibility**: Classes focus on their core responsibility, not dependency management

### Key Benefits

- **Testability**: Easy to inject mocks, stubs, or test doubles
- **Flexibility**: Swap implementations without modifying client code
- **Maintainability**: Dependencies are explicit and easy to track
- **Loose Coupling**: Reduces tight coupling between components
- **Reusability**: Components can work with different implementations
- **Configuration Management**: Centralized dependency wiring

### Trade-offs

- **Boilerplate**: More code required for setup
- **Complexity**: Can be overkill for simple applications
- **Learning Curve**: Team needs to understand the pattern
- **Runtime vs Compile-time**: Python's dynamic nature means fewer compile-time checks

---

## 2. Python DI Libraries and Frameworks

### Comparison Matrix

| Library | Stars | Approach | Complexity | Best For |
|---------|-------|----------|------------|----------|
| **dependency-injector** | ~3.5k | Container-based | Medium-High | Full-featured apps |
| **punq** | ~403 | Minimalist container | Low | Simple use cases |
| **injector** | ~1.5k | Guice-inspired | Medium | Java developers |
| **inject** | ~744 | Decorator-based | Low-Medium | Moderate apps |
| **DIY Manual** | N/A | No framework | Very Low | Lightweight tools |

### 2.1 dependency-injector

**Pros**:
- Most feature-rich and actively maintained
- Excellent documentation with tutorials
- Supports multiple provider types (Singleton, Factory, etc.)
- Built-in wiring for popular frameworks (Flask, Django, FastAPI)
- Configuration management support
- Type hints support

**Cons**:
- Significant boilerplate for simple apps
- Steeper learning curve
- Heavier dependency

**Example**:
```python
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
import subprocess
from pathlib import Path

# Define adapters
class GitAdapter:
    def run_command(self, args: list[str], cwd: Path = None) -> str:
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=cwd, check=True
        )
        return result.stdout.strip()

class TmuxAdapter:
    def create_session(self, name: str, cwd: Path) -> None:
        subprocess.run(["tmux", "new-session", "-d", "-s", name, "-c", str(cwd)])

class FileSystemAdapter:
    def write_file(self, path: Path, content: str) -> None:
        path.write_text(content)

    def read_file(self, path: Path) -> str:
        return path.read_text()

# Define container
class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Singleton adapters
    git = providers.Singleton(GitAdapter)
    tmux = providers.Singleton(TmuxAdapter)
    filesystem = providers.Singleton(FileSystemAdapter)

# Use in CLI commands
@inject
def create_worktree(
    name: str,
    git: GitAdapter = Provide[Container.git],
    tmux: TmuxAdapter = Provide[Container.tmux],
    filesystem: FileSystemAdapter = Provide[Container.filesystem],
):
    # Business logic using injected dependencies
    repo_root = git.run_command(["git", "rev-parse", "--show-toplevel"])
    branch_name = f"claude-wt-{name}"
    git.run_command(["git", "worktree", "add", f"/tmp/{name}", branch_name])
    tmux.create_session(name, Path(f"/tmp/{name}"))
    filesystem.write_file(Path(f"/tmp/{name}/CLAUDE.md"), "# Context")

# Wire the container
def main():
    container = Container()
    container.wire(modules=[__name__])

    # Now CLI commands can be called
    create_worktree("my-feature")

if __name__ == "__main__":
    main()
```

**CLI Integration with Cyclopts**:
```python
from cyclopts import App
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

app = App()

class Container(containers.DeclarativeContainer):
    git = providers.Singleton(GitAdapter)
    tmux = providers.Singleton(TmuxAdapter)

@app.command
@inject
def new(
    name: str,
    git: GitAdapter = Provide[Container.git],
    tmux: TmuxAdapter = Provide[Container.tmux],
):
    # Use injected dependencies
    pass

def main():
    container = Container()
    container.wire(modules=[__name__])
    app()
```

### 2.2 punq

**Pros**:
- Minimalist and lightweight
- Simple API
- Good for small to medium projects
- Type-safe registration

**Cons**:
- Less features than dependency-injector
- No built-in framework integrations
- Manual wiring required

**Example**:
```python
import punq

# Create container
container = punq.Container()

# Register services
container.register(GitAdapter)
container.register(TmuxAdapter)
container.register(FileSystemAdapter)

# Resolve dependencies
def create_worktree(name: str):
    git = container.resolve(GitAdapter)
    tmux = container.resolve(TmuxAdapter)
    filesystem = container.resolve(FileSystemAdapter)

    # Use dependencies
    git.run_command(["git", "status"])
```

**CLI Integration**:
```python
from cyclopts import App
import punq

app = App()
container = punq.Container()
container.register(GitAdapter)

@app.command
def new(name: str):
    git = container.resolve(GitAdapter)
    # Use git adapter
    pass

if __name__ == "__main__":
    app()
```

### 2.3 injector

**Pros**:
- Inspired by Google Guice (familiar to Java developers)
- Decorator-based injection
- Module system for organizing dependencies
- Good type hint support

**Cons**:
- More verbose than punq
- Less Pythonic than manual DI
- Steeper learning curve

**Example**:
```python
from injector import Injector, inject, singleton

class GitAdapter:
    def run_command(self, args: list[str]) -> str:
        # Implementation
        pass

@singleton
class WorktreeService:
    @inject
    def __init__(self, git: GitAdapter):
        self.git = git

    def create(self, name: str):
        self.git.run_command(["git", "worktree", "add", name])

# Setup
injector = Injector()
service = injector.get(WorktreeService)
service.create("my-feature")
```

### 2.4 DIY Manual Dependency Injection

**Pros**:
- Zero dependencies
- Complete control
- Most Pythonic
- Easy to understand
- No framework lock-in
- Minimal boilerplate for simple cases

**Cons**:
- Manual wiring required
- No automatic lifecycle management
- Can become verbose in large projects

**Example**:
```python
# adapters.py
class GitAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def run_command(self, args: list[str], cwd: Path = None) -> str:
        result = self.subprocess.run(
            args, capture_output=True, text=True, cwd=cwd, check=True
        )
        return result.stdout.strip()

class TmuxAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def create_session(self, name: str, cwd: Path) -> None:
        self.subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", str(cwd)]
        )

class FileSystemAdapter:
    def write_file(self, path: Path, content: str) -> None:
        path.write_text(content)

    def read_file(self, path: Path) -> str:
        return path.read_text()

# services.py
class WorktreeService:
    def __init__(self, git: GitAdapter, tmux: TmuxAdapter, fs: FileSystemAdapter):
        self.git = git
        self.tmux = tmux
        self.fs = fs

    def create_worktree(self, name: str, query: str = "") -> Path:
        repo_root = Path(self.git.run_command(["git", "rev-parse", "--show-toplevel"]))
        branch_name = f"claude-wt-{name}"
        wt_path = Path(f"/tmp/{name}")

        self.git.run_command(["git", "worktree", "add", str(wt_path), branch_name])
        self.tmux.create_session(name, wt_path)
        self.fs.write_file(wt_path / "CLAUDE.md", f"# {query}")

        return wt_path

# cli.py - Manual composition root
from cyclopts import App

app = App()

# Composition root - where dependencies are wired
def create_dependencies():
    git = GitAdapter()
    tmux = TmuxAdapter()
    fs = FileSystemAdapter()
    service = WorktreeService(git, tmux, fs)
    return service

@app.command
def new(name: str, query: str = ""):
    service = create_dependencies()
    service.create_worktree(name, query)

if __name__ == "__main__":
    app()
```

**Alternative: Context object pattern**:
```python
# context.py
from dataclasses import dataclass

@dataclass
class AppContext:
    git: GitAdapter
    tmux: TmuxAdapter
    filesystem: FileSystemAdapter

def create_context() -> AppContext:
    return AppContext(
        git=GitAdapter(),
        tmux=TmuxAdapter(),
        filesystem=FileSystemAdapter(),
    )

# cli.py
from cyclopts import App

app = App()
ctx = create_context()

@app.command
def new(name: str):
    # Access via context
    ctx.git.run_command(["git", "status"])
    ctx.tmux.create_session(name, Path("."))
```

---

## 3. Constructor Injection vs Property Injection

### Constructor Injection (Recommended)

Dependencies passed through `__init__` constructor.

**Advantages**:
- Dependencies are immutable after creation
- Object is always in valid state
- Dependencies are explicit and required
- Type checkers work well
- Thread-safe by default
- Prevents circular dependencies

**Example**:
```python
class WorktreeService:
    def __init__(self, git: GitAdapter, tmux: TmuxAdapter):
        self.git = git
        self.tmux = tmux

    def create(self, name: str):
        self.git.run_command(["git", "status"])
        self.tmux.create_session(name, Path("."))

# Usage - dependencies must be provided
git = GitAdapter()
tmux = TmuxAdapter()
service = WorktreeService(git, tmux)  # Clear and explicit
```

**When to use**:
- For required dependencies
- For immutable objects
- For thread-safe code
- Most of the time (best practice)

### Property/Setter Injection

Dependencies set via properties or setter methods after construction.

**Advantages**:
- Allows partial object creation
- Can change dependencies at runtime
- Useful for optional dependencies
- Can break circular dependencies

**Disadvantages**:
- Object may be in invalid state
- Harder to track when dependencies are set
- Not thread-safe
- Mutable state is harder to reason about

**Example**:
```python
class WorktreeService:
    def __init__(self):
        self._git = None
        self._tmux = None

    @property
    def git(self) -> GitAdapter:
        if self._git is None:
            raise RuntimeError("git adapter not set")
        return self._git

    @git.setter
    def git(self, adapter: GitAdapter):
        self._git = adapter

    @property
    def tmux(self) -> TmuxAdapter:
        if self._tmux is None:
            raise RuntimeError("tmux adapter not set")
        return self._tmux

    @tmux.setter
    def tmux(self, adapter: TmuxAdapter):
        self._tmux = adapter

# Usage - dependencies set after creation
service = WorktreeService()
service.git = GitAdapter()  # Can forget to set
service.tmux = TmuxAdapter()
```

**When to use**:
- For optional dependencies
- For circular dependencies (better: refactor)
- For legacy code migration
- Rarely in new code

### Method Injection

Dependencies passed to specific methods.

**Advantages**:
- Different dependency per call
- No state in object
- Very flexible

**Example**:
```python
class WorktreeService:
    def create_worktree(self, name: str, git: GitAdapter, tmux: TmuxAdapter):
        git.run_command(["git", "status"])
        tmux.create_session(name, Path("."))

# Usage - dependency per call
service = WorktreeService()
service.create_worktree("feat-1", git1, tmux1)
service.create_worktree("feat-2", git2, tmux2)  # Different deps
```

**When to use**:
- When dependency varies per operation
- For strategy pattern implementations
- When you want stateless services

### Recommendation for CLI Tools

**Use constructor injection by default**. It provides the best balance of:
- Explicitness
- Type safety
- Immutability
- Testability

Only use property/method injection when you have a specific need for runtime flexibility.

---

## 4. Service Locator Pattern (Anti-Pattern?)

### What is Service Locator?

A Service Locator is a central registry where objects can request their dependencies at runtime.

**Example**:
```python
# Service locator (anti-pattern)
class ServiceLocator:
    _services = {}

    @classmethod
    def register(cls, name: str, service):
        cls._services[name] = service

    @classmethod
    def get(cls, name: str):
        return cls._services[name]

# Registration
ServiceLocator.register("git", GitAdapter())
ServiceLocator.register("tmux", TmuxAdapter())

# Usage - dependencies are hidden!
class WorktreeService:
    def create(self, name: str):
        # Dependencies not visible in signature
        git = ServiceLocator.get("git")
        tmux = ServiceLocator.get("tmux")

        git.run_command(["git", "status"])
        tmux.create_session(name, Path("."))
```

### Why It's Considered an Anti-Pattern

1. **Hidden Dependencies**: Not visible in class signature
   ```python
   # Which dependencies does this need? Unknown!
   service = WorktreeService()
   ```

2. **Runtime Errors**: Fails at runtime, not compile/import time
   ```python
   # Typo not caught by type checker
   git = ServiceLocator.get("gitt")  # KeyError at runtime!
   ```

3. **Testing Difficulties**: Hard to isolate tests
   ```python
   # Test pollution - state shared across tests
   def test_one():
       ServiceLocator.register("git", MockGit())
       # Test code

   def test_two():
       # Still has MockGit from test_one! Need manual cleanup
       service = ServiceLocator.get("git")
   ```

4. **Violates Encapsulation**: Objects reach out to get dependencies
   ```python
   # Object is responsible for finding its dependencies
   class Service:
       def __init__(self):
           self.git = ServiceLocator.get("git")  # Coupling to locator
   ```

5. **No Type Safety**: Type checkers can't help
   ```python
   # Type checker doesn't know what get() returns
   git = ServiceLocator.get("git")  # type: Unknown
   ```

### Dependency Injection Alternative

```python
# DI - dependencies are explicit
class WorktreeService:
    def __init__(self, git: GitAdapter, tmux: TmuxAdapter):  # Clear!
        self.git = git
        self.tmux = tmux

# Clear what dependencies are needed
service = WorktreeService(git, tmux)
```

### When Service Locator Might Be Acceptable

- **Plugin systems**: Dynamic plugin discovery
- **Framework internals**: Flask's `g`, Django's settings (but not for application code)
- **Legacy code**: Gradual migration strategy

### Python-Specific Note

Some Python DI frameworks (like `dependency-injector`) use a container that looks like a service locator but is used only at the **composition root** (application startup), not throughout the code. This is acceptable because:

1. Dependencies are still explicit in class signatures
2. Container is only used for initial wiring
3. Type hints still work
4. Tests can inject directly without the container

---

## 5. How to Inject Dependencies in CLI Tools

### 5.1 Click

Click uses decorators for commands and doesn't have built-in DI support.

**Option 1: Manual DI with context object**
```python
import click
from dataclasses import dataclass

@dataclass
class AppContext:
    git: GitAdapter
    tmux: TmuxAdapter

@click.group()
@click.pass_context
def cli(ctx):
    # Create dependencies at root
    ctx.obj = AppContext(
        git=GitAdapter(),
        tmux=TmuxAdapter(),
    )

@cli.command()
@click.argument('name')
@click.pass_obj
def new(ctx: AppContext, name: str):
    # Access dependencies from context
    ctx.git.run_command(["git", "status"])
    ctx.tmux.create_session(name, Path("."))

if __name__ == '__main__':
    cli()
```

**Option 2: Click + dependency-injector**
```python
import click
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

class Container(containers.DeclarativeContainer):
    git = providers.Singleton(GitAdapter)
    tmux = providers.Singleton(TmuxAdapter)

@click.command()
@click.argument('name')
@inject
def new(
    name: str,
    git: GitAdapter = Provide[Container.git],
    tmux: TmuxAdapter = Provide[Container.tmux],
):
    git.run_command(["git", "status"])
    tmux.create_session(name, Path("."))

if __name__ == '__main__':
    container = Container()
    container.wire(modules=[__name__])
    new()
```

### 5.2 Typer

Typer is built on Click and has similar patterns.

**Option 1: Manual DI with dependency functions**
```python
import typer
from typing import Annotated

app = typer.Typer()

# Dependency functions (similar to FastAPI)
def get_git() -> GitAdapter:
    return GitAdapter()

def get_tmux() -> TmuxAdapter:
    return TmuxAdapter()

@app.command()
def new(
    name: str,
    git: Annotated[GitAdapter, typer.Depends(get_git)],
    tmux: Annotated[TmuxAdapter, typer.Depends(get_tmux)],
):
    git.run_command(["git", "status"])
    tmux.create_session(name, Path("."))

if __name__ == "__main__":
    app()
```

**Option 2: Simple context object**
```python
import typer
from dataclasses import dataclass

app = typer.Typer()

@dataclass
class Context:
    git: GitAdapter
    tmux: TmuxAdapter

# Create global context (or pass through state)
ctx = Context(git=GitAdapter(), tmux=TmuxAdapter())

@app.command()
def new(name: str):
    ctx.git.run_command(["git", "status"])
    ctx.tmux.create_session(name, Path("."))
```

### 5.3 Cyclopts (Current Project)

Cyclopts doesn't have built-in DI, so manual DI is the cleanest approach.

**Option 1: Composition root pattern (Recommended for claude-wt)**
```python
from cyclopts import App
from pathlib import Path

app = App()

# Adapters
class GitAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def run_command(self, args: list[str], cwd: Path = None) -> str:
        result = self.subprocess.run(
            args, capture_output=True, text=True, cwd=cwd, check=True
        )
        return result.stdout.strip()

class TmuxAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def create_session(self, name: str, cwd: Path) -> None:
        self.subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", str(cwd)], check=True
        )

# Service layer
class WorktreeService:
    def __init__(self, git: GitAdapter, tmux: TmuxAdapter):
        self.git = git
        self.tmux = tmux

    def create_worktree(self, name: str, branch: str = "") -> Path:
        repo_root = Path(self.git.run_command(["git", "rev-parse", "--show-toplevel"]))
        current_branch = self.git.run_command(["git", "branch", "--show-current"])
        source_branch = branch or current_branch

        branch_name = f"claude-wt-{name}"
        wt_path = Path.home() / "dev" / "claude-wt-worktrees" / f"myrepo-{name}"

        self.git.run_command(
            ["git", "worktree", "add", "-b", branch_name, str(wt_path), source_branch]
        )
        self.tmux.create_session(f"wt-{name}", wt_path)

        return wt_path

# Composition root - create dependencies once
def create_service() -> WorktreeService:
    git = GitAdapter()
    tmux = TmuxAdapter()
    return WorktreeService(git, tmux)

# CLI commands
@app.command
def new(name: str, branch: str = ""):
    service = create_service()
    wt_path = service.create_worktree(name, branch)
    print(f"Created worktree at: {wt_path}")

@app.command
def clean(name: str):
    service = create_service()
    # Clean logic here
    pass

if __name__ == "__main__":
    app()
```

**Option 2: Global context (simpler for small CLIs)**
```python
from cyclopts import App
from dataclasses import dataclass

app = App()

@dataclass
class AppContext:
    git: GitAdapter
    tmux: TmuxAdapter
    filesystem: FileSystemAdapter

# Create context once at module level
_ctx = AppContext(
    git=GitAdapter(),
    tmux=TmuxAdapter(),
    filesystem=FileSystemAdapter(),
)

@app.command
def new(name: str):
    _ctx.git.run_command(["git", "status"])
    _ctx.tmux.create_session(name, Path("."))

@app.command
def clean(name: str):
    _ctx.git.run_command(["git", "worktree", "remove", name])
```

**Option 3: With dependency-injector**
```python
from cyclopts import App
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

app = App()

class Container(containers.DeclarativeContainer):
    git = providers.Singleton(GitAdapter)
    tmux = providers.Singleton(TmuxAdapter)

@app.command
@inject
def new(
    name: str,
    git: GitAdapter = Provide[Container.git],
    tmux: TmuxAdapter = Provide[Container.tmux],
):
    git.run_command(["git", "status"])
    tmux.create_session(name, Path("."))

def main():
    container = Container()
    container.wire(modules=[__name__])
    app()

if __name__ == "__main__":
    main()
```

---

## 6. Testing with DI (Mocking, Stubbing, Test Doubles)

### Types of Test Doubles

1. **Dummy**: Passed but never used (fills parameter lists)
2. **Stub**: Returns canned responses
3. **Spy**: Records how it was called
4. **Mock**: Pre-programmed with expectations
5. **Fake**: Working implementation (e.g., in-memory database)

### Testing with Manual DI (Recommended)

**Production code**:
```python
# adapters.py
class GitAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def run_command(self, args: list[str], cwd: Path = None) -> str:
        result = self.subprocess.run(
            args, capture_output=True, text=True, cwd=cwd, check=True
        )
        return result.stdout.strip()

class TmuxAdapter:
    def create_session(self, name: str, cwd: Path) -> None:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", str(cwd)], check=True
        )

# services.py
class WorktreeService:
    def __init__(self, git: GitAdapter, tmux: TmuxAdapter):
        self.git = git
        self.tmux = tmux

    def create_worktree(self, name: str) -> Path:
        repo_root = Path(self.git.run_command(["git", "rev-parse", "--show-toplevel"]))
        self.git.run_command(["git", "worktree", "add", f"/tmp/{name}", name])
        self.tmux.create_session(name, Path(f"/tmp/{name}"))
        return Path(f"/tmp/{name}")
```

**Test with stubs (no mocking library)**:
```python
# test_worktree.py
import pytest
from pathlib import Path

# Stub implementations
class StubGitAdapter:
    def __init__(self, repo_root: str = "/test/repo"):
        self.repo_root = repo_root
        self.commands_run = []

    def run_command(self, args: list[str], cwd: Path = None) -> str:
        self.commands_run.append(args)
        if "rev-parse" in args:
            return self.repo_root
        return ""

class StubTmuxAdapter:
    def __init__(self):
        self.sessions_created = []

    def create_session(self, name: str, cwd: Path) -> None:
        self.sessions_created.append((name, cwd))

# Tests
def test_create_worktree_creates_branch():
    # ARRANGE
    git = StubGitAdapter(repo_root="/home/user/myproject")
    tmux = StubTmuxAdapter()
    service = WorktreeService(git, tmux)

    # ACT
    result = service.create_worktree("my-feature")

    # ASSERT
    assert result == Path("/tmp/my-feature")
    assert any("worktree" in str(cmd) and "add" in str(cmd)
               for cmd in git.commands_run)
    assert ("my-feature", Path("/tmp/my-feature")) in tmux.sessions_created

def test_create_worktree_uses_repo_root():
    # ARRANGE
    git = StubGitAdapter(repo_root="/custom/path")
    tmux = StubTmuxAdapter()
    service = WorktreeService(git, tmux)

    # ACT
    service.create_worktree("test")

    # ASSERT
    assert git.commands_run[0] == ["git", "rev-parse", "--show-toplevel"]
```

**Test with unittest.mock**:
```python
from unittest.mock import Mock, call
import pytest

def test_create_worktree_with_mock():
    # ARRANGE
    git = Mock(spec=GitAdapter)
    git.run_command.return_value = "/home/user/repo"

    tmux = Mock(spec=TmuxAdapter)

    service = WorktreeService(git, tmux)

    # ACT
    result = service.create_worktree("my-feature")

    # ASSERT
    git.run_command.assert_called()
    tmux.create_session.assert_called_once_with(
        "my-feature", Path("/tmp/my-feature")
    )
```

**Test with pytest fixtures**:
```python
# conftest.py
import pytest

@pytest.fixture
def git_adapter():
    return StubGitAdapter()

@pytest.fixture
def tmux_adapter():
    return StubTmuxAdapter()

@pytest.fixture
def worktree_service(git_adapter, tmux_adapter):
    return WorktreeService(git_adapter, tmux_adapter)

# test_worktree.py
def test_create_worktree(worktree_service, git_adapter):
    result = worktree_service.create_worktree("test")

    assert result == Path("/tmp/test")
    assert git_adapter.commands_run  # Verify git was called
```

### Testing with dependency-injector

```python
# Production container
class Container(containers.DeclarativeContainer):
    git = providers.Singleton(GitAdapter)
    tmux = providers.Singleton(TmuxAdapter)

# Test container
class TestContainer(containers.DeclarativeContainer):
    git = providers.Singleton(StubGitAdapter)
    tmux = providers.Singleton(StubTmuxAdapter)

# Test
@inject
def test_create_worktree(
    git: StubGitAdapter = Provide[TestContainer.git],
    tmux: StubTmuxAdapter = Provide[TestContainer.tmux],
):
    service = WorktreeService(git, tmux)
    service.create_worktree("test")

    assert git.commands_run
    assert tmux.sessions_created

# Wire test container
def setup_module():
    container = TestContainer()
    container.wire(modules=[__name__])
```

### Testing CLI Commands

**Current approach (using patch)**:
```python
# test_cli_commands.py
from unittest.mock import patch, Mock

@patch("claude_wt.cli.create_new_worktree")
def test_new_command(mock_create_worktree):
    new(query="test", name="feature")

    mock_create_worktree.assert_called_once()
```

**With DI (better)**:
```python
# cli.py with DI
@app.command
def new(name: str, service: WorktreeService = None):
    service = service or create_service()  # Default to production
    service.create_worktree(name)

# test_cli.py - no mocking needed!
def test_new_command():
    # Create test service with stubs
    git = StubGitAdapter()
    tmux = StubTmuxAdapter()
    service = WorktreeService(git, tmux)

    # Call CLI with test service
    new("test-feature", service=service)

    # Verify behavior
    assert git.commands_run
    assert tmux.sessions_created
```

### Fake Implementations for Integration Tests

```python
# test_doubles.py
class FakeFileSystem:
    """In-memory filesystem for testing"""
    def __init__(self):
        self.files = {}

    def write_file(self, path: Path, content: str) -> None:
        self.files[str(path)] = content

    def read_file(self, path: Path) -> str:
        return self.files.get(str(path), "")

    def exists(self, path: Path) -> bool:
        return str(path) in self.files

class FakeGit:
    """In-memory git operations for testing"""
    def __init__(self):
        self.branches = ["main"]
        self.worktrees = {}
        self.current_branch = "main"

    def run_command(self, args: list[str], cwd: Path = None) -> str:
        if "branch" in args and "--show-current" in args:
            return self.current_branch
        elif "worktree" in args and "add" in args:
            # Parse: git worktree add <path> <branch>
            wt_path = args[args.index("add") + 1]
            branch = args[args.index("add") + 2]
            self.worktrees[wt_path] = branch
            self.branches.append(branch)
            return ""
        elif "rev-parse" in args:
            return "/fake/repo"
        return ""

# test_integration.py
def test_full_worktree_workflow():
    # Use fake implementations
    git = FakeGit()
    tmux = StubTmuxAdapter()
    fs = FakeFileSystem()

    service = WorktreeService(git, tmux)

    # Create worktree
    wt_path = service.create_worktree("my-feature")

    # Verify state in fakes
    assert "my-feature" in git.branches
    assert len(git.worktrees) == 1
    assert ("my-feature", wt_path) in tmux.sessions_created
```

---

## 7. Configuration Management with DI

### Environment-Based Configuration

```python
# config.py
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class GitConfig:
    default_branch: str = "main"
    worktree_base: Path = Path.home() / "dev" / "claude-wt-worktrees"

    @classmethod
    def from_env(cls):
        return cls(
            default_branch=os.getenv("GIT_DEFAULT_BRANCH", "main"),
            worktree_base=Path(os.getenv("WORKTREE_BASE", cls.worktree_base)),
        )

@dataclass
class TmuxConfig:
    auto_create_session: bool = True
    session_prefix: str = "wt-"

    @classmethod
    def from_env(cls):
        return cls(
            auto_create_session=os.getenv("AUTO_TMUX", "true").lower() == "true",
            session_prefix=os.getenv("TMUX_PREFIX", "wt-"),
        )

# adapters.py
class GitAdapter:
    def __init__(self, config: GitConfig, subprocess_runner=None):
        self.config = config
        self.subprocess = subprocess_runner or subprocess

    def get_worktree_base(self) -> Path:
        return self.config.worktree_base

class TmuxAdapter:
    def __init__(self, config: TmuxConfig, subprocess_runner=None):
        self.config = config
        self.subprocess = subprocess_runner or subprocess

    def create_session(self, name: str, cwd: Path) -> None:
        if not self.config.auto_create_session:
            return

        session_name = f"{self.config.session_prefix}{name}"
        self.subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", str(cwd)]
        )

# cli.py
def create_dependencies():
    git_config = GitConfig.from_env()
    tmux_config = TmuxConfig.from_env()

    git = GitAdapter(git_config)
    tmux = TmuxAdapter(tmux_config)

    return WorktreeService(git, tmux)

@app.command
def new(name: str):
    service = create_dependencies()
    service.create_worktree(name)
```

### With dependency-injector

```python
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    git_config = providers.Singleton(
        GitConfig,
        default_branch=config.git.default_branch,
        worktree_base=config.git.worktree_base,
    )

    tmux_config = providers.Singleton(
        TmuxConfig,
        auto_create_session=config.tmux.auto_create_session,
        session_prefix=config.tmux.session_prefix,
    )

    git = providers.Singleton(GitAdapter, config=git_config)
    tmux = providers.Singleton(TmuxAdapter, config=tmux_config)

    service = providers.Factory(WorktreeService, git=git, tmux=tmux)

# Initialize with config
container = Container()
container.config.from_yaml("config.yaml")

# Or from environment
container.config.git.default_branch.from_env("GIT_DEFAULT_BRANCH", "main")
```

### Configuration Files

**config.yaml**:
```yaml
git:
  default_branch: main
  worktree_base: ~/dev/claude-wt-worktrees

tmux:
  auto_create_session: true
  session_prefix: "wt-"

features:
  enable_hooks: true
  copy_gitignored_files: true
```

**Loading in manual DI**:
```python
import yaml
from pathlib import Path

def load_config(config_path: Path = None) -> dict:
    if config_path is None:
        config_path = Path.home() / ".config" / "claude-wt" / "config.yaml"

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f)

def create_dependencies():
    config = load_config()

    git_config = GitConfig(
        default_branch=config.get("git", {}).get("default_branch", "main"),
        worktree_base=Path(config.get("git", {}).get("worktree_base",
                                                      Path.home() / "dev" / "claude-wt-worktrees")),
    )

    git = GitAdapter(git_config)
    tmux = TmuxAdapter(TmuxConfig())

    return WorktreeService(git, tmux)
```

---

## 8. Concrete Examples for claude-wt

### Example 1: Injecting Git Adapter

**Current code (direct subprocess calls)**:
```python
# worktree.py
def create_new_worktree(query: str, branch: str = "", name: str = ""):
    # Direct subprocess call - hard to test
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    repo_root = Path(result.stdout.strip())

    # More subprocess calls...
```

**Refactored with DI**:
```python
# adapters/git.py
from pathlib import Path
import subprocess
from typing import Protocol

class SubprocessRunner(Protocol):
    """Protocol for subprocess operations"""
    def run(self, args, **kwargs): ...

class GitAdapter:
    """Adapter for git operations"""
    def __init__(self, subprocess_runner: SubprocessRunner = None):
        self.subprocess = subprocess_runner or subprocess

    def get_repo_root(self, cwd: Path = None) -> Path:
        """Get repository root directory"""
        result = self.subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return Path(result.stdout.strip())

    def get_current_branch(self, cwd: Path = None) -> str:
        """Get current branch name"""
        result = self.subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return result.stdout.strip()

    def create_worktree(
        self, path: Path, branch: str, source_branch: str = None, cwd: Path = None
    ) -> None:
        """Create a new worktree"""
        args = ["git", "worktree", "add"]

        if source_branch:
            args.extend(["-b", branch, str(path), source_branch])
        else:
            args.extend([str(path), branch])

        self.subprocess.run(args, check=True, cwd=cwd)

    def remove_worktree(self, path: Path, cwd: Path = None) -> None:
        """Remove a worktree"""
        self.subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],
            check=True,
            cwd=cwd,
        )

    def delete_branch(self, branch: str, cwd: Path = None) -> None:
        """Delete a branch"""
        self.subprocess.run(
            ["git", "branch", "-D", branch],
            check=True,
            cwd=cwd,
        )

    def list_worktrees(self, cwd: Path = None) -> list[dict]:
        """List all worktrees"""
        result = self.subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )

        worktrees = []
        current = {}

        for line in result.stdout.strip().split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1]
            elif line.startswith("HEAD "):
                current["head"] = line.split(" ", 1)[1]

        if current:
            worktrees.append(current)

        return worktrees

# services/worktree.py
class WorktreeService:
    """Service for worktree operations"""
    def __init__(
        self,
        git: GitAdapter,
        tmux: TmuxAdapter,
        filesystem: FileSystemAdapter,
    ):
        self.git = git
        self.tmux = tmux
        self.filesystem = filesystem

    def create_new_worktree(
        self, query: str, branch: str = "", name: str = ""
    ) -> Path:
        """Create a new worktree with tmux session"""
        # Get repository info
        repo_root = self.git.get_repo_root()
        current_branch = self.git.get_current_branch()
        source_branch = branch or current_branch

        # Generate branch name
        if not name:
            from datetime import datetime
            name = datetime.now().strftime("%Y%m%d-%H%M%S")

        branch_name = f"claude-wt-{name}"

        # Create worktree path
        wt_base = Path.home() / "dev" / "claude-wt-worktrees"
        repo_name = repo_root.name
        wt_path = wt_base / f"{repo_name}-{name}"

        # Create worktree
        self.git.create_worktree(wt_path, branch_name, source_branch, repo_root)

        # Create context file
        self.filesystem.write_file(
            wt_path / "CLAUDE.md",
            f"# Worktree for {branch_name}\n\nQuery: {query}\n"
        )

        # Create tmux session
        self.tmux.create_session(f"wt-{name}", wt_path)

        return wt_path

# cli.py
from cyclopts import App

app = App()

def create_worktree_service() -> WorktreeService:
    """Composition root for worktree service"""
    git = GitAdapter()
    tmux = TmuxAdapter()
    filesystem = FileSystemAdapter()
    return WorktreeService(git, tmux, filesystem)

@app.command
def new(query: str = "", branch: str = "", name: str = ""):
    """Create new worktree"""
    service = create_worktree_service()
    wt_path = service.create_new_worktree(query, branch, name)
    print(f"Created worktree at: {wt_path}")

# tests/test_worktree_service.py
import pytest

class FakeSubprocess:
    """Fake subprocess for testing"""
    def __init__(self):
        self.commands = []

    def run(self, args, **kwargs):
        self.commands.append(args)

        # Return fake responses
        if "rev-parse" in args:
            return FakeResult("/home/user/myproject")
        elif "branch" in args and "--show-current" in args:
            return FakeResult("main")

        return FakeResult("")

class FakeResult:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.returncode = 0

def test_create_worktree_gets_repo_info():
    # ARRANGE
    fake_subprocess = FakeSubprocess()
    git = GitAdapter(subprocess_runner=fake_subprocess)
    tmux = StubTmuxAdapter()
    fs = FakeFileSystem()

    service = WorktreeService(git, tmux, fs)

    # ACT
    wt_path = service.create_new_worktree("test query", name="my-feature")

    # ASSERT
    assert ["git", "rev-parse", "--show-toplevel"] in fake_subprocess.commands
    assert ["git", "branch", "--show-current"] in fake_subprocess.commands
    assert any("worktree" in str(cmd) and "add" in str(cmd)
               for cmd in fake_subprocess.commands)
```

### Example 2: Injecting Tmux Adapter

**adapters/tmux.py**:
```python
from pathlib import Path
import subprocess
import os
from typing import Protocol

class SubprocessRunner(Protocol):
    def run(self, args, **kwargs): ...

class TmuxAdapter:
    """Adapter for tmux operations"""
    def __init__(self, subprocess_runner: SubprocessRunner = None):
        self.subprocess = subprocess_runner or subprocess

    def is_in_tmux(self) -> bool:
        """Check if running inside tmux"""
        return os.environ.get("TMUX") is not None

    def session_exists(self, name: str) -> bool:
        """Check if tmux session exists"""
        result = self.subprocess.run(
            ["tmux", "has-session", "-t", name],
            capture_output=True,
        )
        return result.returncode == 0

    def create_session(self, name: str, cwd: Path, detached: bool = True) -> None:
        """Create new tmux session"""
        args = ["tmux", "new-session"]

        if detached:
            args.append("-d")

        args.extend(["-s", name, "-c", str(cwd)])

        self.subprocess.run(args, check=True)

    def switch_to_session(self, name: str) -> None:
        """Switch to existing session"""
        self.subprocess.run(
            ["tmux", "switch-client", "-t", name],
            check=True,
        )

    def send_keys(self, session: str, keys: str, enter: bool = True) -> None:
        """Send keys to tmux session"""
        args = ["tmux", "send-keys", "-t", session, keys]

        if enter:
            args.append("Enter")

        self.subprocess.run(args, check=True)

    def kill_session(self, name: str) -> None:
        """Kill tmux session"""
        self.subprocess.run(
            ["tmux", "kill-session", "-t", name],
            check=True,
        )

# tests/test_tmux.py
class StubTmuxAdapter:
    """Stub for testing tmux operations"""
    def __init__(self):
        self.sessions_created = []
        self.sessions_killed = []
        self.keys_sent = []

    def is_in_tmux(self) -> bool:
        return True

    def session_exists(self, name: str) -> bool:
        return name in [s[0] for s in self.sessions_created]

    def create_session(self, name: str, cwd: Path, detached: bool = True) -> None:
        self.sessions_created.append((name, cwd, detached))

    def send_keys(self, session: str, keys: str, enter: bool = True) -> None:
        self.keys_sent.append((session, keys, enter))

    def kill_session(self, name: str) -> None:
        self.sessions_killed.append(name)
```

### Example 3: Injecting Subprocess Runner

**adapters/subprocess_adapter.py**:
```python
import subprocess
from typing import Protocol, Any
from pathlib import Path

class SubprocessResult:
    """Value object for subprocess results"""
    def __init__(self, stdout: str, stderr: str, returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

class ISubprocessRunner(Protocol):
    """Interface for subprocess operations"""
    def run(
        self,
        args: list[str],
        cwd: Path = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> SubprocessResult: ...

class SubprocessAdapter:
    """Real subprocess adapter"""
    def run(
        self,
        args: list[str],
        cwd: Path = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> SubprocessResult:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            check=check,
        )
        return SubprocessResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

class FakeSubprocessRunner:
    """Fake for testing - no actual subprocess calls"""
    def __init__(self):
        self.commands_run = []
        self.responses = {}

    def set_response(self, command_pattern: str, stdout: str = "",
                     stderr: str = "", returncode: int = 0):
        """Configure response for a command pattern"""
        self.responses[command_pattern] = (stdout, stderr, returncode)

    def run(
        self,
        args: list[str],
        cwd: Path = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> SubprocessResult:
        self.commands_run.append({
            "args": args,
            "cwd": cwd,
            "capture_output": capture_output,
            "text": text,
            "check": check,
        })

        # Find matching response
        cmd_str = " ".join(args)
        for pattern, (stdout, stderr, returncode) in self.responses.items():
            if pattern in cmd_str:
                if check and returncode != 0:
                    raise subprocess.CalledProcessError(returncode, args)
                return SubprocessResult(stdout, stderr, returncode)

        # Default response
        return SubprocessResult("", "", 0)

# Use in adapters
class GitAdapter:
    def __init__(self, subprocess_runner: ISubprocessRunner = None):
        self.subprocess = subprocess_runner or SubprocessAdapter()

    def get_repo_root(self) -> Path:
        result = self.subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())

# Test
def test_git_adapter_with_fake_subprocess():
    # ARRANGE
    fake = FakeSubprocessRunner()
    fake.set_response("rev-parse", stdout="/home/user/repo\n")

    git = GitAdapter(subprocess_runner=fake)

    # ACT
    repo_root = git.get_repo_root()

    # ASSERT
    assert repo_root == Path("/home/user/repo")
    assert len(fake.commands_run) == 1
    assert fake.commands_run[0]["args"] == ["git", "rev-parse", "--show-toplevel"]
```

### Example 4: Injecting File System Operations

**adapters/filesystem.py**:
```python
from pathlib import Path
from typing import Protocol
import shutil

class IFileSystem(Protocol):
    """Interface for filesystem operations"""
    def read_file(self, path: Path) -> str: ...
    def write_file(self, path: Path, content: str) -> None: ...
    def exists(self, path: Path) -> bool: ...
    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None: ...
    def copy_file(self, src: Path, dst: Path) -> None: ...
    def remove(self, path: Path) -> None: ...

class FileSystemAdapter:
    """Real filesystem adapter"""
    def read_file(self, path: Path) -> str:
        return path.read_text()

    def write_file(self, path: Path, content: str) -> None:
        path.write_text(content)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def copy_file(self, src: Path, dst: Path) -> None:
        shutil.copy2(src, dst)

    def remove(self, path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

class FakeFileSystem:
    """In-memory filesystem for testing"""
    def __init__(self):
        self.files: dict[str, str] = {}
        self.directories: set[str] = set()

    def read_file(self, path: Path) -> str:
        key = str(path)
        if key not in self.files:
            raise FileNotFoundError(f"No such file: {path}")
        return self.files[key]

    def write_file(self, path: Path, content: str) -> None:
        self.files[str(path)] = content
        # Auto-create parent directories
        parent = str(path.parent)
        if parent != ".":
            self.directories.add(parent)

    def exists(self, path: Path) -> bool:
        key = str(path)
        return key in self.files or key in self.directories

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        key = str(path)
        if key in self.directories and not exist_ok:
            raise FileExistsError(f"Directory exists: {path}")
        self.directories.add(key)

    def copy_file(self, src: Path, dst: Path) -> None:
        self.files[str(dst)] = self.files[str(src)]

    def remove(self, path: Path) -> None:
        key = str(path)
        if key in self.files:
            del self.files[key]
        elif key in self.directories:
            self.directories.remove(key)

# Use in services
from claude_wt.core import create_worktree_context as create_context_content

class WorktreeContextService:
    def __init__(self, filesystem: IFileSystem):
        self.filesystem = filesystem

    def create_context_file(
        self, wt_path: Path, issue_id: str, branch_name: str, repo_root: Path
    ) -> None:
        """Create CLAUDE.md context file in worktree"""
        content = create_context_content(wt_path, issue_id, branch_name, repo_root)
        claude_md = wt_path / "CLAUDE.md"
        self.filesystem.write_file(claude_md, content)

# Test
def test_create_context_file():
    # ARRANGE
    fs = FakeFileSystem()
    service = WorktreeContextService(fs)

    wt_path = Path("/tmp/worktree")

    # ACT
    service.create_context_file(
        wt_path,
        issue_id="DOC-123",
        branch_name="claude-wt-doc-123",
        repo_root=Path("/home/user/repo"),
    )

    # ASSERT
    claude_md_path = wt_path / "CLAUDE.md"
    assert fs.exists(claude_md_path)
    content = fs.read_file(claude_md_path)
    assert "DOC-123" in content
    assert "claude-wt-doc-123" in content
```

---

## 9. Lightweight DI vs Heavy Frameworks

### Lightweight Approach (Recommended for claude-wt)

**Characteristics**:
- Manual dependency injection
- Constructor injection
- Simple composition root
- No external DI framework
- Minimal boilerplate

**Pros**:
- Zero dependencies
- Easy to understand
- Full control
- Fast startup
- No magic
- Works with all type checkers

**Cons**:
- Manual wiring
- No lifecycle management
- More verbose for complex apps

**Best for**:
- CLI tools (like claude-wt)
- Small to medium applications
- Projects valuing simplicity
- Teams new to DI

**Example**:
```python
# Lightweight DI for claude-wt
from pathlib import Path
from dataclasses import dataclass

# Simple adapters
class GitAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def get_repo_root(self) -> Path:
        result = self.subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())

class TmuxAdapter:
    def __init__(self, subprocess_runner=None):
        self.subprocess = subprocess_runner or subprocess

    def create_session(self, name: str, cwd: Path) -> None:
        self.subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", str(cwd)],
            check=True
        )

# Service
class WorktreeService:
    def __init__(self, git: GitAdapter, tmux: TmuxAdapter):
        self.git = git
        self.tmux = tmux

    def create(self, name: str) -> Path:
        repo_root = self.git.get_repo_root()
        wt_path = Path(f"/tmp/{name}")
        self.git.run_command(["git", "worktree", "add", str(wt_path)])
        self.tmux.create_session(name, wt_path)
        return wt_path

# Composition root - ONE function to wire everything
def create_service() -> WorktreeService:
    return WorktreeService(
        git=GitAdapter(),
        tmux=TmuxAdapter(),
    )

# CLI
@app.command
def new(name: str):
    service = create_service()  # Simple!
    service.create(name)

# Testing
def test_create_worktree():
    # Easy to inject test doubles
    service = WorktreeService(
        git=StubGitAdapter(),
        tmux=StubTmuxAdapter(),
    )
    service.create("test")
```

### Heavy Framework Approach

**Characteristics**:
- Container-based DI (dependency-injector, injector)
- Automatic wiring
- Lifecycle management
- Configuration support

**Pros**:
- Less boilerplate for large apps
- Automatic dependency resolution
- Built-in scopes (singleton, transient)
- Configuration management
- Framework integrations

**Cons**:
- Additional dependency
- Learning curve
- More complex
- "Magic" behavior
- Slower startup (minimal)

**Best for**:
- Large applications
- Multiple environments
- Complex dependency graphs
- Teams familiar with DI

**Example**:
```python
# Heavy framework approach with dependency-injector
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Subprocess runner
    subprocess = providers.Singleton(SubprocessAdapter)

    # Adapters
    git = providers.Singleton(
        GitAdapter,
        subprocess_runner=subprocess,
    )

    tmux = providers.Singleton(
        TmuxAdapter,
        subprocess_runner=subprocess,
    )

    filesystem = providers.Singleton(FileSystemAdapter)

    # Services
    worktree_service = providers.Factory(
        WorktreeService,
        git=git,
        tmux=tmux,
        filesystem=filesystem,
    )

# CLI with auto-injection
@app.command
@inject
def new(
    name: str,
    service: WorktreeService = Provide[Container.worktree_service],
):
    service.create(name)

# Bootstrap
def main():
    container = Container()
    container.config.from_yaml("config.yaml")
    container.wire(modules=[__name__])
    app()

# Testing
class TestContainer(containers.DeclarativeContainer):
    git = providers.Singleton(StubGitAdapter)
    tmux = providers.Singleton(StubTmuxAdapter)
    filesystem = providers.Singleton(FakeFileSystem)

    worktree_service = providers.Factory(
        WorktreeService,
        git=git,
        tmux=tmux,
        filesystem=filesystem,
    )

def test_create_worktree():
    container = TestContainer()
    container.wire(modules=[__name__])

    new("test")  # Uses test container automatically
```

### Decision Matrix

| Factor | Lightweight | Heavy Framework |
|--------|-------------|-----------------|
| **Project Size** | Small-Medium | Large |
| **Team Experience** | Any | DI-familiar |
| **Dependencies** | 0 | 1+ |
| **Boilerplate** | Low | Medium |
| **Flexibility** | High | Medium |
| **Type Safety** | Excellent | Good |
| **Learning Curve** | Minimal | Moderate |
| **Testability** | Excellent | Excellent |
| **Configuration** | Manual | Built-in |
| **Best For** | CLI tools, libraries | Web apps, services |

### Recommendation for claude-wt

**Use Lightweight Manual DI**:

1. **Reason**: claude-wt is a CLI tool, not a long-running service
2. **Size**: ~2000 LOC - manageable without framework
3. **Dependencies**: Currently minimal - keep it that way
4. **Team**: Solo/small team - avoid complexity
5. **Testing**: Already using mocks - easy to migrate to DI
6. **Type hints**: Python 3.10+ has excellent type hints - no need for framework

**Migration path**:
```python
# Phase 1: Extract adapters (no behavior change)
class GitAdapter:
    def run_command(self, args): ...

# Phase 2: Inject into services
class WorktreeService:
    def __init__(self, git: GitAdapter):
        self.git = git

# Phase 3: Create composition root
def create_service():
    return WorktreeService(GitAdapter())

# Phase 4: Update CLI commands
@app.command
def new(name: str):
    service = create_service()
    service.create(name)

# Phase 5: Update tests
def test_create():
    service = WorktreeService(StubGitAdapter())
    service.create("test")
```

---

## 10. How to Combine DI with Hexagonal/Onion Architecture

### Hexagonal Architecture Overview

**Core Concepts**:
- **Domain**: Pure business logic (entities, value objects)
- **Application**: Use cases, orchestration
- **Ports**: Interfaces for external dependencies
- **Adapters**: Implementations of ports
- **Infrastructure**: Framework, database, filesystem, etc.

**Dependency Rule**: Dependencies point inward
- Infrastructure depends on Application
- Application depends on Domain
- Domain depends on nothing

### Structure for claude-wt

```
claude_wt/
├── domain/                    # Core business logic
│   ├── __init__.py
│   ├── entities.py           # Worktree, Branch entities
│   └── value_objects.py      # BranchName, WorktreePath
├── application/              # Use cases
│   ├── __init__.py
│   ├── ports/                # Interfaces (abstract base classes)
│   │   ├── __init__.py
│   │   ├── git_port.py       # IGitRepository
│   │   ├── tmux_port.py      # ITmuxManager
│   │   └── filesystem_port.py # IFileSystem
│   └── use_cases/            # Application logic
│       ├── __init__.py
│       ├── create_worktree.py
│       ├── clean_worktree.py
│       └── list_worktrees.py
├── infrastructure/           # External dependencies
│   ├── __init__.py
│   ├── adapters/             # Port implementations
│   │   ├── __init__.py
│   │   ├── git_adapter.py
│   │   ├── tmux_adapter.py
│   │   └── filesystem_adapter.py
│   └── cli/                  # CLI framework
│       ├── __init__.py
│       └── cyclopts_app.py
└── bootstrap.py              # Dependency wiring
```

### Example Implementation

**1. Domain Layer** (Pure business logic):
```python
# domain/entities.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class BranchName:
    """Value object for branch names"""
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Branch name cannot be empty")
        if " " in self.value:
            raise ValueError("Branch name cannot contain spaces")

    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class WorktreePath:
    """Value object for worktree paths"""
    value: Path

    def __post_init__(self):
        if not self.value.is_absolute():
            raise ValueError("Worktree path must be absolute")

    def __str__(self) -> str:
        return str(self.value)

@dataclass
class Worktree:
    """Worktree entity"""
    path: WorktreePath
    branch: BranchName
    repo_root: Path

    def get_context_file_path(self) -> Path:
        return self.path.value / "CLAUDE.md"

    def create_context_content(self, query: str = "") -> str:
        return f"""# Worktree Context

Branch: {self.branch}
Path: {self.path}
Repository: {self.repo_root}

Query: {query}
"""
```

**2. Application Layer - Ports** (Interfaces):
```python
# application/ports/git_port.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

class IGitRepository(Protocol):
    """Port for git operations"""

    def get_repo_root(self) -> Path:
        """Get repository root directory"""
        ...

    def get_current_branch(self) -> str:
        """Get current branch name"""
        ...

    def create_worktree(self, path: Path, branch: str, source_branch: str) -> None:
        """Create a new worktree"""
        ...

    def remove_worktree(self, path: Path) -> None:
        """Remove a worktree"""
        ...

    def delete_branch(self, branch: str) -> None:
        """Delete a branch"""
        ...

# application/ports/tmux_port.py
class ITmuxManager(Protocol):
    """Port for tmux operations"""

    def is_in_tmux(self) -> bool:
        """Check if running in tmux"""
        ...

    def create_session(self, name: str, cwd: Path) -> None:
        """Create tmux session"""
        ...

    def switch_to_session(self, name: str) -> None:
        """Switch to session"""
        ...

# application/ports/filesystem_port.py
class IFileSystem(Protocol):
    """Port for filesystem operations"""

    def write_file(self, path: Path, content: str) -> None:
        """Write content to file"""
        ...

    def read_file(self, path: Path) -> str:
        """Read file content"""
        ...

    def exists(self, path: Path) -> bool:
        """Check if path exists"""
        ...
```

**3. Application Layer - Use Cases**:
```python
# application/use_cases/create_worktree.py
from dataclasses import dataclass
from pathlib import Path
from ..ports.git_port import IGitRepository
from ..ports.tmux_port import ITmuxManager
from ..ports.filesystem_port import IFileSystem
from ...domain.entities import Worktree, BranchName, WorktreePath

@dataclass
class CreateWorktreeCommand:
    """Command to create a worktree"""
    name: str
    query: str = ""
    branch: str = ""

@dataclass
class CreateWorktreeResult:
    """Result of creating a worktree"""
    worktree: Worktree
    success: bool
    message: str

class CreateWorktreeUseCase:
    """Use case for creating a new worktree"""

    def __init__(
        self,
        git: IGitRepository,
        tmux: ITmuxManager,
        filesystem: IFileSystem,
    ):
        self.git = git
        self.tmux = tmux
        self.filesystem = filesystem

    def execute(self, command: CreateWorktreeCommand) -> CreateWorktreeResult:
        """Execute the use case"""
        # Get repository info
        repo_root = self.git.get_repo_root()
        current_branch = self.git.get_current_branch()
        source_branch = command.branch or current_branch

        # Create domain objects
        branch_name = BranchName(f"claude-wt-{command.name}")
        wt_path = WorktreePath(
            Path.home() / "dev" / "claude-wt-worktrees" / f"{repo_root.name}-{command.name}"
        )

        # Create worktree entity
        worktree = Worktree(
            path=wt_path,
            branch=branch_name,
            repo_root=repo_root,
        )

        # Execute git operations
        self.git.create_worktree(
            wt_path.value,
            str(branch_name),
            source_branch,
        )

        # Create context file
        context_path = worktree.get_context_file_path()
        context_content = worktree.create_context_content(command.query)
        self.filesystem.write_file(context_path, context_content)

        # Create tmux session
        self.tmux.create_session(f"wt-{command.name}", wt_path.value)

        return CreateWorktreeResult(
            worktree=worktree,
            success=True,
            message=f"Created worktree at {wt_path}",
        )

# application/use_cases/clean_worktree.py
class CleanWorktreeUseCase:
    """Use case for cleaning worktrees"""

    def __init__(
        self,
        git: IGitRepository,
        tmux: ITmuxManager,
    ):
        self.git = git
        self.tmux = tmux

    def execute(self, branch_name: str) -> bool:
        """Clean a worktree by branch name"""
        # Find and remove worktree
        # Delete branch
        # Kill tmux session
        pass
```

**4. Infrastructure Layer - Adapters**:
```python
# infrastructure/adapters/git_adapter.py
import subprocess
from pathlib import Path
from typing import Protocol

class SubprocessRunner(Protocol):
    def run(self, args, **kwargs): ...

class GitAdapter:
    """Adapter implementing IGitRepository port"""

    def __init__(self, subprocess_runner: SubprocessRunner = None):
        self.subprocess = subprocess_runner or subprocess

    def get_repo_root(self) -> Path:
        result = self.subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())

    def get_current_branch(self) -> str:
        result = self.subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def create_worktree(self, path: Path, branch: str, source_branch: str) -> None:
        self.subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(path), source_branch],
            check=True,
        )

    def remove_worktree(self, path: Path) -> None:
        self.subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],
            check=True,
        )

    def delete_branch(self, branch: str) -> None:
        self.subprocess.run(
            ["git", "branch", "-D", branch],
            check=True,
        )

# infrastructure/adapters/tmux_adapter.py
class TmuxAdapter:
    """Adapter implementing ITmuxManager port"""

    def __init__(self, subprocess_runner: SubprocessRunner = None):
        self.subprocess = subprocess_runner or subprocess

    def is_in_tmux(self) -> bool:
        import os
        return os.environ.get("TMUX") is not None

    def create_session(self, name: str, cwd: Path) -> None:
        self.subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", str(cwd)],
            check=True,
        )

    def switch_to_session(self, name: str) -> None:
        self.subprocess.run(
            ["tmux", "switch-client", "-t", name],
            check=True,
        )

# infrastructure/adapters/filesystem_adapter.py
class FileSystemAdapter:
    """Adapter implementing IFileSystem port"""

    def write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def read_file(self, path: Path) -> str:
        return path.read_text()

    def exists(self, path: Path) -> bool:
        return path.exists()
```

**5. Bootstrap / Composition Root**:
```python
# bootstrap.py
from infrastructure.adapters.git_adapter import GitAdapter
from infrastructure.adapters.tmux_adapter import TmuxAdapter
from infrastructure.adapters.filesystem_adapter import FileSystemAdapter
from application.use_cases.create_worktree import CreateWorktreeUseCase
from application.use_cases.clean_worktree import CleanWorktreeUseCase

class Dependencies:
    """Container for all dependencies"""

    def __init__(self):
        # Create adapters
        self.git = GitAdapter()
        self.tmux = TmuxAdapter()
        self.filesystem = FileSystemAdapter()

        # Create use cases
        self.create_worktree = CreateWorktreeUseCase(
            git=self.git,
            tmux=self.tmux,
            filesystem=self.filesystem,
        )

        self.clean_worktree = CleanWorktreeUseCase(
            git=self.git,
            tmux=self.tmux,
        )

# Global instance (created once)
_deps = None

def get_dependencies() -> Dependencies:
    """Get or create dependencies"""
    global _deps
    if _deps is None:
        _deps = Dependencies()
    return _deps
```

**6. CLI Layer**:
```python
# infrastructure/cli/cyclopts_app.py
from cyclopts import App
from rich.console import Console
from bootstrap import get_dependencies
from application.use_cases.create_worktree import CreateWorktreeCommand

app = App()
console = Console()

@app.command
def new(name: str, query: str = "", branch: str = ""):
    """Create new worktree"""
    deps = get_dependencies()

    command = CreateWorktreeCommand(
        name=name,
        query=query,
        branch=branch,
    )

    result = deps.create_worktree.execute(command)

    if result.success:
        console.print(f"[green]{result.message}[/green]")
        console.print(f"[cyan]Path:[/cyan] {result.worktree.path}")
        console.print(f"[cyan]Branch:[/cyan] {result.worktree.branch}")
    else:
        console.print(f"[red]Error: {result.message}[/red]")
        raise SystemExit(1)

@app.command
def clean(branch_name: str):
    """Clean worktree"""
    deps = get_dependencies()

    success = deps.clean_worktree.execute(branch_name)

    if success:
        console.print(f"[green]Cleaned worktree for {branch_name}[/green]")
    else:
        console.print(f"[red]Failed to clean worktree[/red]")
        raise SystemExit(1)

if __name__ == "__main__":
    app()
```

**7. Testing**:
```python
# tests/test_create_worktree_use_case.py
import pytest
from pathlib import Path
from application.use_cases.create_worktree import (
    CreateWorktreeUseCase,
    CreateWorktreeCommand,
)
from tests.doubles.stub_git import StubGitRepository
from tests.doubles.stub_tmux import StubTmuxManager
from tests.doubles.fake_filesystem import FakeFileSystem

def test_create_worktree_creates_branch():
    # ARRANGE
    git = StubGitRepository(repo_root=Path("/home/user/repo"))
    tmux = StubTmuxManager()
    fs = FakeFileSystem()

    use_case = CreateWorktreeUseCase(git, tmux, fs)

    command = CreateWorktreeCommand(
        name="my-feature",
        query="Implement new feature",
    )

    # ACT
    result = use_case.execute(command)

    # ASSERT
    assert result.success
    assert result.worktree.branch.value == "claude-wt-my-feature"
    assert "my-feature" in str(result.worktree.path)

    # Verify git operations
    assert len(git.worktrees_created) == 1
    created_wt = git.worktrees_created[0]
    assert created_wt["branch"] == "claude-wt-my-feature"

    # Verify tmux session
    assert len(tmux.sessions_created) == 1
    assert tmux.sessions_created[0][0] == "wt-my-feature"

    # Verify context file
    context_path = result.worktree.get_context_file_path()
    assert fs.exists(context_path)
    content = fs.read_file(context_path)
    assert "Implement new feature" in content

# tests/doubles/stub_git.py
class StubGitRepository:
    """Stub implementation of IGitRepository"""

    def __init__(self, repo_root: Path = Path("/test/repo")):
        self.repo_root = repo_root
        self.current_branch = "main"
        self.worktrees_created = []
        self.worktrees_removed = []
        self.branches_deleted = []

    def get_repo_root(self) -> Path:
        return self.repo_root

    def get_current_branch(self) -> str:
        return self.current_branch

    def create_worktree(self, path: Path, branch: str, source_branch: str) -> None:
        self.worktrees_created.append({
            "path": path,
            "branch": branch,
            "source": source_branch,
        })

    def remove_worktree(self, path: Path) -> None:
        self.worktrees_removed.append(path)

    def delete_branch(self, branch: str) -> None:
        self.branches_deleted.append(branch)
```

### Benefits of Hexagonal + DI

1. **Clear Separation**: Business logic separate from infrastructure
2. **Testability**: Test core logic without external dependencies
3. **Flexibility**: Swap implementations easily
4. **Maintainability**: Changes in one layer don't affect others
5. **Domain Focus**: Core logic is pure Python, no framework dependencies

### Trade-offs

1. **More Files**: More structure = more files
2. **Indirection**: More layers to navigate
3. **Overkill for Simple Apps**: May be too much for small CLIs

### Recommendation for claude-wt

**Lightweight Hexagonal Approach**:
- Keep domain layer minimal (value objects for paths/names)
- Use protocols (duck typing) instead of ABC
- Combine application + domain in one layer for simplicity
- Focus on separating adapters from business logic
- Don't over-engineer - add structure as needed

---

## 11. Summary and Recommendations

### For claude-wt Specifically

**Recommended Approach**: **Lightweight Manual DI with Adapter Pattern**

**Rationale**:
1. **Size**: ~2000 LOC - doesn't need heavy framework
2. **Type**: CLI tool - simple lifecycle
3. **Team**: Solo/small - avoid complexity
4. **Dependencies**: Keep minimal
5. **Testability**: Major improvement over mocking
6. **Maintainability**: Clear dependencies

**Implementation Steps**:

1. **Create Adapter Layer** (Week 1):
   ```python
   # adapters/git.py
   class GitAdapter:
       def __init__(self, subprocess_runner=None):
           self.subprocess = subprocess_runner or subprocess

       def get_repo_root(self) -> Path: ...
       def create_worktree(self, path, branch, source): ...
   ```

2. **Create Service Layer** (Week 2):
   ```python
   # services/worktree.py
   class WorktreeService:
       def __init__(self, git: GitAdapter, tmux: TmuxAdapter):
           self.git = git
           self.tmux = tmux
   ```

3. **Create Composition Root** (Week 2):
   ```python
   # bootstrap.py
   def create_worktree_service() -> WorktreeService:
       return WorktreeService(
           git=GitAdapter(),
           tmux=TmuxAdapter(),
       )
   ```

4. **Update CLI Commands** (Week 3):
   ```python
   @app.command
   def new(name: str):
       service = create_worktree_service()
       service.create(name)
   ```

5. **Update Tests** (Week 3):
   ```python
   def test_create_worktree():
       service = WorktreeService(
           git=StubGitAdapter(),
           tmux=StubTmuxAdapter(),
       )
       service.create("test")
   ```

### General Recommendations

**For Small CLI Tools** (<5000 LOC):
- Use manual DI
- Constructor injection
- Simple composition root
- Stub/fake test doubles

**For Medium Applications** (5000-20000 LOC):
- Consider dependency-injector if complexity warrants it
- Use protocols for interfaces
- Add lightweight hexagonal structure
- Mix stubs and mocks

**For Large Applications** (>20000 LOC):
- Use dependency-injector or similar
- Full hexagonal architecture
- Comprehensive test double strategy
- Configuration management

### Key Principles

1. **Favor composition over inheritance**
2. **Constructor injection by default**
3. **Explicit dependencies always**
4. **Avoid service locator pattern**
5. **Test without frameworks when possible**
6. **Keep it simple until complexity demands more**

---

## 12. References and Resources

### Official Documentation

- **dependency-injector**: https://python-dependency-injector.ets-labs.org/
- **punq**: https://github.com/bobthemighty/punq
- **injector**: https://github.com/python-injector/injector
- **Click**: https://click.palletsprojects.com/
- **Typer**: https://typer.tiangolo.com/
- **Cyclopts**: https://github.com/BrianPugh/cyclopts

### Books and Articles

- **Cosmic Python** (Architecture Patterns with Python): https://www.cosmicpython.com/
  - Chapter 13: Dependency Injection and Bootstrapping
- **Clean Architecture** by Robert C. Martin
- **Dependency Injection Principles, Practices, and Patterns** by Mark Seemann

### Blog Posts

- "Service Locator is an Anti-Pattern" by Mark Seemann: https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/
- "Dependency Injection in Python" by Better Stack: https://betterstack.com/community/guides/scaling-python/python-dependency-injection/
- "Hexagonal Architecture in Python" by Douwe van der Meij: https://douwevandermeij.medium.com/hexagonal-architecture-in-python-7468c2606b63
- "Testing in Python: Dependency Injection vs. Mocking": https://medium.com/better-programming/testing-in-python-dependency-injection-vs-mocking-5e542783cb20

### Code Examples

- **dependency-injector CLI Tutorial**: https://python-dependency-injector.ets-labs.org/tutorials/cli.html
- **Hexagonal Architecture Django**: https://github.com/BasicWolf/hexagonal-architecture-django
- **Comparison of Python DI Libraries**: https://github.com/orsinium-labs/dependency_injectors

### Python-Specific

- **PEP 544 – Protocols**: https://peps.python.org/pep-0544/
- **typing.Protocol documentation**: https://docs.python.org/3/library/typing.html#typing.Protocol
- **unittest.mock**: https://docs.python.org/3/library/unittest.mock.html

### Tools and Libraries

- **pytest**: https://docs.pytest.org/
- **mypy** (type checking): http://mypy-lang.org/
- **ruff** (linting): https://github.com/astral-sh/ruff

---

## Conclusion

Dependency Injection is a powerful pattern that significantly improves testability, maintainability, and flexibility of Python applications. For CLI tools like claude-wt, a **lightweight manual DI approach** provides the best balance of:

- Zero framework dependencies
- Clear, explicit code
- Excellent testability
- Minimal boilerplate
- Full type safety

The key is to:
1. Extract adapters for external dependencies (git, tmux, subprocess, filesystem)
2. Inject dependencies via constructors
3. Create a simple composition root
4. Use stubs/fakes for testing

This approach scales well and can be enhanced with a framework like dependency-injector if the project grows significantly.
