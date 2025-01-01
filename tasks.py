from invoke import task

@task
def install(context):
    context.run("python -m pip install --upgrade pip")
    context.run("pip install -e .")

@task
def lint(context):
    context.run("flake8 . --exclude=node_modules,dashboard/node_modules " \
               "--count --select=E9,F63,F7,F82 --show-source --statistics")
    context.run("flake8 . --exclude=node_modules,dashboard/node_modules " \
               "--count --exit-zero --max-complexity=10 " \
               "--max-line-length=127 --statistics")

@task
def test(context):
    context.run("pytest")

@task(pre=[lint, test])
def ci(context):
    """Run all Python validation tasks: lint and test"""
    pass 