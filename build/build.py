import logging
import shutil
from dataclasses import dataclass
from functools import cached_property, wraps
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol, TYPE_CHECKING

import mistune
from jinja2 import Template

from build.env import Env

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer
else:
    ReadableBuffer = Any

logger = logging.getLogger(__name__)


class Hash(Protocol):
    def update(self, data: ReadableBuffer, /) -> None: ...
    def hexdigest(self) -> str: ...


@dataclass
class _BuildContext:
    env: Env
    root_path: Path
    build_sha: Hash

    @cached_property
    def build_path(self) -> Path:
        return self.root_path / "build"

    @cached_property
    def template_path(self) -> Path:
        return self.build_path / "html" / "template.html"

    @cached_property
    def stylesheet_path(self) -> Path:
        return self.build_path / "css" / "styles.css"

    @cached_property
    def js_path(self) -> Path:
        return self.build_path / "js"

    @cached_property
    def pages_path(self) -> Path:
        return self.root_path / "pages"

    @cached_property
    def index_md_path(self) -> Path:
        return self.pages_path / "index.md"

    @cached_property
    def dist_path(self) -> Path:
        return self.root_path / "dist"

    @cached_property
    def dist_css_path(self) -> Path:
        return self.dist_path / "css"

    @cached_property
    def dist_stylesheet_path(self) -> Path:
        return self.dist_css_path / "styles.css"

    @cached_property
    def dist_js_path(self) -> Path:
        return self.dist_path / "js"

    @cached_property
    def dist_index_path(self) -> Path:
        return self.dist_path / "index.html"

    @cached_property
    def base_template(self) -> Template:
        with open(self.template_path) as f:
            return Template(f.read())

    @cached_property
    def sha_path(self) -> Path:
        return self.dist_path / "sha256.txt"

    def get_sha(self) -> str:
        return self.build_sha.hexdigest()

    def update_sha(self, data: bytes) -> None:
        self.build_sha.update(data)


def _assert_project_root(path: Path) -> None:
    # TODO: also check for some file that should be in the project root
    if path.name != "website":
        raise ValueError("Not in project root")


def _ensure_dir(dir_path: Path) -> None:
    if not dir_path.exists():
        dir_path.mkdir(parents=True)
    elif not dir_path.is_dir():
        raise ValueError(f"Expected {dir_path} to be a directory")


def _clean_dist(ctx: _BuildContext) -> None:
    if not ctx.dist_path.exists():
        return
    if ctx.dist_path.is_dir():
        shutil.rmtree(ctx.dist_path)
    else:
        raise ValueError(f"Expected {ctx.dist_path} to be a directory")


def _copy_stylesheet(ctx: _BuildContext) -> None:
    shutil.copy(ctx.stylesheet_path, ctx.dist_stylesheet_path)


def _copy_js(ctx: _BuildContext) -> None:
    # TODO: filter scripts by environment
    shutil.copytree(ctx.js_path, ctx.dist_path / "js")


def _is_md(path: Path) -> bool:
    return path.suffix == ".md"


def _read_md(path: Path) -> str:
    assert _is_md(path), f"Expected {path} to be a markdown file"
    with open(path) as f:
        return f.read()


def _write_html(path: Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _page_fn(fn: Callable[[_BuildContext], str]) -> Callable[[_BuildContext], None]:
    @wraps(fn)
    def wrapper(ctx: _BuildContext) -> None:
        content = fn(ctx)
        ctx.update_sha(content.encode())
        _write_html(ctx.dist_index_path, content)

    return wrapper


@_page_fn
def _gen_index_html(ctx: _BuildContext) -> str:
    logger.info(f"Generating {ctx.index_md_path} -> {ctx.dist_index_path}")
    md_content = _read_md(ctx.index_md_path)
    html_content = mistune.html(md_content)
    return ctx.base_template.render(
        title="George Danforth",
        env=ctx.env.value,
        content=html_content
    )


def _write_sha(ctx: _BuildContext) -> None:
    sha = ctx.get_sha()
    logger.info(f"SHA256: {sha}")
    with open(ctx.sha_path, "w") as f:
        f.write(sha)


def build(env: Env) -> None:
    root_path = Path(".").resolve()
    _assert_project_root(root_path)

    logger.info(f"Starting build from {root_path}")

    ctx = _BuildContext(env, root_path, sha256())

    logger.info(f"Setting up dist dir at {ctx.dist_path}")
    _clean_dist(ctx)
    _ensure_dir(ctx.dist_path)
    _ensure_dir(ctx.dist_css_path)
    _copy_stylesheet(ctx)
    _copy_js(ctx)

    logger.info("Generating pages")
    _gen_index_html(ctx)

    _write_sha(ctx)

    logger.info("Build complete.")
