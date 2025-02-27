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
              <h3 className="text-xl font-medium mb-2">Weights</h3>
              <p className="text-muted-foreground mb-4">
                Importance factors that determine how much each score contributes to the
                overall evaluation result. Weights allow you to prioritize certain criteria
                over others based on their importance to your business objectives.
              </p>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Configuration</h3>
              <p className="text-muted-foreground mb-4">
                Each score has a configuration that defines how it evaluates content. This can include:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Evaluation method (rule-based, ML model, LLM prompt)</li>
                <li>Thresholds for pass/fail determination</li>
                <li>Custom parameters specific to the score type</li>
                <li>Expected output format and validation rules</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scorecard Identifiers</h2>
          <p className="text-muted-foreground mb-4">
            Scorecards in Plexus can be referenced using multiple types of identifiers, making them
            easy to work with across different interfaces (UI, CLI, SDK). This flexible identifier
            system is particularly useful when working with the CLI or SDK.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Types of Identifiers</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>DynamoDB ID</strong>: The unique database identifier 
                  (e.g., <code>e51cd5ec-1940-4d8e-abcc-faa851390112</code>)
                </li>
                <li>
                  <strong>Name</strong>: The human-readable name 
                  (e.g., <code>"Quality Assurance"</code>)
                </li>
                <li>
                  <strong>Key</strong>: The URL-friendly key 
                  (e.g., <code>quality-assurance</code>)
                </li>
                <li>
                  <strong>External ID</strong>: Your custom external identifier 
                  (e.g., <code>qa-2023</code>)
                </li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Using Identifiers</h3>
              <p className="text-muted-foreground mb-4">
                When working with the CLI or SDK, you can use any of these identifiers to reference a scorecard:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# CLI examples - all reference the same scorecard
plexus scorecards info --scorecard e51cd5ec-1940-4d8e-abcc-faa851390112
plexus scorecards info --scorecard "Quality Assurance"
plexus scorecards info --scorecard quality-assurance
plexus scorecards info --scorecard qa-2023

# SDK example
scorecard = plexus.scorecards.get("Quality Assurance")  # Works with any identifier type`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Working with Scorecards</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Creating Scorecards</h3>
              <p className="text-muted-foreground mb-4">
                Scorecards can be created through the dashboard UI, CLI, or SDK. The creation process
                involves defining sections, adding scores, and configuring evaluation parameters.
              </p>
              <Link href="/documentation/methods/add-edit-scorecard">
                <DocButton>Learn how to create scorecards</DocButton>
              </Link>
            </div>
            
            <div className="mt-6">
              <h3 className="text-xl font-medium mb-2">Managing Scores</h3>
              <p className="text-muted-foreground mb-4">
                Once a scorecard is created, you can add, edit, or remove scores to refine your
                evaluation criteria. Each score can be individually configured and weighted.
              </p>
              <Link href="/documentation/methods/add-edit-score">
                <DocButton>Learn how to manage scores</DocButton>
              </Link>
            </div>
            
            <div className="mt-6">
              <h3 className="text-xl font-medium mb-2">Running Evaluations</h3>
              <p className="text-muted-foreground mb-4">
                Scorecards are used to evaluate content by applying all their scores to your sources.
                The evaluation process generates detailed results that can be analyzed and acted upon.
              </p>
              <Link href="/documentation/methods/evaluate-score">
                <DocButton>Learn how to run evaluations</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scorecard Management</h2>
          <p className="text-muted-foreground mb-4">
            Plexus provides multiple interfaces for managing scorecards:
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Dashboard UI</h3>
              <p className="text-muted-foreground mb-4">
                The web-based dashboard provides a visual interface for creating and managing scorecards,
                with intuitive forms and real-time feedback.
              </p>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Command Line Interface (CLI)</h3>
              <p className="text-muted-foreground mb-4">
                The Plexus CLI offers powerful commands for scorecard management, ideal for automation
                and scripting. The CLI supports the flexible identifier system for easy reference.
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# List all scorecards
plexus scorecards list

# Get detailed information about a specific scorecard
plexus scorecards info --scorecard "Content Quality"

# List all scores in a scorecard
plexus scorecards list-scores --scorecard "Content Quality"`}</code>
              </pre>
              <Link href="/documentation/advanced/cli">
                <DocButton>View CLI documentation</DocButton>
              </Link>
            </div>
            
            <div className="mt-6">
              <h3 className="text-xl font-medium mb-2">Python SDK</h3>
              <p className="text-muted-foreground mb-4">
                The Python SDK provides programmatic access to scorecard management, allowing
                integration with your existing systems and workflows.
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Get a scorecard using any identifier
scorecard = plexus.scorecards.get("Content Quality")

# List all scores in a scorecard
scores = scorecard.get_scores()`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Scorecard Design</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Focus on measurable, objective criteria whenever possible</li>
                <li>Group related scores into logical sections</li>
                <li>Balance the number of scores (too few may not be comprehensive, too many may be unwieldy)</li>
                <li>Use clear, descriptive names for scorecards and scores</li>
                <li>Document the purpose and expected outcomes for each score</li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Weight Distribution</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Assign weights based on business impact and importance</li>
                <li>Ensure weights sum to 1.0 (or 100%) for proper normalization</li>
                <li>Periodically review and adjust weights based on changing priorities</li>
                <li>Consider using section weights to balance different aspects of evaluation</li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-xl font-medium mb-2">Versioning and Iteration</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Use meaningful keys and external IDs for better tracking</li>
                <li>Document changes when updating scorecard configurations</li>
                <li>Test new scorecard versions on historical data before deployment</li>
                <li>Consider creating specialized scorecards for different content types</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Ready to start working with scorecards? Explore these resources:
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/documentation/methods/add-edit-scorecard">
              <DocButton>Create Your First Scorecard</DocButton>
            </Link>
            <Link href="/documentation/concepts/scores">
              <DocButton variant="outline">Learn About Scores</DocButton>
            </Link>
            <Link href="/documentation/advanced/cli">
              <DocButton variant="outline">Explore the CLI</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 