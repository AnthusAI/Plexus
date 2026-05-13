import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Configuration Files - Plexus Documentation',
  description: 'How to configure Plexus using YAML configuration files',
}

export default function ConfigurationPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Configuration Files</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to configure Plexus using YAML configuration files for managing environment variables and settings.
        This provides a more organized and maintainable alternative to using .env files.
      </p>

      <div className="space-y-8">

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuration File Locations</h2>
          <p className="text-muted-foreground mb-4">
            Plexus looks for configuration files in the following locations, in order of precedence:
          </p>

          <ol className="list-decimal pl-6 space-y-2 text-muted-foreground mb-6">
            <li><code>{'{project}'}/.plexus/config.yaml</code> (project-specific, highest priority)</li>
            <li><code>{'{project}'}/.plexus/config.yml</code></li>
            <li><code>~/.plexus/config.yaml</code> (user-wide configuration)</li>
            <li><code>~/.plexus/config.yml</code> (lowest priority)</li>
          </ol>

          <div className="bg-muted/50 border rounded-lg p-4">
            <h4 className="font-medium mb-2">💡 Recommendation</h4>
            <p className="text-muted-foreground mb-0">
              Use <code>.plexus/config.yaml</code> in your project directory for project-specific settings.
              This keeps your configuration version-controlled and consistent across team members.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting Started</h2>
          <p className="text-muted-foreground mb-4">
            The easiest way to get started is to copy the example configuration file:
          </p>

          <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
            <code>{`# Create the .plexus directory
mkdir -p .plexus

# Copy the example configuration
cp plexus.yaml.example .plexus/config.yaml

# Edit the configuration with your settings
nano .plexus/config.yaml`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuration Structure</h2>
          <p className="text-muted-foreground mb-4">
            The YAML configuration supports all Plexus environment variables organized in a hierarchical structure:
          </p>

          <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
        <code>{`# Environment and Debug Settings
environment: development  # development, staging, production
debug: false

# Core Plexus Configuration
plexus:
  api_url: https://your-plexus-instance.appsync-api.amazonaws.com/graphql
  api_key: da2-your-api-key-here
  app_url: https://plexus.anth.us
  account_key: your-account-key
  enable_batching: true
  
  # Optional: Change working directory when loading config
  # working_directory: /path/to/your/project

# AWS Configuration
aws:
  access_key_id: AKIA-YOUR-ACCESS-KEY
  secret_access_key: your-secret-access-key
  region_name: us-west-2
  
  # Storage Buckets (Amplify-generated bucket names)
  storage:
    report_block_details_bucket: "amplify-your-app-reportblockdetails-bucket"
    datasets_bucket: "amplify-your-app-datasets-bucket"
    task_attachments_bucket: "amplify-your-app-taskattachments-bucket"

# Celery Task Queue Configuration
celery:
  queue_name: plexus-celery-development
  result_backend_template: "dynamodb://{aws_access_key}:{aws_secret_key}@{aws_region_name}/plexus-action-development"

# AI/ML Service APIs
openai:
  api_key: sk-your-openai-api-key

anthropic:
  api_key: sk-ant-api03-your-anthropic-api-key

# Azure OpenAI Configuration
azure:
  api_key: your-azure-openai-key
  api_base: https://your-instance.openai.azure.com
  api_version: "2024-02-01"

# LangChain/LangSmith Configuration
langchain:
  api_key: lsv2_pt_your-langsmith-api-key
  endpoint: https://api.smith.langchain.com
  project: your-project-name
  tracing_v2: true`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How Configuration Loading Works</h2>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Precedence Order</h3>
              <p className="text-muted-foreground mb-3">
                Configuration is loaded with the following precedence (highest to lowest priority):
              </p>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li><strong>Environment variables</strong> - Always take highest priority</li>
                <li><strong>Project-level config</strong> - <code>.plexus/config.yaml</code> in current directory</li>
                <li><strong>User-level config</strong> - <code>~/.plexus/config.yaml</code> in home directory</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Automatic Loading</h3>
              <p className="text-muted-foreground mb-3">
                Configuration is automatically loaded when you use:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Plexus CLI commands (e.g., <code>plexus item last</code>)</li>
                <li>Plexus MCP server</li>
                <li>Python code that imports Plexus modules</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Configuration Logging</h3>
              <p className="text-muted-foreground mb-3">
                When configuration is loaded, you'll see a log message like:
              </p>
              <pre className="bg-muted p-4 rounded-lg">
                <code>Loaded Plexus configuration from 1 file(s): /project/.plexus/config.yaml - Set 34 environment variables</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Special Features</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Working Directory Change</h3>
              <p className="text-muted-foreground mb-3">
                You can specify a working directory in your configuration that will be set when the config loads:
              </p>
              <pre className="bg-muted p-4 rounded-lg">
                <code>{`plexus:
  working_directory: /path/to/your/project`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Template Variables</h3>
              <p className="text-muted-foreground mb-3">
                Some configuration values support template variables. For example, the Celery result backend
                can reference AWS credentials:
              </p>
              <pre className="bg-muted p-4 rounded-lg">
                <code>{`celery:
  result_backend_template: "dynamodb://{aws_access_key}:{aws_secret_key}@{aws_region_name}/table-name"`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Migration from .env Files</h2>
          <p className="text-muted-foreground mb-4">
            If you're currently using <code>.env</code> files, you can migrate to YAML configuration:
          </p>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step 1: Convert Variables</h3>
              <p className="text-muted-foreground mb-3">Transform your flat environment variables into the nested YAML structure:</p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h5 className="font-medium mb-2">Before (.env)</h5>
                  <pre className="bg-muted p-3 rounded text-sm">
            <code>{`PLEXUS_API_URL=https://api.example.com
PLEXUS_API_KEY=da2-key
AWS_ACCESS_KEY_ID=AKIA123
AWS_SECRET_ACCESS_KEY=secret
OPENAI_API_KEY=sk-key`}</code>
          </pre>
        </div>
                <div>
                  <h5 className="font-medium mb-2">After (config.yaml)</h5>
                  <pre className="bg-muted p-3 rounded text-sm">
            <code>{`plexus:
  api_url: https://api.example.com
  api_key: da2-key
aws:
  access_key_id: AKIA123
  secret_access_key: secret
openai:
  api_key: sk-key`}</code>
                  </pre>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Step 2: Test the Migration</h3>
              <p className="text-muted-foreground mb-3">
                Test that your configuration works by running a simple command:
              </p>
              <pre className="bg-muted p-4 rounded-lg">
                <code>plexus item last</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Step 3: Remove .env File (Optional)</h3>
              <p className="text-muted-foreground">
                Once you've verified the YAML configuration works, you can remove your <code>.env</code> file.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Security Best Practices</h2>
          <div className="bg-muted/50 border border-orange-200 rounded-lg p-4">
            <h4 className="font-medium mb-2">⚠️ Security Notice</h4>
            <ul className="text-muted-foreground space-y-1">
              <li>Never commit configuration files with real credentials to version control</li>
              <li>Use <code>.gitignore</code> to exclude <code>.plexus/config.yaml</code> from git</li>
              <li>Consider using separate config files for different environments</li>
              <li>Use environment variables for the most sensitive credentials in production</li>
            </ul>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Troubleshooting</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Configuration Not Loading</h3>
              <p className="text-muted-foreground mb-2">If your configuration isn't being loaded:</p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Check the file path and ensure it's in one of the expected locations</li>
                <li>Verify the YAML syntax is valid</li>
                <li>Look for configuration loading log messages</li>
                <li>Ensure the file has proper read permissions</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Missing Environment Variables</h3>
              <p className="text-muted-foreground mb-2">If you get "missing environment variables" errors:</p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Check that the YAML structure matches the expected format</li>
                <li>Verify that required fields like <code>aws.access_key_id</code> are present</li>
                <li>Make sure there are no typos in the configuration keys</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">YAML Syntax Errors</h3>
              <p className="text-muted-foreground mb-2">Common YAML syntax issues:</p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Ensure proper indentation (use spaces, not tabs)</li>
                <li>Quote strings that contain special characters</li>
                <li>Use consistent spacing around colons</li>
                <li>Validate your YAML using an online YAML validator</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <div className="bg-muted/50 border border-green-200 rounded-lg p-4">
            <h4 className="font-medium mb-2">✅ Next Steps</h4>
            <p className="text-muted-foreground mb-0">
              Once you have your configuration file set up, try running <code>plexus item last</code> to verify
              everything is working correctly. You can also explore the{' '}
              <a href="/documentation/concepts" className="text-blue-600 hover:text-blue-800">
                Concepts
              </a>{' '}
              section to learn more about how Plexus works.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}