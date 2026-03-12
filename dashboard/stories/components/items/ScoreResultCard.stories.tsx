import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import ScoreResultCard, { ScoreResultData } from '../../../components/items/ScoreResultCard'

const meta: Meta<typeof ScoreResultCard> = {
  title: 'Items/ScoreResultCard',
  component: ScoreResultCard,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A comprehensive card component for displaying score result details including value, explanation, trace data, and attachments. Supports full-width mode, skeleton loading, and various interaction states.'
      }
    }
  },
  argTypes: {
    scoreResult: {
      control: { type: 'object' },
      description: 'Score result data object containing all the information to display'
    },
    isFullWidth: {
      control: { type: 'boolean' },
      description: 'Whether the card should display in full width mode'
    },
    onToggleFullWidth: {
      action: 'toggleFullWidth',
      description: 'Callback function when full width toggle is clicked'
    },
    onClose: {
      action: 'close',
      description: 'Callback function when close button is clicked'
    },
    skeletonMode: {
      control: { type: 'boolean' },
      description: 'Whether to show skeleton loading state'
    },
    naturalHeight: {
      control: { type: 'boolean' },
      description: 'Whether to use natural height instead of fixed height'
    }
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl h-[600px]">
        <Story />
      </div>
    )
  ]
}

export default meta
type Story = StoryObj<typeof ScoreResultCard>

// Sample score result data
const basicScoreResult: ScoreResultData = {
  id: "sr_abc123def456",
  value: "Positive",
  explanation: "The customer's tone and language indicate satisfaction with the service provided.",
  confidence: 0.87,
  itemId: "item_789xyz",
  accountId: "acc_123",
  scorecardId: "sc_456",
  scoreId: "score_789",
  scorecard: {
    id: "sc_456",
    name: "Customer Satisfaction v2.1",
    externalId: "cs-v2.1"
  },
  score: {
    id: "score_789",
    name: "Sentiment Analysis",
    externalId: "sentiment-v1"
  },
  updatedAt: "2024-01-15T14:30:00Z",
  createdAt: "2024-01-15T14:29:45Z"
}

const detailedScoreResult: ScoreResultData = {
  id: "sr_detailed123",
  value: "Needs Improvement",
  explanation: `## Analysis Summary

The conversation analysis reveals several areas for improvement:

### Key Findings
- **Response Time**: Agent took 45 seconds to acknowledge the customer
- **Empathy**: Limited use of empathetic language
- **Resolution**: Issue was resolved but process was inefficient

### Recommendations
1. Implement faster acknowledgment protocols
2. Use more empathetic phrases like "I understand your frustration"
3. Streamline the resolution process

### Confidence Breakdown
- Technical accuracy: 92%
- Communication style: 68%
- Overall effectiveness: 75%`,
  confidence: 0.75,
  itemId: "item_detailed",
  accountId: "acc_123",
  scorecardId: "sc_qa",
  scoreId: "score_communication",
  trace: {
    node_results: [
      {
        node_name: "Response Time Analyzer",
        input: {
          conversation_start: "2024-01-15T14:00:00Z",
          first_agent_response: "2024-01-15T14:00:45Z"
        },
        output: {
          response_time_seconds: 45,
          benchmark_seconds: 30,
          performance: "below_standard"
        }
      },
      {
        node_name: "Empathy Detector",
        input: {
          agent_messages: [
            "I can help you with that.",
            "Let me check your account.",
            "The issue has been resolved."
          ]
        },
        output: {
          empathy_score: 0.3,
          empathetic_phrases: 0,
          suggestions: ["I understand your frustration", "I'm sorry for the inconvenience"]
        }
      },
      {
        node_name: "Resolution Efficiency",
        input: {
          total_conversation_time: 480,
          resolution_achieved: true,
          steps_taken: 8
        },
        output: {
          efficiency_score: 0.68,
          optimal_steps: 5,
          time_efficiency: "moderate"
        }
      }
    ]
  },
  attachments: [
    "/tmp/conversation_transcript.txt",
    "/tmp/analysis_report.json",
    "/tmp/trace.json"
  ],
  scorecard: {
    id: "sc_qa",
    name: "Quality Assurance Scorecard",
    externalId: "qa-v3.0"
  },
  score: {
    id: "score_communication",
    name: "Communication Effectiveness",
    externalId: "comm-eff-v2"
  },
  updatedAt: "2024-01-15T15:45:30Z",
  createdAt: "2024-01-15T15:44:00Z"
}

