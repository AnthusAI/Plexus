from invoke import task, Exit

@task
def install(context):
    context.run("python -m pip install --upgrade pip")
    context.run("pip install -e .")

@task
def lint(context):
    """Run flake8 linting using configuration from .flake8"""
    result = context.run("flake8 . --count --select=E9,F63,F7,F82 --statistics", warn=True)
    if result.ok:
        print("\n✅ Linting passed - no serious errors found!")
    else:
        print("\n❌ Linting failed - please fix the errors above")
        raise Exit(code=result.return_code)

@task
def test(context):
    context.run("pytest")

@task
def docs(context):
    context.run("sphinx-apidoc --separate -o documentation/source plexus " \
               "\"**/*_test*.*\" -f -M")
    context.run("sphinx-build documentation/source documentation")

@task(pre=[lint, test])
def ci(context):
    """Run all Python validation tasks: lint and test"""
    pass 