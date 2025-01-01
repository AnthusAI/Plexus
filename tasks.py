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

@task
def dashboard_install(context):
    with context.cd("./dashboard"):
        context.run("npm ci")

@task
def dashboard_test(context):
    with context.cd("./dashboard"):
        context.run("npm run typecheck")
        context.run("npm run test:coverage")

@task
def docs(context):
    context.run("sphinx-apidoc --separate -o documentation/source plexus " \
               "\"**/*_test*.*\" -f -M")
    context.run("sphinx-build documentation/source documentation")

@task(pre=[lint, test, docs])
def ci(context):
    """Run all validation tasks: lint, test, and build docs"""
    pass 