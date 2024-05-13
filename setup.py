from setuptools import setup, find_packages

setup(
    name='plexus',
    version='0.1.0',
    packages=find_packages(),
    package_data={
        'plexus': ['templates/*', '__main__.py'],
    },
    entry_points={
        'console_scripts': [
            'plexus=plexus.cli.CommandLineInterface:main',
        ],
    },
    install_requires=[
        'python-dotenv==1.0.0',
        'typer[all]==0.9.0',
        'pandas==2.1.4',
        'openai==1.6.1',
        'tenacity==8.2.3',
        'nltk',
        'pybind11',
        'fasttext',
        'tiktoken',
        'seaborn',
        'litellm',
        'boto3',
        'graphviz',
        'mistune',
        'pyyaml',
        'sphinx'
    ],
    dependency_links=[
        'git+https://github.com/Anth-us/openai_cost_calculator.git@main#egg=openai-cost-calculator'
    ]
)