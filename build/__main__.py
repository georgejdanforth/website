import os
import shutil
from pathlib import Path
from jinja2 import Template

import mistune

def ensure_dir(dir_path):
    """Create directory if it doesn't exist"""
    if not dir_path.exists():
        dir_path.mkdir(parents=True)

if __name__ == "__main__":
    path = Path(".").resolve()
    # TODO: come up with a better way to do this.
    if path.name != "website":
        raise ValueError("Not in project root")

    # Define paths
    dist = path/"dist"
    dist_css = dist/"css"
    
    build = path/"build"
    template_path = build/"html"/"template.html"
    css_src = build/"css"/"styles.css"
    
    pages = path/"pages"
    index = pages/"index.md"

    # Delete and recreate dist dir if it exists
    if (dist.is_dir()):
        os.system(f"rm -rf {dist}")

    # Create needed directories
    ensure_dir(dist)
    ensure_dir(dist_css)

    # Copy CSS file to dist
    shutil.copy(css_src, dist_css/"styles.css")
    print(f"Copied stylesheet to {dist_css/'styles.css'}")

    # Read template
    with open(template_path) as f:
        template_content = f.read()
    
    template = Template(template_content)

    # Process index page
    with open(index) as f:
        content = f.read()

    # Convert markdown to HTML
    html_content = mistune.html(content)
    
    # Render the template with the content
    rendered_html = template.render(
        title="Home",
        content=html_content
    )

    # Write the output HTML
    index_html = dist/"index.html"
    with open(index_html, "w") as f:
        f.write(rendered_html)
    
    print(f"Built {index_html}")
