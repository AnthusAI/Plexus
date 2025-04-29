import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BaseBlock } from '@/components/blocks/BaseBlock';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof BaseBlock> = {
  title: 'Report Blocks/BaseBlock',
  component: BaseBlock,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof BaseBlock>;

// Basic examples of the BaseBlock on its own
export const Basic: Story = {
  args: {
    name: 'Score Information',
    output: {
      name: 'Temperature Check',
      description: 'A score that measures the customer\'s sentiment',
      accuracy: 0.92,
      value: 0.78,
      updatedAt: '2023-10-27T10:05:00Z',
    },
  },
};

export const LongContent: Story = {
  args: {
    name: 'Customer Feedback Analysis',
    output: {
      feedback_categories: {
        positive: [
          'User interface is intuitive',
          'Customer service is responsive',
          'Navigation is clear and logical',
          'Documentation is helpful and detailed',
          'Search functionality works well',
        ],
        negative: [
          'Loading times could be improved',
          'Occasional errors when submitting forms',
          'Missing advanced filtering options',
          'Limited export capabilities',
          'Some features are difficult to discover',
        ],
        neutral: [
          'Would like to see more customization options',
          'Instructions could be clearer in some areas',
          'Not sure about the pricing model',
          'Integration with other tools is adequate',
          'Update frequency is reasonable but could be faster',
        ],
      },
      sentiment_analysis: {
        overall_score: 0.65,
        breakdown: {
          positive: 0.72,
          negative: 0.23,
          neutral: 0.05,
        },
        trend: 'Improving',
        commonWords: ['easy', 'helpful', 'slow', 'confusing', 'reliable', 'intuitive'],
        longTextExample: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
      },
    },
  },
};

export const VeryLongJsonContent: Story = {
  args: {
    name: 'Topic Modeling Results',
    output: {
      topics: {
        topic1: {
          label: 'Technical Support',
          keywords: ['help', 'support', 'issue', 'problem', 'fix', 'error', 'bug', 'crash', 'troubleshoot', 'resolve'],
          documentCount: 457,
          averageSentiment: -0.23,
          topDocuments: [
            { id: 'doc-1234', title: 'System crash during startup', sentiment: -0.78, text: 'The application consistently crashes during startup after the latest update. I\'ve tried reinstalling but the problem persists.' },
            { id: 'doc-2345', title: 'API integration failing', sentiment: -0.65, text: 'The API integration is failing with a 403 error. We\'ve verified our credentials are correct but can\'t access the data.' },
            { id: 'doc-3456', title: 'Slow performance on large datasets', sentiment: -0.42, text: 'The system becomes extremely slow when processing datasets larger than 100MB. This is affecting our workflow.' },
          ],
          relatedTopics: ['Performance Issues', 'User Interface Problems', 'Installation Difficulties'],
          trendData: [
            { date: '2023-01', count: 42, sentiment: -0.31 },
            { date: '2023-02', count: 51, sentiment: -0.27 },
            { date: '2023-03', count: 38, sentiment: -0.24 },
            { date: '2023-04', count: 45, sentiment: -0.23 },
            { date: '2023-05', count: 39, sentiment: -0.20 },
          ],
          detailedAnalysis: 'Technical support issues appear to be decreasing in severity over time, though the volume remains consistent. Most common problems relate to startup issues, integration failures, and performance degradation with larger datasets. User sentiment is generally negative but showing slight improvement in recent months, possibly correlating with the fixes implemented in version 2.5.3.'
        },
        topic2: {
          label: 'Feature Requests',
          keywords: ['add', 'feature', 'ability', 'enhance', 'improvement', 'suggestion', 'option', 'functionality', 'implement', 'include'],
          documentCount: 312,
          averageSentiment: 0.45,
          topDocuments: [
            { id: 'doc-7890', title: 'Add dark mode option', sentiment: 0.82, text: 'Would love to see a dark mode option added to reduce eye strain when working late hours.' },
            { id: 'doc-8901', title: 'Bulk editing capabilities', sentiment: 0.67, text: 'The ability to select and edit multiple items at once would greatly improve productivity.' },
            { id: 'doc-9012', title: 'Integration with third-party calendars', sentiment: 0.53, text: 'Please add integration with Google Calendar and Outlook to streamline scheduling.' },
          ],
          relatedTopics: ['User Interface Improvements', 'Workflow Enhancements', 'Integration Possibilities'],
          trendData: [
            { date: '2023-01', count: 27, sentiment: 0.41 },
            { date: '2023-02', count: 32, sentiment: 0.43 },
            { date: '2023-03', count: 35, sentiment: 0.44 },
            { date: '2023-04', count: 41, sentiment: 0.46 },
            { date: '2023-05', count: 45, sentiment: 0.47 },
          ],
          detailedAnalysis: 'Feature requests have been increasing steadily, with generally positive sentiment. Users are enthusiastic about potential improvements, particularly focusing on interface customization, batch operations, and additional integrations. This topic appears to represent engaged users who are invested in the product\'s continued development and are providing constructive feedback.'
        },
        topic3: {
          label: 'User Interface Feedback',
          keywords: ['interface', 'ui', 'design', 'layout', 'button', 'menu', 'screen', 'display', 'visual', 'find'],
          documentCount: 289,
          averageSentiment: 0.12,
          topDocuments: [
            { id: 'doc-4567', title: 'Confusing navigation structure', sentiment: -0.45, text: 'The navigation menu is not intuitive. It takes too many clicks to find commonly used features.' },
            { id: 'doc-5678', title: 'Love the new dashboard', sentiment: 0.91, text: 'The redesigned dashboard is fantastic! Much easier to see all the important information at a glance.' },
            { id: 'doc-6789', title: 'Inconsistent button placement', sentiment: -0.33, text: 'The positioning of action buttons changes between different screens, making the interface feel inconsistent.' },
          ],
          relatedTopics: ['Usability Issues', 'Feature Requests', 'Mobile Experience'],
          trendData: [
            { date: '2023-01', count: 35, sentiment: 0.05 },
            { date: '2023-02', count: 29, sentiment: 0.07 },
            { date: '2023-03', count: 42, sentiment: 0.11 },
            { date: '2023-04', count: 38, sentiment: 0.14 },
            { date: '2023-05', count: 31, sentiment: 0.18 },
          ],
          detailedAnalysis: 'User interface feedback is mixed but trending slightly more positive over time. Recent dashboard improvements have been well-received, while navigation and consistency issues remain pain points. Mobile experience comments have increased 43% in the last quarter, suggesting more users are accessing the application on mobile devices.'
        },
      },
      metadata: {
        analysisDate: '2023-06-15',
        dataRange: { start: '2023-01-01', end: '2023-05-31' },
        documentCount: 1058,
        modelVersion: '3.2.1',
        processingTime: 124.5,
        confidenceScore: 0.87,
        notes: 'Topic clustering performed using LDA with optimized hyperparameters. Sentiment analysis conducted using fine-tuned BERT model.',
      },
    },
  },
};

// Type definition for the report task props
type ReportTaskData = {
  id: string;
  title: string;
  name?: string;
  configName?: string;
  configDescription?: string;
  createdAt?: string;
  updatedAt?: string;
  output?: string;
};

type TaskType = BaseTaskProps<ReportTaskData>['task'];

// Helper to create a ReportTask with a BaseBlock embedded in markdown output
const createReportTaskWithBlock = (id: string, blockName: string, blockOutput: any) => {
  const taskData: TaskType = {
    id,
    type: 'Report',
    scorecard: 'Report Analysis',
    score: '',
    time: '2 hours ago',
    status: 'COMPLETED',
    name: 'Sample Report',
    description: 'A test report that includes our BaseBlock component',
    data: {
      id,
      title: 'Sample Report',
      name: 'Test Report',
      configName: 'Report Analysis',
      configDescription: 'A test report that includes our BaseBlock component',
      createdAt: '2023-06-15T10:00:00Z',
      updatedAt: '2023-06-15T10:05:00Z',
      output: `# Test Report with Block

This is a sample report that includes a block component.

\`\`\`block
class: TestBlock
name: ${blockName}
\`\`\`

Some additional text after the block.
`,
    },
  };

  return {
    task: taskData,
    blockOutput: blockOutput,
  };
};

// Create a component that renders a ReportTask with a BaseBlock
const ReportTaskWithBlock = ({ task, blockOutput }: { task: TaskType, blockOutput: any }) => {
  // Mock the reportBlocks state that would normally be fetched
  React.useEffect(() => {
    // In a real component, this would be set by the fetchReportBlocks function
    // For the story, we're just simulating that the blocks were loaded
    // This is just for demonstration purposes
    console.log('Mock report blocks would be loaded with:', {
      id: 'block1',
      name: task.data?.name || 'Test Block',
      position: 0,
      output: {
        type: 'TestBlock',
        data: blockOutput
      },
      log: 'Block generated successfully'
    });
  }, [blockOutput, task.data?.name]);

  return (
    <div className="w-full max-w-4xl mx-auto">
      <ReportTask 
        variant="detail" 
        task={task} 
        onClick={() => {}}
        isFullWidth={true}
      />
    </div>
  );
};

// Story for the BaseBlock inside a ReportTask
export const InReportTask: Story = {
  render: () => {
    const { task, blockOutput } = createReportTaskWithBlock(
      'report-with-block',
      'Score Information',
      {
        name: 'Temperature Check',
        description: 'A score that measures the customer\'s sentiment',
        accuracy: 0.92,
        value: 0.78,
        updatedAt: '2023-10-27T10:05:00Z',
      }
    );
    
    return (
      <div className="p-4 max-w-full">
        <h1 className="text-xl font-bold mb-4">BaseBlock in Report Task Context</h1>
        <div className="border rounded shadow-sm p-4">
          <ReportTaskWithBlock task={task} blockOutput={blockOutput} />
        </div>
      </div>
    );
  }
};

export const LongContentInReportTask: Story = {
  render: () => {
    const { task, blockOutput } = createReportTaskWithBlock(
      'report-with-long-block',
      'Customer Feedback Analysis',
      LongContent.args?.output
    );
    
    return (
      <div className="p-4 max-w-full">
        <h1 className="text-xl font-bold mb-4">BaseBlock with Long Content in Report Task</h1>
        <div className="border rounded shadow-sm p-4">
          <ReportTaskWithBlock task={task} blockOutput={blockOutput} />
        </div>
      </div>
    );
  }
};

export const VeryLongJsonInReportTask: Story = {
  render: () => {
    const { task, blockOutput } = createReportTaskWithBlock(
      'report-with-very-long-json',
      'Topic Modeling Results',
      VeryLongJsonContent.args?.output
    );
    
    return (
      <div className="p-4 max-w-full">
        <h1 className="text-xl font-bold mb-4">BaseBlock with Very Long JSON in Report Task</h1>
        <div className="border rounded shadow-sm p-4">
          <ReportTaskWithBlock task={task} blockOutput={blockOutput} />
        </div>
      </div>
    );
  }
}; 