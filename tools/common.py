from pathlib import Path


def resolve_project_path(file_path: str, project_root: Path) -> Path:
    """Resolve a relative path and reject anything outside the project root."""
    # Model arguments must be non-empty relative paths, never arbitrary absolute paths.
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("the path must be a non-empty string")

    requested_path = Path(file_path)
    if requested_path.is_absolute():
        raise ValueError("use a path relative to the project root")

    # Resolve symlinks before checking containment so they cannot escape the root.
    resolved_root = project_root.resolve()
    resolved_path = (resolved_root / requested_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError("the requested path is outside the project root")

    return resolved_path
