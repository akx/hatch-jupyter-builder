import os
from unittest.mock import call

import pytest

from hatch_jupyter_builder import npm_builder


@pytest.fixture
def repo(tmp_path):
    os.makedirs(os.path.join(tmp_path, ".git"))
    return tmp_path


def test_npm_builder(mocker, repo):
    which = mocker.patch("hatch_jupyter_builder.utils.which")
    run = mocker.patch("hatch_jupyter_builder.utils.run")
    which.return_value = "foo"
    npm_builder("wheel", "standard", path=repo)
    run.assert_has_calls(
        [call(["foo", "install"], cwd=str(repo)), call(["foo", "run", "build"], cwd=str(repo))]
    )


def test_npm_build_skip(mocker, repo):
    which = mocker.patch("hatch_jupyter_builder.utils.which")
    run = mocker.patch("hatch_jupyter_builder.utils.run")
    os.environ["HATCH_JUPYTER_BUILDER_SKIP_NPM"] = "1"
    which.return_value = "foo"
    npm_builder("wheel", "standard", path=repo)
    run.assert_not_called()
    del os.environ["HATCH_JUPYTER_BUILDER_SKIP_NPM"]


def test_npm_builder_yarn(mocker, repo):
    which = mocker.patch("hatch_jupyter_builder.utils.which")
    run = mocker.patch("hatch_jupyter_builder.utils.run")
    repo.joinpath("yarn.lock").write_text("hello")
    which.return_value = "foo"
    npm_builder("wheel", "standard", path=repo)
    run.assert_has_calls(
        [
            call(["foo", "install"], cwd=str(repo)),
            call(["foo", "run", "build"], cwd=str(repo)),
        ]
    )


def test_npm_builder_missing_yarn(mocker, repo):
    which = mocker.patch("hatch_jupyter_builder.utils.which")
    run = mocker.patch("hatch_jupyter_builder.utils.run")
    repo.joinpath("yarn.lock").write_text("hello")
    which.side_effect = ["", "foo"]
    npm_builder("wheel", "standard", path=repo)
    run.assert_has_calls(
        [
            call(["foo", "install"], cwd=str(repo)),
            call(["foo", "run", "build"], cwd=str(repo)),
        ]
    )


def test_npm_builder_not_stale(mocker, repo):
    which = mocker.patch("hatch_jupyter_builder.utils.which")
    run = mocker.patch("hatch_jupyter_builder.utils.run")
    is_stale = mocker.patch("hatch_jupyter_builder.utils.is_stale")
    is_stale.return_value = False
    which.return_value = "foo"
    npm_builder("wheel", "standard", path=repo, build_dir=repo, source_dir=repo)
    run.assert_not_called()


def test_npm_builder_no_npm(mocker, repo):
    which = mocker.patch("hatch_jupyter_builder.utils.which")
    run = mocker.patch("hatch_jupyter_builder.utils.run")
    is_stale = mocker.patch("hatch_jupyter_builder.utils.is_stale")
    is_stale.return_value = False
    which.return_value = ""
    with pytest.raises(ValueError):
        npm_builder("wheel", "standard", path=repo)
    run.assert_not_called()