const minimalScoreResult: ScoreResultData = {
  id: "sr_minimal",
  value: "Pass",
  itemId: "item_min",
  accountId: "acc_123",
  scorecardId: "sc_basic",
  scoreId: "score_basic",
  createdAt: "2024-01-15T12:00:00Z"
}

const longExplanationScoreResult: ScoreResultData = {
  id: "sr_long_explanation",
  value: "Complex Analysis",
  explanation: `# Comprehensive Call Analysis Report

## Executive Summary
This analysis covers multiple dimensions of the customer service interaction, providing detailed insights into performance metrics, communication effectiveness, and areas for improvement.

## Detailed Findings

### 1. Communication Quality Assessment
The agent demonstrated **strong technical knowledge** but showed room for improvement in emotional intelligence and customer rapport building. Key observations include:

- Clear articulation of technical solutions
- Appropriate use of company terminology
- Limited personalization of responses
- Missed opportunities for relationship building

### 2. Problem Resolution Efficiency
The resolution process followed standard protocols with the following timeline:
1. **Initial Assessment** (0-2 minutes): Customer issue identification
2. **Information Gathering** (2-5 minutes): Account verification and history review
3. **Solution Development** (5-8 minutes): Technical troubleshooting
4. **Implementation** (8-12 minutes): Solution deployment and testing
5. **Verification** (12-15 minutes): Customer confirmation and follow-up

### 3. Customer Satisfaction Indicators
Based on linguistic analysis and sentiment detection:

#### Positive Indicators
- Customer expressed gratitude multiple times
- Tone remained cooperative throughout
- No escalation requests made
- Willingness to follow technical instructions

#### Areas of Concern
- Initial frustration with wait time
- Confusion during technical explanation phase
- Request for simpler language

### 4. Compliance and Quality Metrics

| Metric | Score | Benchmark | Status |
|--------|-------|-----------|--------|
| Script Adherence | 85% | 80% | ✅ Pass |
| Empathy Score | 72% | 75% | ⚠️ Below Target |
| Resolution Time | 15 min | 12 min | ⚠️ Above Target |
| Customer Satisfaction | 4.2/5 | 4.0/5 | ✅ Pass |

### 5. Recommendations for Improvement

#### Immediate Actions
1. **Empathy Training**: Focus on active listening and emotional validation techniques
2. **Process Optimization**: Streamline information gathering to reduce resolution time
3. **Communication Skills**: Practice explaining technical concepts in customer-friendly language

#### Long-term Development
- Advanced conflict resolution training
- Cross-functional knowledge expansion
- Mentorship program participation

### 6. Technical Analysis Details

The conversation was processed through our advanced NLP pipeline, which analyzed:
- **Sentiment progression** throughout the interaction
- **Keyword density** for compliance verification
- **Speech patterns** for communication effectiveness
- **Resolution pathway** for efficiency optimization

### Conclusion
While the interaction resulted in successful problem resolution and acceptable customer satisfaction, there are clear opportunities for enhancement in empathy demonstration and process efficiency. The agent shows strong potential and would benefit from targeted coaching in the identified areas.`,
  confidence: 0.91,
  itemId: "item_comprehensive",
  accountId: "acc_123",
  scorecardId: "sc_comprehensive",
  scoreId: "score_comprehensive",
  scorecard: {
    id: "sc_comprehensive",
    name: "Comprehensive Quality Assessment",
    externalId: "cqa-v4.0"
  },
  score: {
    id: "score_comprehensive",
    name: "Multi-Dimensional Analysis",
    externalId: "mda-v2.1"
  },
  updatedAt: "2024-01-15T16:20:15Z",
  createdAt: "2024-01-15T16:18:30Z"
}

// Basic stories
export const Default: Story = {
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Default score result card with basic information including value, explanation, and metadata.'
      }
    }
  }
}

export const FullWidth: Story = {
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: true,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card in full width mode for expanded viewing.'
      }
    }
  }
}

export const WithCloseButton: Story = {
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false,
    onClose: () => console.log('Close clicked')
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with close button enabled.'
      }
    }
  }
}

export const NaturalHeight: Story = {
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: true
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with natural height instead of fixed height.'
      }
    }
  }
}

