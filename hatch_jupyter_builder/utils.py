import importlib
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from shutil import which
from typing import Any, Callable, Dict, List, Optional, Union

if sys.platform == "win32":  # pragma: no cover
    from subprocess import list2cmdline
else:
    import pipes

    def list2cmdline(cmd_list):
        return " ".join(map(pipes.quote, cmd_list))


log = logging.getLogger(__name__)


def npm_builder(
    target_name: str,
    version: str,
    path: str = ".",
    build_dir: Optional[str] = None,
    source_dir: Optional[str] = None,
    build_cmd: Optional[str] = "build",
    force: bool = False,
    npm: Optional[Union[str, List]] = None,
    editable_build_cmd: Optional[str] = None,
) -> None:
    """Build function for managing an npm installation.
    Note: The function is a no-op if the `--skip-npm` cli flag is used
        or HATCH_JUPYTER_BUILDER_SKIP_NPM env is set.

    Parameters
    ----------
    target_name: str
        The build target name ("wheel" or "sdist").
    version: str
        The version name ("standard" or "editable").
    path: str, optional
        The base path of the node package. Defaults to the current directory.
    build_dir: str, optional
        The target build directory.  If this and source_dir are given,
        the JavaScript will only be built if necessary.
    source_dir: str, optional
        The source code directory.
    build_cmd: str, optional
        The npm command to build assets to the build_dir.
    editable_build_cmd: str, optional.
        The npm command to build assets to the build_dir when building in editable mode.
    npm: str or list, optional.
        The npm executable name, or a tuple of ['node', executable].
    """

    # Check if we are building a wheel from an sdist.
    abs_path = Path(path).resolve()

    if "--skip-npm" in sys.argv or os.environ.get("HATCH_JUPYTER_BUILDER_SKIP_NPM") == "1":
        log.info("Skipping npm install as requested.")
        skip_npm = True
        if "--skip-npm" in sys.argv:
            sys.argv.remove("--skip-npm")
    else:
        skip_npm = False

    is_git_checkout = (abs_path / ".git").exists()
    if target_name == "wheel" and not is_git_checkout and not force:
        skip_npm = True

    if skip_npm:
        log.info("Skipping npm-installation")
        return

    if version == "editable":
        build_cmd = editable_build_cmd or build_cmd

    if isinstance(npm, str):
        npm = [npm]

    # Find a suitable default for the npm command.
    if npm is None:
        is_yarn = (abs_path / "yarn.lock").exists()
        if is_yarn and not which("yarn"):
            log.warning("yarn not found, ignoring yarn.lock file")
            is_yarn = False

        if is_yarn:
            npm = ["yarn"]
        else:
            npm = ["npm"]

    npm_cmd = normalize_cmd(npm)

    if build_dir and source_dir and not force:
        should_build = is_stale(build_dir, source_dir)
    else:
        should_build = True

    if should_build:
        log.info("Installing build dependencies with npm.  This may take a while...")
        run(npm_cmd + ["install"], cwd=str(abs_path))
        if build_cmd:
            run(npm_cmd + ["run", build_cmd], cwd=str(abs_path))


def is_stale(target: Union[str, Path], source: Union[str, Path]) -> bool:
    """Test whether the target file/directory is stale based on the source
    file/directory.
    """
    if not Path(source).exists():
        return False
    if not Path(target).exists():
        return True
    target_mtime = recursive_mtime(target) or 0
    return compare_recursive_mtime(source, cutoff=target_mtime)


def compare_recursive_mtime(path: Union[str, Path], cutoff: float, newest: bool = True) -> bool:
    """Compare the newest/oldest mtime for all files in a directory.
    Cutoff should be another mtime to be compared against. If an mtime that is
    newer/older than the cutoff is found it will return True.
    E.g. if newest=True, and a file in path is newer than the cutoff, it will
    return True.
    """
    path = Path(path)
    if path.is_file():
        mt = mtime(path)
        if newest:
            if mt > cutoff:
                return True
        elif mt < cutoff:
            return True
    for dirname, _, filenames in os.walk(str(path), topdown=False):
        for filename in filenames:
            mt = mtime(Path(dirname) / filename)
            if newest:  # Put outside of loop?
                if mt > cutoff:
                    return True
            elif mt < cutoff:
                return True
    return False


def recursive_mtime(path: Union[str, Path], newest: bool = True) -> float:
    """Gets the newest/oldest mtime for all files in a directory."""
    path = Path(path)
    if path.is_file():
        return mtime(path)
    current_extreme = -1.0
    for dirname, _, filenames in os.walk(str(path), topdown=False):
        for filename in filenames:
            mt = mtime(Path(dirname) / filename)
            if newest:  # Put outside of loop?
                if mt >= (current_extreme or mt):
                    current_extreme = mt
            elif mt <= (current_extreme or mt):
                current_extreme = mt
    return current_extreme


def mtime(path: Union[str, Path]) -> float:
    """shorthand for mtime"""
    return Path(path).stat().st_mtime


def get_build_func(build_func_str: str) -> Callable[..., None]:
    # Get the build function by importing it.
    mod_name, _, func_name = build_func_str.rpartition(".")

    # If the module fails to import, try importing as a local script.
    try:
        sys.path.insert(0, str(Path.cwd()))
        mod = importlib.import_module(mod_name)
    finally:
        sys.path.pop(0)

    return getattr(mod, func_name)


def normalize_cmd(cmd: Union[str, list]) -> List[str]:
    if not isinstance(cmd, (list, tuple)):
        cmd = shlex.split(cmd, posix=os.name != "nt")
    if not Path(cmd[0]).is_absolute():
        # If a command is not an absolute path find it first.
        cmd_path = which(cmd[0])
        if not cmd_path:
            raise ValueError(
                f"Aborting. Could not find cmd ({cmd[0]}) in path. "
                "If command is not expected to be in user's path, "
                "use an absolute path."
            )
        cmd[0] = cmd_path
    return cmd


def normalize_kwargs(kwargs: Dict[str, str]) -> Dict[str, str]:
    """Normalize the key names in a kwargs input dictionary"""
    for key in list(kwargs):
        if "-" in key:
            kwargs[key.replace("-", "_")] = kwargs[key]
            del kwargs[key]
    return kwargs


def run(cmd: Union[str, list], **kwargs: Any) -> int:
    """Echo a command before running it."""
    kwargs.setdefault("shell", os.name == "nt")
    cmd = normalize_cmd(cmd)
    log.info(f"> {list2cmdline(cmd)}")
    return subprocess.check_call(cmd, **kwargs)


def ensure_targets(ensured_targets: List[str]) -> None:
    """Ensure that target files are available"""
    for target in ensured_targets:
        if not Path(target).exists():
            raise ValueError(f'Ensured target "{target}" does not exist')
