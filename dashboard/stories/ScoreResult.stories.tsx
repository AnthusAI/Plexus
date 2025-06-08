import type { Meta, StoryObj } from '@storybook/react'
import { ScoreResultComponent } from '../components/ui/score-result'

const meta: Meta<typeof ScoreResultComponent> = {
  title: 'Scorecards/ScoreResult',
  component: ScoreResultComponent,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'radio',
      options: ['list', 'detail'],
      description: 'Display variant - list (compact) or detail (full view)'
    },
    isFocused: {
      control: 'boolean',
      description: 'Whether the result is focused/selected (only applies to list variant)'
    },
    onSelect: { action: 'selected' },
    onClose: { action: 'closed' }
  },
  decorators: [
    (Story) => (
      <div style={{ maxWidth: '800px', width: '100%' }}>
        <Story />
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof ScoreResultComponent>

// Realistic trace data in the format provided in the example
const realisticTraceData = {
  "node_results": [
    {
      "output": {
        "explanation": "1. The 2-party commitment question occurs in the transcript at the following point: \n   \"Agent: ...we also ask to meet with all owners of the property, and that could include other family members, partners, significant others, or spouses. Fair enough?\"\n\n2. Analyzing what the customer said before this point, the customer did not mention having a spouse, co-owner, or any family members involved in property decisions. The customer only stated that they own the property and did not provide any information about other owners or decision-makers.\n\n3. Since the customer did not mention any spouse or co-owners before the 2-party commitment question, no relevant text meets the conditions.\n\n4. Therefore, none of the conditions were met before the 2-party commitment question.\n\nFinal Answer: No"
      },
      "input": {},
      "node_name": "na_classifier"
    },
    {
      "output": {
        "explanation": "Required Phrases Present: \n1. \"Besides yourself\" - Present\n2. \"else owns, helps make decisions on\" - Present\n3. \"property or that you would like to have present\" - Present\n4. \"when we visit\" - Present\n5. \"Thank you - I'll go ahead\" - Not applicable (customer did not indicate sole ownership)\n6. \"and notate the account to reflect that\" - Not applicable (customer did not indicate sole ownership)\n\nName Collection: The agent obtained the name of the spouse, Renata, as she was identified as a decision-maker.\n\nSpecial Circumstances: The customer did not interrupt claiming sole ownership; instead, they provided the name of their wife when asked.\n\nFinal Answer: Yes"
      },
      "input": {},
      "node_name": "multi_class_classifier"
    }
  ]
};

// Sample long text for collapsible text feature
const longText = `Agent: Hello. Good morning, and thank you for calling. My name is Sarah. How can I help you today?
Customer: Hi, I'm calling about my internet service. It's been really slow lately.
Agent: I'm sorry to hear that. I'd be happy to help you troubleshoot that issue. Before we begin, may I have your name please?
Customer: It's John Smith.
Agent: Thank you, Mr. Smith. And besides yourself, is there anyone else who owns, helps make decisions on this property, or that you would like to have present when we visit?
Customer: Yes, my wife Renata.
Agent: Great, thank you for that information. Now, let's take a look at your internet service...
Customer: Thanks.
Agent: You're welcome. Bye bye.
Agent: Bye bye.`;

// Base result data
const baseResult = {
  id: '1',
  value: 'Yes',
  confidence: 0.95,
  explanation: "Required Phrases Present: \n1. \"Besides yourself\" - Present\n2. \"else owns, helps make decisions on\" - Present\n3. \"property or that you would like to have present\" - Present\n4. \"when we visit\" - Present\n5. \"Thank you - I'll go ahead\" - Not applicable (customer did not indicate sole ownership)\n6. \"and notate the account to reflect that\" - Not applicable (customer did not indicate sole ownership)\n\nName Collection: The agent obtained the name of the spouse, Renata, as she was identified as a decision-maker.\n\nSpecial Circumstances: The customer did not interrupt claiming sole ownership; instead, they provided the name of their wife when asked.\n\nFinal Answer: Yes",
  metadata: {
    human_label: 'yes',
    correct: true,
    human_explanation: "Proactively stated the name of the customer's wife.",
    text: longText
  },
  trace: realisticTraceData,
  itemId: '49445947'
};

export const ListVariantCorrect: Story = {
  args: {
    result: baseResult,
    variant: 'list',
    isFocused: false
  },
};

export const ListVariantFocused: Story = {
  args: {
    result: baseResult,
    variant: 'list',
    isFocused: true
  },
};

export const ListVariantIncorrect: Story = {
  args: {
    result: {
      ...baseResult,
      value: 'No',
      confidence: 0.65,
      metadata: {
        ...baseResult.metadata,
        human_label: 'yes',
        correct: false,
        human_explanation: "The agent should have asked for the name of the decision maker."
      }
    },
    variant: 'list',
    isFocused: false
  },
};

export const DetailVariantWithTrace: Story = {
  args: {
    result: baseResult,
    variant: 'detail'
  },
};

export const DetailVariantNoTrace: Story = {
  args: {
    result: {
      ...baseResult,
      trace: null
    },
    variant: 'detail'
  },
};

export const DetailVariantIncorrect: Story = {
  args: {
    result: {
      ...baseResult,
      value: 'No',
      confidence: 0.65,
      metadata: {
        ...baseResult.metadata,
        human_label: 'yes',
        correct: false,
        human_explanation: "The agent should have asked for the name of the decision maker."
      }
    },
    variant: 'detail'
  },
};

export const DetailVariantWithStringTrace: Story = {
  args: {
    result: {
      ...baseResult,
      trace: JSON.stringify(realisticTraceData)
    },
    variant: 'detail'
  },
  name: 'Detail Variant with String Trace'
}; 