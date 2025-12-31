"""Setup script for kryten-robot package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read version from pyproject.toml
version = "0.0.0"
pyproject_file = Path(__file__).parent / "pyproject.toml"
if pyproject_file.exists():
    with open(pyproject_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("version ="):
                version = line.split("=")[1].strip().strip('"')
                break

# Read long description from README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8")

# Read requirements from requirements.txt
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
for line in requirements_file.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#"):
        requirements.append(line)

setup(
    name="kryten-robot",
    version=version,
    description="CyTube to NATS bridge connector - publishes CyTube events to NATS message bus",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Kryten Robot Team",
    author_email="",
    url="https://github.com/grobertson/kryten-robot",
    project_urls={
        "Bug Tracker": "https://github.com/grobertson/kryten-robot/issues",
        "Documentation": "https://github.com/grobertson/kryten-robot/blob/main/README.md",
        "Source Code": "https://github.com/grobertson/kryten-robot",
    },
    packages=find_packages(exclude=["tests", "tests.*", "llm", "llm.*", "docs"]),
    package_data={
        "": ["README.md"],
    },
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "kryten-robot=kryten.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
    ],
    keywords="cytube nats bridge connector socketio microservices",
    license="MIT",
)
