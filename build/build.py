import shutil
from dataclasses import dataclass
from pathlib import Path
from functools import cached_property

import mistune
from jinja2 import Template

@dataclass
class _BuildContext:
    root_path: Path

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
    def dist_index_path(self) -> Path:
        return self.dist_path / "index.html"

    @cached_property
    def base_template(self) -> Template:
        with open(self.template_path) as f:
            return Template(f.read())


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


def _is_md(path: Path) -> bool:
    return path.suffix == ".md"


def _read_md(path: Path) -> str:
    assert _is_md(path), f"Expected {path} to be a markdown file"
    with open(path) as f:
        return f.read()


def _write_html(path: Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _gen_index_html(ctx: _BuildContext) -> None:
    md_content = _read_md(ctx.index_md_path)
    html_content = mistune.html(md_content)
    page = ctx.base_template.render(
        title="George Danforth",
        content=html_content
    )
    _write_html(ctx.dist_index_path, page)


def build() -> None:
    root_path = Path(".").resolve()
    _assert_project_root(root_path)

    ctx = _BuildContext(root_path)

    _clean_dist(ctx)
    _ensure_dir(ctx.dist_path)
    _ensure_dir(ctx.dist_css_path)
    _copy_stylesheet(ctx)

    _gen_index_html(ctx)
