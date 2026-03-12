import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { ScoreResultTrace } from '../../../components/ui/score-result-trace'

const meta: Meta<typeof ScoreResultTrace> = {
  title: 'Items/ScoreResultTrace',
  component: ScoreResultTrace,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A component for displaying trace data from score results. Supports multiple trace formats and provides both parsed node view and raw data fallback.'
      }
    }
  },
  argTypes: {
    trace: {
      control: { type: 'object' },
      description: 'Trace data in various supported formats'
    },
    variant: {
      control: { type: 'select' },
      options: ['default', 'compact'],
      description: 'Display variant for the trace'
    },
    className: {
      control: { type: 'text' },
      description: 'Additional CSS classes'
    }
  }
}

export default meta
type Story = StoryObj<typeof ScoreResultTrace>

// Sample trace data for stories
const nodeResultsTrace = {
  node_results: [
    {
      node_name: "Input Classifier",
      input: {
        text: "Customer complaint about billing issue",
        previous_context: null
      },
      output: {
        classification: "billing_inquiry",
        confidence: 0.92
      }
    },
    {
      node_name: "Sentiment Analyzer",
      input: {
        text: "Customer complaint about billing issue",
        classification: "billing_inquiry"
      },
      output: {
        sentiment: "negative",
        sentiment_score: -0.8,
        explanation: "Customer uses frustrated language regarding billing"
      }
    },
    {
      node_name: "Response Generator",
      input: {
        classification: "billing_inquiry",
        sentiment: "negative",
        customer_tier: "premium"
      },
      output: {
        response: "I understand your frustration with the billing issue. Let me escalate this to our billing specialist immediately.",
        escalation_required: true,
        urgency_level: "high"
      }
    }
  ]
}

const arrayFormatTrace = [
  {
    name: "Text Extractor",
    inputs: {
      raw_content: "Call transcript: Customer says they are dissatisfied with service quality",
      extraction_type: "sentiment"
    },
    outputs: {
      extracted_text: "dissatisfied with service quality",
      sentiment_indicators: ["dissatisfied", "service quality"],
      confidence: 0.87
    }
  },
  {
    name: "Score Calculator",
    inputs: {
      sentiment_indicators: ["dissatisfied", "service quality"],
      weights: { "dissatisfied": -2, "service quality": -1 }
    },
    outputs: {
      final_score: -3,
      normalized_score: 0.2,
      explanation: "Negative sentiment detected with service quality concerns"
    }
  }
]

const stepsFormatTrace = {
  steps: [
    {
      name: "Data Preprocessing",
      inputs: {
        raw_text: "Hello, I'm calling about my account. The service has been terrible lately.",
        preprocessing_options: ["normalize_text", "remove_stopwords"]
      },
      outputs: {
        cleaned_text: "calling account service terrible lately",
        tokens: ["calling", "account", "service", "terrible", "lately"],
        token_count: 5
      }
    },
    {
      name: "Feature Extraction",
      inputs: {
        tokens: ["calling", "account", "service", "terrible", "lately"],
        feature_type: "tfidf"
      },
      outputs: {
        features: [0.2, 0.1, 0.3, 0.8, 0.1],
        feature_names: ["calling", "account", "service", "terrible", "lately"],
        feature_importance: { "terrible": 0.8, "service": 0.3 }
      }
    }
  ]
}

const complexTrace = {
  node_results: [
    {
      node_name: "Multi-step Analyzer",
      input: {
        text: "This is a very long text input that contains multiple sentences. The customer is expressing concerns about various aspects of the service including response time, quality of support, and billing accuracy. They mention specific incidents and provide detailed feedback about their experience.",
        analysis_depth: "comprehensive",
        include_metadata: true
      },
      output: {
        primary_classification: "service_complaint",
        secondary_classifications: ["billing_issue", "support_quality", "response_time"],
        detailed_analysis: {
          sentiment_breakdown: {
            overall: -0.6,
            aspects: {
              "response_time": -0.8,
              "support_quality": -0.5,
              "billing_accuracy": -0.7
            }
          },
          key_phrases: [
            "response time concerns",
            "quality of support issues",
            "billing accuracy problems"
          ],
          urgency_indicators: ["specific incidents", "detailed feedback"],
          recommended_actions: [
            "escalate_to_supervisor",
            "schedule_follow_up",
            "billing_team_review"
          ]
        },
        confidence_scores: {
          classification: 0.94,
          sentiment: 0.87,
          urgency: 0.76
        },
        processing_time_ms: 245,
        model_version: "v2.1.3"
      }
    }
  ]
}

const rawStringTrace = JSON.stringify({
  execution_id: "exec_12345",
  timestamp: "2024-01-15T10:30:00Z",
  steps: [
    { step: 1, operation: "load_model", duration: "50ms", status: "success" },
    { step: 2, operation: "process_input", duration: "120ms", status: "success" },
    { step: 3, operation: "generate_output", duration: "80ms", status: "success" }
  ],
  total_duration: "250ms"
})

const malformedTrace = {
  // This is a trace that doesn't match any known format
  execution_log: "Processing started at 10:30:00...",
  debug_info: {
    memory_usage: "125MB",
    cpu_time: "0.8s"
  },
  random_data: [1, 2, 3, 4, 5]
}

// Basic stories
export const Default: Story = {
  args: {
    trace: nodeResultsTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Default trace display showing parsed nodes from a node_results format trace.'
      }
    }
  }
}

