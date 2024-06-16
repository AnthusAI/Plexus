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
        'pydot==2.0.0',
        'pydotplus==2.0.2',
        'graphviz==0.20.3',
        'litellm',
        'boto3',
        'graphviz',
        'mistune',
        'pyyaml',
        'sphinx',
        'sphinx-rtd-theme',
        'mlflow',
        'scikit-learn',
        'tables',
        'keras==2.15.0'
        'tensorflow==2.15.1',
        'tensorboard==2.15.2',
        'tensorboard-plugin-profile==2.15.1'
    ],
    dependency_links=[
        'git+https://github.com/Anth-us/openai_cost_calculator.git@main#egg=openai-cost-calculator'
    ]
)