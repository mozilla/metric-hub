from setuptools import setup


def text_from_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


test_dependencies = [
    "coverage",
    "isort",
    "jsonschema",
    "pytest",
    "pytest-black",
    "pytest-cov",
    "pytest-flake8",
    "mypy",
    "types-futures",
    "types-pkg-resources",
    "types-protobuf",
    "types-pytz",
    "types-PyYAML",
    "types-requests",
    "types-six",
    "types-toml",
]

extras = {
    "testing": test_dependencies,
}

setup(
    name="mozilla-metric-config-parser",
    author="Mozilla Corporation",
    author_email="fx-data-dev@mozilla.org",
    description="Parses metric configuration files",
    url="https://github.com/mozilla/metric-config-parser",
    packages=[
        "metric_config_parser",
        "metric_config_parser.tests",
        "metric_config_parser.tests.integration",
    ],
    package_data={
        "metric_config_parser.tests": ["data/*"],
        "metric_config_parser": ["templates/*"],
    },
    install_requires=[
        "attrs",
        "cattrs",
        "Click",
        "GitPython",
        "jinja2",
        "pytz",
        "requests",
        "toml",
        "mozilla-nimbus-schemas",
    ],
    include_package_data=True,
    tests_require=test_dependencies,
    extras_require=extras,
    long_description=text_from_file("README.md"),
    long_description_content_type="text/markdown",
    python_requires=">=3.6",
    entry_points="""
        [console_scripts]
        metric-config-parser=metric_config_parser.cli:cli
    """,
    version="2024.5.2",
)
