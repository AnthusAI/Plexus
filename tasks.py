from invoke import task, Exit

@task
def install(context):
    context.run("poetry install --with dev")

@task
def lint(context):
    """Run flake8 linting using configuration from .flake8"""
    result = context.run("poetry run flake8 . --count --select=E9,F63,F7,F82 --statistics", warn=True)
    if result.ok:
        print("\n✅ Linting passed - no serious errors found!")
    else:
        print("\n❌ Linting failed - please fix the errors above")
        raise Exit(code=result.return_code)

@task
def test(context):
    context.run("poetry run pytest")

@task
def docs(context):
    context.run("poetry run sphinx-apidoc --separate -o documentation/source plexus " \
               "\"**/*_test*.*\" -f -M")
    context.run("poetry run sphinx-build documentation/source documentation")

@task(pre=[lint, test])
def ci(context):
    """Run all Python validation tasks: lint and test"""
    pass 
