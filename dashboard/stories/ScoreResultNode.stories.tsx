import type { Meta, StoryObj } from '@storybook/react'
import { ScoreResultNode } from '../components/ui/score-result-node'

const meta: Meta<typeof ScoreResultNode> = {
  title: 'Components/ScoreResultNode',
  component: ScoreResultNode,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: '600px', width: '100%' }}>
        <Story />
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof ScoreResultNode>

// Realistic classifier node
export const ClassifierNode: Story = {
  args: {
    name: "multi_class_classifier",
    inputs: {},
    outputs: { 
      explanation: "Required Phrases Present: \n1. \"Besides yourself\" - Present\n2. \"else owns, helps make decisions on\" - Present\n3. \"property or that you would like to have present\" - Present\n4. \"when we visit\" - Present\n5. \"Thank you - I'll go ahead\" - Not applicable (customer did not indicate sole ownership)\n6. \"and notate the account to reflect that\" - Not applicable (customer did not indicate sole ownership)\n\nName Collection: The agent obtained the name of the spouse, Renata, as she was identified as a decision-maker.\n\nSpecial Circumstances: The customer did not interrupt claiming sole ownership; instead, they provided the name of their wife when asked.\n\nFinal Answer: Yes"
    }
  },
};

// Another realistic classifier node
export const NAClassifierNode: Story = {
  args: {
    name: "na_classifier",
    inputs: {},
    outputs: { 
      explanation: "1. The 2-party commitment question occurs in the transcript at the following point: \n   \"Agent: ...we also ask to meet with all owners of the property, and that could include other family members, partners, significant others, or spouses. Fair enough?\"\n\n2. Analyzing what the customer said before this point, the customer did not mention having a spouse, co-owner, or any family members involved in property decisions. The customer only stated that they own the property and did not provide any information about other owners or decision-makers.\n\n3. Since the customer did not mention any spouse or co-owners before the 2-party commitment question, no relevant text meets the conditions.\n\n4. Therefore, none of the conditions were met before the 2-party commitment question.\n\nFinal Answer: No"
    }
  },
};

// Node with more complex inputs and outputs
export const LLMPromptNode: Story = {
  args: {
    name: "llm_prompt",
    inputs: { 
      prompt: "Analyze the following customer service transcript and determine if the agent properly asked about other decision makers:",
      transcript: "Agent: Hello. Good morning, and thank you for calling. My name is Sarah. How can I help you today?\nCustomer: Hi, I'm calling about my internet service. It's been really slow lately.\nAgent: I'm sorry to hear that. I'd be happy to help you troubleshoot that issue. Before we begin, may I have your name please?\nCustomer: It's John Smith.\nAgent: Thank you, Mr. Smith. And besides yourself, is there anyone else who owns, helps make decisions on this property, or that you would like to have present when we visit?\nCustomer: Yes, my wife Renata.\nAgent: Great, thank you for that information. Now, let's take a look at your internet service...",
      model: "gpt-4",
      temperature: 0.2
    },
    outputs: { 
      response: "Yes, the agent properly asked about other decision makers. The agent specifically asked \"And besides yourself, is there anyone else who owns, helps make decisions on this property, or that you would like to have present when we visit?\" This question clearly seeks to identify any other individuals who might be involved in making decisions about the property or service. The customer responded by identifying his wife Renata as another decision maker, and the agent acknowledged this information appropriately.",
      tokens_used: 87,
      model: "gpt-4-0613"
    }
  },
};

// Node with document retrieval
export const RetrievalNode: Story = {
  args: {
    name: "retrieve_documents",
    inputs: { 
      query: "two-party commitment requirements",
      collection: "policy_documents",
      top_k: 3
    },
    outputs: { 
      documents: [
        { 
          id: "policy-2023-05",
          title: "Two-Party Commitment Policy",
          content: "Agents must identify all decision makers for a property. This includes spouses, partners, co-owners, and any other individuals who help make decisions about the property.",
          relevance: 0.92
        },
        { 
          id: "training-2023-06",
          title: "Agent Training Manual",
          content: "When speaking with customers, always ask: 'Besides yourself, is there anyone else who owns, helps make decisions on this property, or that you would like to have present when we visit?'",
          relevance: 0.87
        },
        { 
          id: "compliance-2023-04",
          title: "Compliance Guidelines",
          content: "Failure to identify all decision makers may result in regulatory violations. Ensure all parties are present during service discussions.",
          relevance: 0.76
        }
      ],
      search_time_ms: 120
    }
  },
};

// Multiple nodes in a sequence (realistic workflow)
export const RealisticWorkflow: Story = {
  render: () => (
    <div>
      <ScoreResultNode 
        name="na_classifier" 
        inputs={{}} 
        outputs={{ 
          explanation: "1. The 2-party commitment question occurs in the transcript at the following point: \n   \"Agent: ...we also ask to meet with all owners of the property, and that could include other family members, partners, significant others, or spouses. Fair enough?\"\n\n2. Analyzing what the customer said before this point, the customer did not mention having a spouse, co-owner, or any family members involved in property decisions. The customer only stated that they own the property and did not provide any information about other owners or decision-makers.\n\n3. Since the customer did not mention any spouse or co-owners before the 2-party commitment question, no relevant text meets the conditions.\n\n4. Therefore, none of the conditions were met before the 2-party commitment question.\n\nFinal Answer: No"
        }}
      />
      <ScoreResultNode 
        name="multi_class_classifier" 
        inputs={{}} 
        outputs={{ 
          explanation: "Required Phrases Present: \n1. \"Besides yourself\" - Present\n2. \"else owns, helps make decisions on\" - Present\n3. \"property or that you would like to have present\" - Present\n4. \"when we visit\" - Present\n5. \"Thank you - I'll go ahead\" - Not applicable (customer did not indicate sole ownership)\n6. \"and notate the account to reflect that\" - Not applicable (customer did not indicate sole ownership)\n\nName Collection: The agent obtained the name of the spouse, Renata, as she was identified as a decision-maker.\n\nSpecial Circumstances: The customer did not interrupt claiming sole ownership; instead, they provided the name of their wife when asked.\n\nFinal Answer: Yes"
        }}
      />
    </div>
  )
}; 