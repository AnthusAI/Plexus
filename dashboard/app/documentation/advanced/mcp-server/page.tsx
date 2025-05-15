'use client';

import Link from "next/link";

export default function McpServerPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <style jsx>{`
        .code-container {
          position: relative;
          overflow-x: auto;
          white-space: pre;
          -webkit-overflow-scrolling: touch;
        }
        
        .code-container::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 16px;
          background: linear-gradient(to right, transparent, var(--background-muted));
          opacity: 0;
          transition: opacity 0.2s;
          pointer-events: none;
        }
        
        .code-container:hover::after {
          opacity: 1;
        }
      `}</style>

      <h1 className="text-4xl font-bold mb-4">Using the Plexus MCP Server</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Connect AI assistants like Claude to your Plexus data and functionality using the Model Context Protocol (MCP) server.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What is MCP?</h2>
          <p className="text-muted-foreground mb-4">
            The Model Context Protocol (MCP) is an open standard designed by Anthropic that allows AI models, such as Claude, 
            to securely interact with external tools and data sources. For an AI assistant, an MCP server acts as a gateway, 
            enabling it to access and use capabilities from other systems. In the context of Plexus, this means you can 
            empower an AI to work with your scorecards, evaluations, and reports directly. This allows for more dynamic and 
            powerful ways to interact with your Plexus instance. 
            For a deeper dive into the protocol itself, see the official <Link href="https://www.anthropic.com/news/model-context-protocol" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Anthropic Model Context Protocol announcement</Link>.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Plexus MCP Server Overview</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus MCP server is a pre-built tool that you can run on your system. Once running, it allows AI assistants 
            that support MCP (like the Claude desktop app) to connect to your Plexus environment. This connection lets the AI 
            perform various actions within Plexus on your behalf, such as listing scorecards, retrieving report details, or 
            even initiating new evaluations. The server is typically run via a wrapper script (<code>plexus_mcp_wrapper.py</code>) 
            which handles environment setup and ensures smooth communication with the AI client.
          </p>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting the Server Code</h2>
          <p className="text-muted-foreground mb-4">
            To run the Plexus MCP server, you'll first need to obtain the server code. This is available in the main Plexus GitHub repository. 
            You can clone or download it from: <Link href="https://github.com/AnthusAI/Plexus" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">https://github.com/AnthusAI/Plexus</Link>.
            The necessary scripts (<code>plexus_mcp_wrapper.py</code> and <code>plexus_fastmcp_server.py</code>) are typically located at <code>MCP/</code> within the repository.
            You will primarily need these files and to ensure their dependencies can be met in your Python environment.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Setting Up an MCP Client (e.g., Claude Desktop App)</h2>
          <p className="text-muted-foreground mb-2">
            To use the Plexus MCP server, you need an MCP client. For example, if you are using the Claude desktop application, 
            you would configure it by creating or editing an <code>mcp.json</code> file. This file tells Claude (or another client) 
            how to find and communicate with your running Plexus MCP server.
          </p>
          <p className="text-muted-foreground mb-2">
            Here is an example configuration for your <code>mcp.json</code> file. You will need to replace the placeholder paths 
            (<code>/path/to/...</code>) with the actual paths relevant to your system and where you have cloned the Plexus repository.
          </p>
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
{`{
  "mcpServers": {
    "plexus-mcp-service": {
      "command": "/path/to/your/conda/envs/py39/bin/python",
      "args": [
        "/path/to/your/Plexus/MCP/plexus_mcp_wrapper.py",
        "--transport", "stdio",
        "--env-file", "/path/to/your/Plexus/.env",
        "--target-cwd", "/path/to/your/Plexus/"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/your/Plexus"
      }
    }
  }
}`}
            </div>
          </pre>
          <p className="text-muted-foreground mb-1">Key parts of this configuration:</p>
          <ul className="list-disc pl-6 space-y-1 text-muted-foreground mb-4">
            <li><code>command</code>: The full path to the Python interpreter within your Plexus conda environment (e.g., <code>py39</code>).</li>
            <li><code>args</code>: Specifies the wrapper script to run (<code>plexus_mcp_wrapper.py</code>) and its parameters. 
                The <code>--transport stdio</code> argument is standard for client-server communication. 
                The <code>--env-file</code> argument must point directly to your <code>.env</code> file (which contains API keys). 
                The <code>--target-cwd</code> should point to your Plexus project root directory. Note that if your cloned repository is named `Plexus_2` or similar, use that name in the paths.</li>
            <li><code>env.PYTHONPATH</code>: Should point to the root of your Plexus project directory to ensure the server can find all necessary Python modules.</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            The location of the <code>mcp.json</code> file can vary depending on the client. For the Claude desktop app, consult its documentation for the correct location (often in a configuration directory within your user profile).
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Available Tools & Capabilities</h2>
          <p className="text-muted-foreground mb-4">Once the Plexus MCP server is running (via the wrapper script) and your AI assistant is connected, you can instruct the assistant to use the following tools:</p>
          
          <div>
            <h3 className="text-xl font-medium mb-2">Scorecard Management</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>list_plexus_scorecards</code></strong>: Ask the AI to list available scorecards in your Plexus Dashboard. 
                You can optionally tell it to filter by an account name/key, a partial scorecard name, or a scorecard key. For example: "List Plexus scorecards for the 'Sales' account that include 'Q3' in the name."
              </li>
              <li>
                <strong><code>get_plexus_scorecard_info</code></strong>: Request detailed information about a specific scorecard. 
                Provide the AI with an identifier for the scorecard (like its name, key, or ID). It will return the scorecard's description, sections, and the scores within each section. For example: "Get info for the 'Customer Satisfaction Q3' scorecard."
              </li>
              <li>
                <strong><code>get_plexus_score_details</code></strong>: Get specific details for a particular score within a scorecard, including its configuration and version history. 
                You'll need to specify both the scorecard and the score. You can also ask for a specific version of the score. For example: "Show me the details for the 'Responsiveness' score in the 'Support Tickets' scorecard, especially its champion version."
              </li>
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-xl font-medium mb-2">Evaluation Tools</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>run_plexus_evaluation</code></strong>: Instruct the AI to start a new scorecard evaluation. 
                You need to provide the scorecard name and optionally a specific score name and the number of samples. The server will dispatch this task to your Plexus backend. Note that the MCP server itself doesn't track the progress; you would monitor the evaluation in the Plexus Dashboard as usual. For example: "Run a Plexus evaluation for the 'Lead Quality' scorecard using 100 samples."
              </li>
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-xl font-medium mb-2">Reporting Tools</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>list_plexus_reports</code></strong>: Ask for a list of generated reports. You can filter by account or by a specific report configuration ID if you know it. 
                The AI will return a list showing report names, IDs, and when they were created. For example: "List the latest Plexus reports for the main account."
              </li>
              <li>
                <strong><code>get_plexus_report_details</code></strong>: Retrieve detailed information about a specific report by providing its ID. 
                This includes the report's parameters, output, and any generated blocks. For example: "Get the details for Plexus report ID '123-abc-456'."
              </li>
              <li>
                <strong><code>get_latest_plexus_report</code></strong>: A convenient way to get the details of the most recently generated report. 
                You can optionally filter by account or report configuration ID. For example: "Show me the latest report generated from the 'Weekly Performance' configuration."
              </li>
              <li>
                <strong><code>list_plexus_report_configurations</code></strong>: Get a list of all available report configurations for an account. 
                This is useful for knowing what reports you *can* generate. For example: "What report configurations are available for the 'Marketing' account?"
              </li>
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-xl font-medium mb-2">Utility Tools</h3>
            <ul className="list-disc pl-6 space-y-3 text-muted-foreground">
              <li>
                <strong><code>debug_python_env</code></strong>: A technical tool, mainly for troubleshooting if the server is having issues. 
                You can ask the AI to use this to check the server's Python environment, available modules, and paths. For example: "Debug the Python environment for the Plexus MCP server and check if the 'plexus.cli' module is available."
              </li>
              <li>
                <strong><code>hello_world</code></strong>: A simple test tool to verify the server is responsive and the AI can communicate with it. 
                For example: "Say hello to the Plexus MCP server with my name, John."
              </li>
            </ul>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Environment Requirements for Running the Server</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Software</h3>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li>Python 3.10 or newer (required by the <code>fastmcp</code> library the server uses).</li>
                <li>An existing Plexus installation and access to its dashboard credentials.</li>
                <li>The <code>python-dotenv</code> Python package (used by the server to load your API keys from the <code>.env</code> file).</li>
              </ul>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2"><code>.env</code> File with Plexus Credentials</h3>
              <p className="text-muted-foreground mb-2">
                The server needs to access your Plexus API. Create a file named <code>.env</code>. The <code>--env-file</code> parameter in your <code>mcp.json</code> should point directly to this file.
                It's typically located in your main Plexus project root directory (e.g., <code>Plexus/.env</code> or <code>Plexus_2/.env</code>).
              </p>
              <h4 className="text-lg font-medium mt-2 mb-1">Required Variables in <code>.env</code>:</h4>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li><code>PLEXUS_API_URL</code>: The API endpoint URL for your Plexus instance.</li>
                <li><code>PLEXUS_API_KEY</code>: Your API key for authenticating with Plexus.</li>
                <li><code>PLEXUS_DASHBOARD_URL</code>: The main URL of your Plexus dashboard (used for generating links).</li>
              </ul>
              <h4 className="text-lg font-medium mt-2 mb-1">Optional Variables in <code>.env</code>:</h4>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li><code>PLEXUS_ACCOUNT_KEY</code>: If you work with multiple accounts, you can set a default account key here.</li>
                <li><code>LOG_LEVEL</code>: You can set this to <code>DEBUG</code>, <code>INFO</code>, <code>WARNING</code>, or <code>ERROR</code> to control the server's logging verbosity.</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running the Server</h2>
          <p className="text-muted-foreground mb-2">
            Once you have the code and your <code>.env</code> file is set up, you should run the server using the <code>plexus_mcp_wrapper.py</code> script as configured in your <code>mcp.json</code> file. 
            The MCP client (e.g., Claude Desktop App) will execute the command specified in <code>mcp.json</code> when it attempts to connect to the "plexus-mcp-service".
          </p>
          <p className="text-muted-foreground mb-2">
            You typically don't run the <code>plexus_mcp_wrapper.py</code> script manually from the terminal for client use. Instead, ensure your <code>mcp.json</code> is correctly configured, and the client application will start the server process as needed.
          </p>
          <p className="text-muted-foreground mb-4">
            Make sure your Plexus Python environment (e.g., <code>conda activate py39</code>) is correctly referenced by the full path to python in the <code>command</code> field of your <code>mcp.json</code>. 
            The wrapper script handles passing the necessary environment variables and paths to the underlying <code>plexus_fastmcp_server.py</code>.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Troubleshooting Common Issues</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Connection Errors:</strong> Double-check all paths in your <code>mcp.json</code> file (<code>command</code>, <code>args</code>, <code>env.PYTHONPATH</code>). Ensure they accurately point to your Python executable, the <code>plexus_mcp_wrapper.py</code> script, your <code>.env</code> file, and your project directory.</li>
            <li><strong>Authentication Errors:</strong> Verify that the <code>--env-file</code> path in <code>mcp.json</code> correctly points to your <code>.env</code> file and that this file contains the correct <code>PLEXUS_API_URL</code> and <code>PLEXUS_API_KEY</code>.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Server Logs</h2>
          <p className="text-muted-foreground mb-2">
            The Plexus MCP server setup (via <code>plexus_mcp_wrapper.py</code>) directs operational logs and error messages to stderr. 
            MCP clients like the Claude desktop app typically capture and display these stderr logs, or store them in a dedicated log file.
          </p>
          <p className="text-muted-foreground mb-4">
            For instance, Cursor often stores MCP interaction logs in <code>~/Library/Logs/Claude/mcp.log</code> on macOS. Monitoring this file is key for diagnosing issues if the client doesn't display them directly.
          </p>
        </section>
      </div>
    </div>
  )
} 