export const ArrayFormat: Story = {
  args: {
    trace: arrayFormatTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Trace display with array format showing multiple processing steps.'
      }
    }
  }
}

export const StepsFormat: Story = {
  args: {
    trace: stepsFormatTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Trace display with steps format showing data preprocessing and feature extraction.'
      }
    }
  }
}

export const CompactVariant: Story = {
  args: {
    trace: nodeResultsTrace,
    variant: 'compact'
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact variant with reduced spacing between nodes for denser display.'
      }
    }
  }
}

// Complex data stories
export const ComplexTrace: Story = {
  args: {
    trace: complexTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Complex trace with nested objects, arrays, and detailed analysis results.'
      }
    }
  }
}

export const LongText: Story = {
  args: {
    trace: {
      node_results: [
        {
          node_name: "Text Processing Node",
          input: {
            long_text: "This is an extremely long text input that would normally be truncated in most displays. It contains multiple paragraphs, detailed information, and extensive data that needs to be properly formatted and displayed in the trace view. The text continues for several lines to demonstrate how the component handles lengthy content and whether it provides appropriate formatting, scrolling, or truncation mechanisms.",
            parameters: {
              max_length: 1000,
              include_metadata: true,
              processing_mode: "comprehensive"
            }
          },
          output: {
            processed_text: "Processed version of the long text with various transformations applied including normalization, tokenization, and feature extraction.",
            metadata: {
              original_length: 456,
              processed_length: 123,
              compression_ratio: 0.27,
              processing_time: "0.245s"
            },
            summary: "Long text successfully processed with high confidence"
          }
        }
      ]
    },
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Trace with very long text content to demonstrate text handling and formatting.'
      }
    }
  }
}

// Edge cases and fallbacks
export const EmptyTrace: Story = {
  args: {
    trace: null,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'No trace data provided - component should not render anything.'
      }
    }
  }
}

export const StringTrace: Story = {
  args: {
    trace: rawStringTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Trace data provided as a JSON string - should be parsed and displayed.'
      }
    }
  }
}

export const MalformedTrace: Story = {
  args: {
    trace: malformedTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Trace data that doesn\'t match known formats - should fallback to raw data display.'
      }
    }
  }
}

export const InvalidJSONString: Story = {
  args: {
    trace: "{ invalid json string that cannot be parsed }",
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Invalid JSON string trace - should fallback to displaying the raw string.'
      }
    }
  }
}

// Integration stories
export const InScoreResultCard: Story = {
  render: (args) => (
    <div className="bg-card rounded-lg p-4 border max-w-2xl">
      <h3 className="text-lg font-semibold mb-4">Score Result Details</h3>
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Value</h4>
          <div className="bg-secondary px-2 py-1 rounded text-sm">Positive</div>
        </div>
        <div>
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Explanation</h4>
          <p className="text-sm">The sentiment analysis indicates positive customer feedback based on language patterns and context.</p>
        </div>
        <ScoreResultTrace {...args} />
      </div>
    </div>
  ),
  args: {
    trace: nodeResultsTrace,
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'How the ScoreResultTrace component appears when integrated within a score result card.'
      }
    }
  }
}

export const MultipleNodes: Story = {
  args: {
    trace: {
      node_results: [
        {
          node_name: "Input Validation",
          input: { text: "Customer feedback text", source: "email" },
          output: { valid: true, length: 156, language: "en" }
        },
        {
          node_name: "Preprocessing",
          input: { text: "Customer feedback text", clean_html: true },
          output: { cleaned_text: "Customer feedback text", removed_elements: [] }
        },
        {
          node_name: "Feature Extraction",
          input: { text: "Customer feedback text" },
          output: { features: [0.1, 0.8, 0.3], feature_names: ["positive", "negative", "neutral"] }
        },
        {
          node_name: "Classification",
          input: { features: [0.1, 0.8, 0.3] },
          output: { prediction: "positive", confidence: 0.85 }
        },
        {
          node_name: "Post-processing",
          input: { prediction: "positive", confidence: 0.85 },
          output: { final_result: "positive", adjusted_confidence: 0.82, metadata: { model_version: "v1.2" } }
        }
      ]
    },
    variant: 'default'
  },
  parameters: {
    docs: {
      description: {
        story: 'Trace with multiple sequential processing nodes showing a complete analysis pipeline.'
      }
    }
  }
}

export const CompactMultipleNodes: Story = {
  args: {
    trace: {
      node_results: [
        {
          node_name: "Input Validation",
          input: { text: "Customer feedback text", source: "email" },
          output: { valid: true, length: 156, language: "en" }
        },
        {
          node_name: "Preprocessing",
          input: { text: "Customer feedback text", clean_html: true },
          output: { cleaned_text: "Customer feedback text", removed_elements: [] }
        },
        {
          node_name: "Feature Extraction",
          input: { text: "Customer feedback text" },
          output: { features: [0.1, 0.8, 0.3], feature_names: ["positive", "negative", "neutral"] }
        },
        {
          node_name: "Classification",
          input: { features: [0.1, 0.8, 0.3] },
          output: { prediction: "positive", confidence: 0.85 }
        },
        {
          node_name: "Post-processing",
          input: { prediction: "positive", confidence: 0.85 },
          output: { final_result: "positive", adjusted_confidence: 0.82, metadata: { model_version: "v1.2" } }
        }
      ]
    },
    variant: 'compact'
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact version of multiple nodes trace for denser display in constrained spaces.'
      }
    }
  }
} 