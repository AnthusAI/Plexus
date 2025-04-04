import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Scorecards - Plexus Documentation",
  description: "Learn about Scorecards in Plexus - the framework for evaluating content quality and performance"
}

export default function ScorecardsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Scorecards</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understand how to create and manage Scorecards to evaluate your content effectively.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Scorecards?</h2>
          <p className="text-muted-foreground mb-4">
            Scorecards are collections of evaluation criteria that define how your content
            should be analyzed. They help ensure consistent evaluation across all your sources
            by providing a structured framework for assessment.
          </p>
          <p className="text-muted-foreground mb-4">
            Think of a scorecard as a comprehensive evaluation template that contains all the 
            metrics and criteria you want to measure for a specific type of content. Scorecards 
            can be tailored to different content types, business objectives, or quality standards.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scorecard Structure</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Sections</h3>
              <p className="text-muted-foreground mb-4">
                Scorecards are organized into logical sections that group related evaluation criteria.
                For example, a customer service scorecard might have sections for "Greeting", "Problem Resolution",
                and "Closing".
              </p>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Scores</h3>
              <p className="text-muted-foreground mb-4">
                Individual evaluation criteria that assess specific aspects of your content.
                Each score can be customized with its own evaluation logic and requirements.
                Scores are the building blocks of your evaluation framework.
              </p>
              <p className="text-muted-foreground mb-4">
                Examples of scores include:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Grammar and spelling accuracy</li>
                <li>Sentiment analysis (positive/negative/neutral)</li>
                <li>Compliance with specific regulations</li>
                <li>Presence of required information</li>
                <li>Custom business-specific metrics</li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Sections</h3>
              <p className="text-muted-foreground">
                Logical groupings of related scores within a scorecard. Sections help organize
                scores into categories for better management and understanding.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Weights</h3>
              <p className="text-muted-foreground mb-4">
                Importance factors that determine how much each score contributes to the
                overall evaluation result. Weights allow you to prioritize certain criteria
                over others based on their importance to your business objectives.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Versions</h3>
              <p className="text-muted-foreground">
                Score configurations are versioned, allowing you to track changes over time,
                compare different implementations, and promote specific versions to champion status.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">CLI Management</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus CLI provides powerful commands for managing scorecards:
          </p>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Listing Scorecards</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# List all scorecards for an account
plexus scorecards list "account-name"

# List with filtering
plexus scorecards list "account-name" --name "Scorecard Name"
plexus scorecards list "account-name" --key "scorecard-key"

# Performance options
plexus scorecards list "account-name" --fast  # Skip fetching scores for faster results
plexus scorecards list "account-name" --hide-scores  # Don't display scores in output`}</code>
              </pre>
              <p className="text-muted-foreground">
                The list command uses an optimized single GraphQL query to fetch scorecards, sections, 
                and scores in one request, providing significantly faster performance.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Viewing Score Details</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# View a specific score by name, key, ID, or external ID
plexus scorecards score "Score Name" --account "account-name"
plexus scorecards score "score-key" --account "account-name"
plexus scorecards score "score-id" --show-versions --show-config

# Scope to a specific scorecard
plexus scorecards score "Score Name" --scorecard "Scorecard Name"`}</code>
              </pre>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Listing Scores in a Scorecard</h3>
              <p className="text-muted-foreground mb-4">
                To list all scores within a scorecard, use the <code>scores list</code> command:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# List all scores in a scorecard
plexus scores list --scorecard "Scorecard Name"

# You can also use the singular form
plexus score list --scorecard "Scorecard Name"`}</code>
              </pre>
              <p className="text-muted-foreground">
                This command displays all scores organized by section, including their IDs, keys, and external IDs.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Version Management</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# View version history (coming soon)
plexus scorecards history --account-key "account-key" --score-key "score-key"

# Promote a version to champion (coming soon)
plexus scorecards promote --account-key "account-key" --score-id "score-id" --version-id "version-id"

# Pull latest champion versions (coming soon)
plexus scorecards pull --account-key "account-key"

# Push local changes as new versions
plexus scorecards push --scorecard "scorecard-name" --note "Updated configuration"`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Scorecard Organization</h3>
              <p className="text-muted-foreground">
                Group related scores into logical sections to improve clarity and maintainability.
                Use consistent naming conventions for scorecards, sections, and scores.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Version Management</h3>
              <p className="text-muted-foreground">
                Add descriptive notes to new versions to document changes. Test new versions
                thoroughly before promoting them to champion status.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Performance Considerations</h3>
              <p className="text-muted-foreground">
                Use the <code>--fast</code> option when listing many scorecards to improve performance.
                This skips fetching score details when you only need basic scorecard information.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional scorecard features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced score configuration options</li>
            <li>Collaborative editing features</li>
            <li>Performance analytics</li>
            <li>Bulk operations for scorecard management</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 