import click

from build.build import build as _build
from build.dev_server import run
from build.logging_config import configure_logging

# Configure logging
configure_logging()


@click.group()
def cli():
    pass


@cli.command()
def build():
    _build()


@cli.command()
def serve():
    run()


if __name__ == "__main__":
    cli()

