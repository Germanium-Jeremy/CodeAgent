from pathlib import Path


def resolve_project_path(file_path: str, project_root: Path) -> Path:
    """Resolve a relative path and reject anything outside the project root."""
    # Model arguments must be non-empty relative paths, never arbitrary absolute paths.
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("the path must be a non-empty string")

    # Reject absolute paths and explicit parent directory traversal patterns before resolution.
    if Path(file_path).is_absolute() or ".." in file_path:
        raise ValueError("use a path relative to the project root and avoid '..' traversal")

    requested_path = Path(file_path)

    # Resolve symlinks before checking containment so they cannot escape the root.
    resolved_root = project_root.resolve()
    resolved_path = (resolved_root / requested_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError("the requested path is outside the project root")

    return resolved_path
