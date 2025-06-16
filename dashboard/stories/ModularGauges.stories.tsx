import type { Meta, StoryObj } from '@storybook/react'
import { BaseGauges } from '@/components/BaseGauges'
import { EvaluationItemsGauges } from '@/components/EvaluationItemsGauges'
import { PredictionItemsGauges } from '@/components/PredictionItemsGauges'
import { FeedbackItemsGauges } from '@/components/FeedbackItemsGauges'
import { ItemsGaugesRefactored } from '@/components/ItemsGaugesRefactored'
import { AccountProvider } from '@/app/contexts/AccountContext'

const meta: Meta<typeof BaseGauges> = {
  title: 'Dashboard/Modular Gauges Architecture',
  component: BaseGauges,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
# Modular Gauge Architecture

A flexible, reusable architecture for creating gauge components with different configurations.
All components share the same base implementation ensuring consistent behavior and styling.

## Architecture Benefits

- **🔧 Modularity**: Each component is configured independently but shares the same base implementation
- **📱 Responsive**: Grid configurations adapt to different numbers of gauges automatically
- **🎨 Consistent**: All animations, loading states, error handling, and visual effects are identical
- **🔄 Reusable**: Adding new gauge types only requires creating a new configuration object

## Components

- **ItemsGauges** (refactored): 2 gauges - items + score results (all types combined)
- **EvaluationItemsGauges**: 2 gauges - evaluation items + evaluation score results
- **PredictionItemsGauges**: 2 gauges - prediction items + prediction score results  
- **FeedbackItemsGauges**: 1 gauge - feedback items only (demonstrates single-gauge responsive behavior)

## Responsive Behavior

- **Single Gauge**: Uses same grid as multi-gauge but gauge takes 1 column, chart takes remaining
- **Multi-Gauge**: 2→3→4→5→6 columns as screen gets wider, chart spans remaining columns
- **Perfect Alignment**: All gauges are exactly the same width across all component types
        `
      }
    }
  },
  decorators: [
    (Story) => (
      <AccountProvider>
        <div className="@container p-6 space-y-8">
          <Story />
        </div>
      </AccountProvider>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof BaseGauges>

// Mock data for consistent demonstrations
const mockOverallData = {
  itemsPerHour: 45,
  itemsAveragePerHour: 38,
  itemsPeakHourly: 85,
  itemsTotal24h: 912,
  scoreResultsPerHour: 180,
  scoreResultsAveragePerHour: 165,
  scoreResultsPeakHourly: 320,
  scoreResultsTotal24h: 3960,
  chartData: [
    { time: '24h ago', items: 25, scoreResults: 120 },
    { time: '20h ago', items: 32, scoreResults: 145 },
    { time: '16h ago', items: 41, scoreResults: 180 },
    { time: '12h ago', items: 55, scoreResults: 220 },
    { time: '8h ago', items: 38, scoreResults: 165 },
    { time: '4h ago', items: 52, scoreResults: 195 },
    { time: 'now', items: 45, scoreResults: 180 },
  ],
  lastUpdated: new Date(),
  hasErrorsLast24h: false,
  totalErrors24h: 0
}

const mockEvaluationData = {
  evaluationItemsPerHour: 12,
  evaluationItemsAveragePerHour: 8,
  evaluationItemsPeakHourly: 25,
  evaluationItemsTotal24h: 192,
  evaluationScoreResultsPerHour: 48,
  evaluationScoreResultsAveragePerHour: 35,
  evaluationScoreResultsPeakHourly: 85,
  evaluationScoreResultsTotal24h: 840,
  chartData: [
    { time: '24h ago', items: 5, scoreResults: 20 },
    { time: '20h ago', items: 8, scoreResults: 32 },
    { time: '16h ago', items: 12, scoreResults: 48 },
    { time: '12h ago', items: 15, scoreResults: 60 },
    { time: '8h ago', items: 10, scoreResults: 40 },
    { time: '4h ago', items: 18, scoreResults: 72 },
    { time: 'now', items: 12, scoreResults: 48 },
  ],
  lastUpdated: new Date(),
  hasErrorsLast24h: false,
  totalErrors24h: 0
}

const mockPredictionData = {
  predictionItemsPerHour: 33,
  predictionItemsAveragePerHour: 30,
  predictionItemsPeakHourly: 60,
  predictionItemsTotal24h: 720,
  predictionScoreResultsPerHour: 132,
  predictionScoreResultsAveragePerHour: 130,
  predictionScoreResultsPeakHourly: 235,
  predictionScoreResultsTotal24h: 3120,
  chartData: [
    { time: '24h ago', items: 20, scoreResults: 100 },
    { time: '20h ago', items: 24, scoreResults: 113 },
    { time: '16h ago', items: 29, scoreResults: 132 },
    { time: '12h ago', items: 40, scoreResults: 160 },
    { time: '8h ago', items: 28, scoreResults: 125 },
    { time: '4h ago', items: 34, scoreResults: 123 },
    { time: 'now', items: 33, scoreResults: 132 },
  ],
  lastUpdated: new Date(),
  hasErrorsLast24h: false,
  totalErrors24h: 0
}

const mockFeedbackData = {
  feedbackItemsPerHour: 12,
  feedbackItemsAveragePerHour: 8,
  feedbackItemsPeakHourly: 25,
  feedbackItemsTotal24h: 192,
  chartData: [
    { time: '24h ago', feedbackItems: 5 },
    { time: '20h ago', feedbackItems: 8 },
    { time: '16h ago', feedbackItems: 12 },
    { time: '12h ago', feedbackItems: 15 },
    { time: '8h ago', feedbackItems: 10 },
    { time: '4h ago', feedbackItems: 18 },
    { time: 'now', feedbackItems: 12 },
  ],
  lastUpdated: new Date(),
  hasErrorsLast24h: false,
  totalErrors24h: 0
}

export const OverallMetrics: Story = {
  name: '📊 Overall Metrics (Refactored)',
  render: () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Overall Metrics</h2>
        <p className="text-sm text-muted-foreground">
          All items and score results combined (refactored to use BaseGauges architecture)
        </p>
      </div>
      <ItemsGaugesRefactored 
        useRealData={false}
        overrideData={mockOverallData}
      />
    </div>
  ),
}

export const EvaluationMetrics: Story = {
  name: '🔬 Evaluation Metrics',
  render: () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Evaluation Metrics</h2>
        <p className="text-sm text-muted-foreground">
          Items and score results from evaluation workflows only
        </p>
      </div>
      <EvaluationItemsGauges 
        useRealData={false}
        overrideData={mockEvaluationData}
      />
    </div>
  ),
}

export const PredictionMetrics: Story = {
  name: '🎯 Prediction Metrics',
  render: () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Prediction Metrics</h2>
        <p className="text-sm text-muted-foreground">
          Items and score results from prediction workflows only
        </p>
      </div>
      <PredictionItemsGauges 
        useRealData={false}
        overrideData={mockPredictionData}
      />
    </div>
  ),
}

export const FeedbackMetrics: Story = {
  name: '💬 Feedback Metrics (Single Gauge)',
  render: () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Feedback Metrics</h2>
        <p className="text-sm text-muted-foreground">
          Single gauge example - feedback items only. The gauge maintains consistent width 
          with multi-gauge components, while the chart greedily takes all remaining space.
        </p>
      </div>
      <FeedbackItemsGauges 
        useRealData={false}
        overrideData={mockFeedbackData}
      />
    </div>
  ),
}

export const AllComponentsComparison: Story = {
  name: '🏗️ Architecture Comparison',
  render: () => (
    <div className="space-y-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Modular Gauge Architecture</h1>
        <p className="text-muted-foreground">
          All components below use the same BaseGauges foundation but with different configurations.
          Notice how they all align perfectly and behave consistently.
        </p>
      </div>

      {/* Overall Metrics */}
      <section className="space-y-4">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">📊 Overall Metrics</h2>
          <p className="text-sm text-muted-foreground">
            All items and score results combined (2 gauges + chart)
          </p>
        </div>
        <ItemsGaugesRefactored 
          useRealData={false}
          overrideData={mockOverallData}
        />
      </section>

      {/* Evaluation Metrics */}
      <section className="space-y-4">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">🔬 Evaluation Metrics</h2>
          <p className="text-sm text-muted-foreground">
            Evaluation workflows only (2 gauges + chart)
          </p>
        </div>
        <EvaluationItemsGauges 
          useRealData={false}
          overrideData={mockEvaluationData}
        />
      </section>

      {/* Prediction Metrics */}
      <section className="space-y-4">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">🎯 Prediction Metrics</h2>
          <p className="text-sm text-muted-foreground">
            Prediction workflows only (2 gauges + chart)
          </p>
        </div>
        <PredictionItemsGauges 
          useRealData={false}
          overrideData={mockPredictionData}
        />
      </section>

             {/* Feedback Metrics */}
       <section className="space-y-4">
         <div className="space-y-2">
           <h2 className="text-2xl font-semibold">💬 Feedback Metrics</h2>
           <p className="text-sm text-muted-foreground">
             Single gauge example (1 gauge + chart) - gauge width matches multi-gauge components, chart is greedy
           </p>
         </div>
         <FeedbackItemsGauges 
           useRealData={false}
           overrideData={mockFeedbackData}
         />
       </section>

      {/* Architecture Benefits */}
      <section className="space-y-4">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">🏗️ Architecture Benefits</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="bg-card p-4 rounded-lg">
            <h3 className="font-semibold mb-2">🔧 Modularity</h3>
            <p className="text-sm text-muted-foreground">
              Each component is configured independently but shares the same base implementation,
              ensuring consistent behavior and styling.
            </p>
          </div>
          <div className="bg-card p-4 rounded-lg">
            <h3 className="font-semibold mb-2">📱 Responsive</h3>
            <p className="text-sm text-muted-foreground">
              Grid configurations adapt to different numbers of gauges. Single gauge components
              maintain the same gauge width as multi-gauge components.
            </p>
          </div>
          <div className="bg-card p-4 rounded-lg">
            <h3 className="font-semibold mb-2">🎨 Consistent</h3>
            <p className="text-sm text-muted-foreground">
              All animations, loading states, error handling, and visual effects are identical
              across all gauge types.
            </p>
          </div>
          <div className="bg-card p-4 rounded-lg">
            <h3 className="font-semibold mb-2">🔄 Reusable</h3>
            <p className="text-sm text-muted-foreground">
              Adding new gauge types (e.g., API calls, costs, errors) only requires creating
              a new configuration object.
            </p>
          </div>
        </div>
      </section>
    </div>
  ),
}

export const ResponsiveBehavior: Story = {
  name: '📱 Responsive Behavior Demo',
  render: () => (
    <div className="space-y-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Responsive Behavior</h1>
        <p className="text-muted-foreground">
          Resize your browser window to see how the components adapt. All gauge widths stay consistent.
        </p>
      </div>

      <div className="space-y-6">
        <div className="bg-muted/20 p-4 rounded-lg">
          <h3 className="font-semibold mb-2">Multi-Gauge Components (2 gauges)</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Grid: 2→3→4→5→6 columns | Chart spans: 2→1→2→3→4 columns
          </p>
          <ItemsGaugesRefactored 
            useRealData={false}
            overrideData={mockOverallData}
          />
        </div>

                 <div className="bg-muted/20 p-4 rounded-lg">
           <h3 className="font-semibold mb-2">Single-Gauge Component (1 gauge)</h3>
           <p className="text-sm text-muted-foreground mb-4">
             Grid: 2→3→4→5→6 columns | Gauge: 1 column (SAME width as above) | Chart: greedy remaining space
           </p>
           <FeedbackItemsGauges 
             useRealData={false}
             overrideData={mockFeedbackData}
           />
         </div>
      </div>
    </div>
  ),
} 