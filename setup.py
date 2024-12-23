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
        'pytest==8.2.2',
        'pytest-cov==5.0.0',
        'python-dotenv==1.0.0',
        'pytest-watch==4.2.0',
        'pandas==2.1.4',
        'openai>=1.35.10',
        'tenacity==8.2.3',
        'nltk',
        'pybind11',
        'fasttext',
        'tiktoken==0.7.0',
        'transformers',
        'seaborn',
        'pydot==2.0.0',
        'pydotplus==2.0.2',
        'graphviz==0.20.3',
        'boto3',
        'graphviz',
        'mistune',
        'pyyaml',
        'sphinx',
        'sphinx-rtd-theme',
        'mlflow',
        'scikit-learn==1.5.1',
        'tables',
        'keras==2.15.0',
        'tensorflow==2.15.1',
        'tensorboard==2.15.2',
        'tensorboard-plugin-profile==2.15.1',
        'xgboost==2.0.3',
        'imbalanced-learn==0.12.3',
        'imblearn==0.0',
        'shap==0.45.1',
        'contractions==0.1.73',
        'langchain>=0.2.11',
        'langchain-core>=0.2.38',
        'langchain-community>=0.2.6',
        'langgraph>=0.2.53',
        'langchain-aws>=0.1.9',
        'langchain-openai>=0.1.14',
        'langchain-google-vertexai>=1.0.6',
        'langgraph-checkpoint-postgres==2.0.3',
        'openpyxl==3.1.5',
        'rapidfuzz==3.9.4',
        'datasets',
        'gensim',
        'watchtower',
        'pyairtable'
    ],
    dependency_links=[
        'git+https://github.com/Anth-us/openai_cost_calculator.git@main#egg=openai-cost-calculator',
        'git+https://github.com/AnthusAI/Plexus-Dashboard.git@main#egg=plexus-dashboard',
    ]
)