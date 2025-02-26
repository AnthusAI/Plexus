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
            <code>{`# List scorecards with optimized performance
plexus scorecards list "account-name" --fast

# View a specific scorecard by filtering
plexus scorecards list "account-name" --name "Content Quality"

# View detailed information about a score
plexus scorecards score "score-name" --account "account-name" --show-versions

# Coming soon:
# Create a new scorecard
plexus scorecards create --name "Content Quality" --description "Evaluates content quality"

# Add a score to the scorecard
plexus scorecards add-score scorecard-id --type sentiment --weight 0.5

# Update a scorecard
plexus scorecards update scorecard-id --name "Updated Name"`}</code>
          </pre>
          
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Performance Considerations</h3>
              <p className="text-muted-foreground">
                The CLI now uses optimized GraphQL queries to fetch scorecard data efficiently:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>
                  <strong>Single Query Approach:</strong> Instead of making separate queries for each scorecard's sections and scores, 
                  the system now fetches all data in a single comprehensive GraphQL query.
                </li>
                <li>
                  <strong>Fast Mode:</strong> Use the <code>--fast</code> option to skip fetching sections and scores when you only need basic scorecard information.
                </li>
                <li>
                  <strong>Hide Scores:</strong> Use <code>--hide-scores</code> to exclude score details from the output while still fetching basic scorecard data.
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic scorecard management, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Create a new scorecard
scorecard = plexus.scorecards.create(
    name="Content Quality",
    description="Evaluates content quality"
)

# Add a score
scorecard.add_score(
    type="sentiment",
    weight=0.5,
    threshold=0.7
)

# Update a scorecard
scorecard.update(name="Updated Name")`}</code>
          </pre>
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
            <li>YAML synchronization for offline editing</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 