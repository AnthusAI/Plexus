from setuptools import setup, find_packages

setup(
    name="plexus-dashboard",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "python-dotenv",
        "gql[requests]>=3.0.0",
        "boto3",
        "requests_aws4auth",
    ],
    entry_points={
        "console_scripts": [
            "plexus-dashboard=plexus_dashboard.cli:cli",
        ],
    },
) 