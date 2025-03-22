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


INDEX_MD = "index.md"
NOTES_MD = "notes.md"


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
    def build_css_path(self) -> Path:
        return self.build_path / "css"

    @cached_property
    def build_js_path(self) -> Path:
        return self.build_path / "js"

    @cached_property
    def pages_path(self) -> Path:
        return self.root_path / "pages"

    @cached_property
    def dist_path(self) -> Path:
        return self.root_path / "dist"

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


def _is_dotfile(path: Path) -> bool:
    return path.name.startswith(".")


def _is_md(path: Path) -> bool:
    return path.suffix == ".md"


def _read_md(path: Path) -> str:
    assert _is_md(path), f"Expected {path} to be a markdown file"
    with open(path) as f:
        return f.read()


def _write_html(path: Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _copy_assets(ctx: _BuildContext) -> None:
    src_dirs: list[Path] = [ctx.build_css_path, ctx.build_js_path]
    while src_dirs:
        src_dir = src_dirs.pop()
        _ensure_dir(ctx.dist_path / src_dir.relative_to(ctx.build_path))
        for src_path in src_dir.iterdir():
            if _is_dotfile(src_path):
                continue
            if src_path.is_dir():
                src_dirs.append(src_path)
            else:
                dst_path = ctx.dist_path / src_path.relative_to(ctx.build_path)
                logger.info(f"Copying {src_path} -> {dst_path}")
                shutil.copy(src_path, dst_path)


def _gen_page(ctx: _BuildContext, src_path: Path) -> None:
    dst_path = (ctx.dist_path / src_path.relative_to(ctx.pages_path)).with_name("index.html")
    md_content = _read_md(src_path)
    html_content = mistune.html(md_content)
    page = ctx.base_template.render(
        # TODO: get title from front matter
        title="foo",
        env=ctx.env.value,
        content=html_content
    )

    ctx.update_sha(page.encode())
    logger.info(f"Generating {src_path} -> {dst_path}")
    _write_html(dst_path, page)


def _gen_pages(ctx: _BuildContext) -> None:
    src_dirs = [ctx.pages_path]
    while src_dirs:
        src_dir = src_dirs.pop()
        _ensure_dir(ctx.dist_path / src_dir.relative_to(ctx.pages_path))
        files: list[Path] = []
        for src_path in src_dir.iterdir():
            if _is_dotfile(src_path):
                continue
            if src_path.is_dir():
                src_dirs.append(src_path)
            else:
                files.append(src_path)

        for src_path in files:
            if src_path.name == INDEX_MD:
                _gen_page(ctx, src_path)
            elif src_path.name == NOTES_MD:
                pass
            else:
                dst_path = ctx.dist_path / src_path.relative_to(ctx.pages_path)
                logger.info(f"Copying {src_path} -> {dst_path}")
                shutil.copy(src_path, dst_path)


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

    logger.info("Copying assets")
    _copy_assets(ctx)

    logger.info("Generating pages")
    _gen_pages(ctx)

    _write_sha(ctx)

    logger.info("Build complete.")