// Content variations
export const DetailedWithTrace: Story = {
  args: {
    scoreResult: detailedScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with detailed explanation, trace data, and attachments.'
      }
    }
  }
}

export const MinimalData: Story = {
  args: {
    scoreResult: minimalScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with minimal data - only required fields populated.'
      }
    }
  }
}

export const LongExplanation: Story = {
  args: {
    scoreResult: longExplanationScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with very long markdown explanation to test content handling.'
      }
    }
  }
}

export const NoConfidence: Story = {
  args: {
    scoreResult: {
      ...basicScoreResult,
      confidence: null
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card without confidence score.'
      }
    }
  }
}

export const NoExplanation: Story = {
  args: {
    scoreResult: {
      ...basicScoreResult,
      explanation: undefined
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card without explanation text.'
      }
    }
  }
}

export const NoScorecard: Story = {
  args: {
    scoreResult: {
      ...basicScoreResult,
      scorecard: undefined,
      score: undefined
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card without scorecard and score information.'
      }
    }
  }
}

// Loading and skeleton states
export const SkeletonMode: Story = {
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: false,
    skeletonMode: true,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card in skeleton loading mode.'
      }
    }
  }
}

export const SkeletonFullWidth: Story = {
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: true,
    skeletonMode: true,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card in skeleton loading mode with full width.'
      }
    }
  }
}

// Interactive states
export const AllInteractions: Story = {
  args: {
    scoreResult: detailedScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close clicked')
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with all interactive elements enabled (toggle full width and close).'
      }
    }
  }
}

// Edge cases
export const VeryLongValue: Story = {
  args: {
    scoreResult: {
      ...basicScoreResult,
      value: "This is an extremely long value that might cause layout issues in the badge component"
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with very long value to test badge handling.'
      }
    }
  }
}

export const HighConfidence: Story = {
  args: {
    scoreResult: {
      ...basicScoreResult,
      confidence: 0.99
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with very high confidence score.'
      }
    }
  }
}

export const LowConfidence: Story = {
  args: {
    scoreResult: {
      ...basicScoreResult,
      confidence: 0.12
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with very low confidence score.'
      }
    }
  }
}

export const WithTraceJson: Story = {
  args: {
    scoreResult: {
      ...detailedScoreResult,
      attachments: [
        "/tmp/conversation_transcript.txt",
        "/tmp/trace.json"
      ]
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with trace.json attachment showing the trace section above attachments.'
      }
    }
  }
}

export const WithoutTraceJson: Story = {
  args: {
    scoreResult: {
      ...detailedScoreResult,
      trace: null,
      attachments: [
        "/tmp/conversation_transcript.txt",
        "/tmp/analysis_report.json"
      ]
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card without trace.json attachment - trace section should not appear.'
      }
    }
  }
}

export const MultipleAttachments: Story = {
  args: {
    scoreResult: {
      ...detailedScoreResult,
      attachments: [
        "/tmp/conversation_transcript.txt",
        "/tmp/analysis_report.json",
        "/tmp/audio_recording.wav",
        "/tmp/customer_feedback.pdf",
        "/tmp/agent_notes.md",
        "/tmp/trace.json"
      ]
    },
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: false
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card with multiple attachments including trace.json to test accordion behavior and trace section.'
      }
    }
  }
}

// Layout testing
export const InContainer: Story = {
  render: (args) => (
    <div className="bg-background p-4 border rounded-lg">
      <h2 className="text-lg font-semibold mb-4">Score Result Container</h2>
      <ScoreResultCard {...args} />
    </div>
  ),
  args: {
    scoreResult: basicScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: true
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card displayed within a container to show integration context.'
      }
    }
  }
}

export const ResponsiveTest: Story = {
  render: (args) => (
    <div className="space-y-4">
      <div className="w-96">
        <h3 className="text-sm font-medium mb-2">Small Width (384px)</h3>
        <ScoreResultCard {...args} />
      </div>
      <div className="w-full max-w-2xl">
        <h3 className="text-sm font-medium mb-2">Medium Width (672px)</h3>
        <ScoreResultCard {...args} />
      </div>
    </div>
  ),
  args: {
    scoreResult: detailedScoreResult,
    isFullWidth: false,
    skeletonMode: false,
    naturalHeight: true
  },
  parameters: {
    docs: {
      description: {
        story: 'Score result card at different widths to test responsive behavior.'
      }
    }
  }
} 