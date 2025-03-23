import logging
import re
import shutil
import enum
from dataclasses import dataclass, field
from functools import cached_property
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional, Protocol, TYPE_CHECKING

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
BASE_HTML = "base.html"
BLOG_INDEX_HTML = "blog_index.html"
FRONT_MATTER_DELIM = "---"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class _PageType(enum.Enum):
    index = "index"
    blog_post = "blog_post"


@dataclass
class _PageMetadata:
    href: str
    page_type: _PageType
    title: str
    date: Optional[str] = None

    def __post_init__(self) -> None:
        assert self.href, "Page must have an href"
        assert self.title, "Page must have a title"
        if self.page_type == _PageType.blog_post:
            assert self.date is not None, "Blog post must have a date"
            assert DATE_RE.match(self.date), "Blog post date must be in the format YYYY-MM-DD"


class Hash(Protocol):
    def update(self, data: ReadableBuffer, /) -> None: ...
    def hexdigest(self) -> str: ...


@dataclass
class _BuildContext:
    env: Env
    root_path: Path
    build_sha: Hash
    blog_posts: list[_PageMetadata] = field(default_factory=list)

    @cached_property
    def build_path(self) -> Path:
        return self.root_path / "build"

    @cached_property
    def assets_path(self) -> Path:
        return self.root_path / "assets"

    @cached_property
    def templates_path(self) -> Path:
        return self.root_path / "templates"

    @cached_property
    def pages_path(self) -> Path:
        return self.root_path / "pages"

    @cached_property
    def blog_path(self) -> Path:
        return self.pages_path / "blog"

    @cached_property
    def dist_path(self) -> Path:
        return self.root_path / "dist"

    @cached_property
    def base_template(self) -> Template:
        with open(self.templates_path / BASE_HTML) as f:
            return Template(f.read())

    @property
    def blog_index_template(self) -> Template:
        with open(self.templates_path / BLOG_INDEX_HTML) as f:
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


def _parse_front_matter(src_path: Path, md_content: str) -> tuple[dict[str, str], str]:
    front_matter = {}
    lines = md_content.splitlines()
    if lines[0] != FRONT_MATTER_DELIM:
        raise ValueError(f"Page {src_path} is missing front matter")
    i = 1
    while lines[i] != FRONT_MATTER_DELIM:
        line = lines[i]
        key, value = line.split(":", 1)
        front_matter[key.strip()] = value.strip()
        i += 1

    return front_matter, "\n".join(lines[i + 1:])


def _read_md(path: Path) -> tuple[dict[str, str], str]:
    assert _is_md(path), f"Expected {path} to be a markdown file"
    with open(path) as f:
        raw_content = f.read()

    return _parse_front_matter(path, raw_content)


def _write_html(path: Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _copy_assets(ctx: _BuildContext) -> None:
    src_dirs: list[Path] = [ctx.assets_path]
    while src_dirs:
        src_dir = src_dirs.pop()
        _ensure_dir(ctx.dist_path / src_dir.relative_to(ctx.assets_path))
        for src_path in src_dir.iterdir():
            if _is_dotfile(src_path):
                continue
            if src_path.is_dir():
                src_dirs.append(src_path)
            else:
                dst_path = ctx.dist_path / src_path.relative_to(ctx.assets_path)
                logger.info(f"Copying {src_path} -> {dst_path}")
                shutil.copy(src_path, dst_path)


def _gen_page(ctx: _BuildContext, src_path: Path) -> None:
    dst_path = (ctx.dist_path / src_path.relative_to(ctx.pages_path)).with_name("index.html")

    front_matter, md_content = _read_md(src_path)
    page_meta = _PageMetadata(
        href = f"/{src_path.parent.relative_to(ctx.pages_path).as_posix()}/",
        page_type=_PageType(front_matter["page_type"]),
        title=front_matter["title"],
        date=front_matter.get("date"),
    )

    if page_meta.page_type == _PageType.blog_post:
        ctx.blog_posts.append(page_meta)

    html_content = mistune.html(md_content)
    assert isinstance(html_content, str)
    if src_path.parent == ctx.blog_path:
        html_content += ctx.blog_index_template.render(blog_posts=ctx.blog_posts)

    page = ctx.base_template.render(
        # Require front matter to have a title. Intentionally error if it doesn't.
        title=page_meta.title,
        env=ctx.env.value,
        date=page_meta.date,
        content=html_content
    )

    ctx.update_sha(page.encode())
    logger.info(f"Generating {src_path} -> {dst_path}")
    _write_html(dst_path, page)


def _gen_pages(ctx: _BuildContext, path: Optional[Path] = None, recurse: bool = True) -> None:
    if path is None:
        path = ctx.pages_path

    assert path.is_dir(), f"Expected {path} to be a directory"

    dst_path = ctx.dist_path / path.relative_to(ctx.pages_path)
    _ensure_dir(dst_path)

    files: list[Path] = []
    for src_path in path.iterdir():
        if _is_dotfile(src_path):
            continue
        if src_path.is_dir() and recurse:
            _gen_pages(ctx, src_path)
        if src_path.is_file():
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
