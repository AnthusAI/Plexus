export default function AddEditScorecardPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Add/Edit a Scorecard</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to create and manage scorecards using the Plexus dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Creating a Scorecard in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Scorecards define the criteria for evaluating your content. The dashboard provides
            an intuitive interface for creating and managing scorecards.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Access Scorecards:</strong>
                  <p>Navigate to the "Scorecards" section in the main navigation menu.</p>
                </li>
                <li>
                  <strong>Create New Scorecard:</strong>
                  <p>Click the "New Scorecard" button in the top-right corner.</p>
                </li>
                <li>
                  <strong>Basic Information:</strong>
                  <p>Fill in the scorecard details:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Scorecard name</li>
                    <li>Description</li>
                    <li>Category/tags (optional)</li>
                  </ul>
                </li>
                <li>
                  <strong>Add Scores:</strong>
                  <p>Click "Add Score" to include evaluation criteria:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Select score type</li>
                    <li>Configure score parameters</li>
                    <li>Set weight and threshold</li>
                  </ul>
                </li>
                <li>
                  <strong>Save Scorecard:</strong>
                  <p>Click "Create" to save your new scorecard.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editing a Scorecard</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Find the Scorecard:</strong>
                  <p>Locate the scorecard you want to modify in the Scorecards list.</p>
                </li>
                <li>
                  <strong>Enter Edit Mode:</strong>
                  <p>Click the edit icon or select "Edit" from the actions menu.</p>
                </li>
                <li>
                  <strong>Make Changes:</strong>
                  <p>Modify scorecard details, add/remove scores, or adjust weights.</p>
                </li>
                <li>
                  <strong>Save Updates:</strong>
                  <p>Click "Save Changes" to apply your modifications.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scorecard Management Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Organization</h3>
              <p className="text-muted-foreground">
                Use meaningful names and descriptions to keep your scorecards organized.
                Consider using tags to group related scorecards.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Score Weights</h3>
              <p className="text-muted-foreground">
                Balance score weights to reflect the relative importance of each criterion
                in your evaluation process.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Templates</h3>
              <p className="text-muted-foreground">
                Save commonly used scorecard configurations as templates for quick reuse.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automated scorecard management, you can use the Plexus CLI:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# List all scorecards
plexus scorecards list

# Get detailed information about a specific scorecard
plexus scorecards info --scorecard "Content Quality"

# List all scores in a scorecard
plexus scorecards list-scores --scorecard "Content Quality"

# Pull scorecard configuration to YAML
plexus scorecards pull --scorecard "Content Quality" --output ./my-scorecards

# Push scorecard configuration from YAML
plexus scorecards push --file ./my-scorecard.yaml --update

# Delete a scorecard
plexus scorecards delete --scorecard "Content Quality"`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            The Plexus CLI uses a flexible identifier system that allows you to reference scorecards using different types of identifiers:
          </p>
          
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li>By name: <code>--scorecard "Content Quality"</code></li>
            <li>By key: <code>--scorecard content-quality</code></li>
            <li>By ID: <code>--scorecard e51cd5ec-1940-4d8e-abcc-faa851390112</code></li>
            <li>By external ID: <code>--scorecard cq-2023</code></li>
          </ul>
          
          <p className="text-muted-foreground">
            For more details on using the CLI, see the <a href="/documentation/advanced/cli" className="text-primary hover:underline">CLI documentation</a>.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic scorecard management, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Get a scorecard using any identifier (name, key, ID, or external ID)
scorecard = plexus.scorecards.get("Content Quality")

# List all scorecards
scorecards = plexus.scorecards.list()

# Get all scores in a scorecard
scores = scorecard.get_scores()

# Export scorecard to YAML
yaml_config = scorecard.to_yaml()
with open("scorecard.yaml", "w") as f:
    f.write(yaml_config)

# Import scorecard from YAML
with open("scorecard.yaml", "r") as f:
    yaml_content = f.read()
    
new_scorecard = plexus.scorecards.from_yaml(yaml_content)`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like the CLI, the Python SDK also supports the flexible identifier system, allowing you to reference scorecards using different types of identifiers.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional scorecard features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced score configuration options</li>
            <li>Scorecard version control</li>
            <li>Collaborative editing features</li>
            <li>Performance analytics</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 