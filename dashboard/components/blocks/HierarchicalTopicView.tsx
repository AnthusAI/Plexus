"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { ChevronDown, ChevronRight, Network, MessagesSquare } from 'lucide-react';

// Import the existing components from TopicAnalysis
import { TopicNgramsSection, TopicExamplesSection, cleanTopicName } from './TopicAnalysis';

export interface TopicExample {
  id?: any;
  text: string;
  [key: string]: any;
}

export interface Topic {
  id: number;
  name: string;
  count: number;
  representation: string;
  keywords: string[];
  examples?: TopicExample[];
}

interface HierarchicalNode {
  id: number;
  name: string;
  count?: number;
  distance?: number;
  is_leaf: boolean;
  children: number[];
}

interface HierarchicalData {
  leaf_topics: { [key: number]: HierarchicalNode };
  parent_nodes: { [key: number]: HierarchicalNode };
  metadata: {
    total_leaf_topics: number;
    total_parent_nodes: number;
    max_distance: number;
  };
}

interface HierarchicalTopicViewProps {
  hierarchicalData: HierarchicalData;
  topics: Topic[];
  attachedFiles?: string[];
  completeTopicsData?: any;
  loadingCompleteData?: boolean;
  fetchCompleteTopicsData?: () => void;
}

/**
 * Hierarchical Topic View Component
 * Displays topics in a tree structure with parent-child relationships
 * Each leaf topic shows full details including word clouds and examples
 */
export const HierarchicalTopicView: React.FC<HierarchicalTopicViewProps> = ({
  hierarchicalData,
  topics,
  attachedFiles,
  completeTopicsData,
  loadingCompleteData,
  fetchCompleteTopicsData
}) => {
  const [expandedAccordions, setExpandedAccordions] = useState<string[]>([]);

  // Create a map of topic ID to full topic data
  const topicMap = new Map<number, Topic>();
  topics.forEach(topic => {
    topicMap.set(topic.id, topic);
  });

  // Find the root node (the node with the highest ID, which is the final merge)
  const findRootNode = (): number | null => {
    const parentIds = Object.keys(hierarchicalData.parent_nodes).map(Number);
    if (parentIds.length === 0) return null;
    return Math.max(...parentIds);
  };

  const handleAccordionChange = (value: string[]) => {
    setExpandedAccordions(value);
    // Load complete data when any topic is expanded
    if (value.length > 0 && fetchCompleteTopicsData) {
      fetchCompleteTopicsData();
    }
  };

  const renderLeafTopic = (nodeId: number, depth: number = 0): React.ReactNode => {
    const leafNode = hierarchicalData.leaf_topics[nodeId];
    const topic = topicMap.get(nodeId);
    
    if (!leafNode || !topic) return null;

    // Get examples from complete data if available
    const getTopicExamples = () => {
      if (topic.examples && topic.examples.length > 0) {
        return topic.examples;
      }
      
      if (completeTopicsData?.topics) {
        const completeTopic = completeTopicsData.topics.find((t: any) => t.id === topic.id);
        return completeTopic?.examples || [];
      }
      
      return [];
    };
    
    const topicExamples = getTopicExamples();
    const accordionValue = `leaf-${nodeId}`;
    const isExpanded = expandedAccordions.includes(accordionValue);

    return (
      <AccordionItem 
        key={`leaf-${nodeId}`} 
        value={accordionValue}
        className="mb-4"
        style={{ marginLeft: `${depth * 24}px` }}
      >
        <AccordionTrigger 
          className={`py-2 px-3 rounded-lg transition-colors ${
            isExpanded ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/50'
          }`}
          onClick={() => {
            // Load complete data when a topic is expanded
            if (fetchCompleteTopicsData) {
              fetchCompleteTopicsData();
            }
          }}
        >
          <div className="flex items-center justify-between w-full pr-4">
            <span className="font-medium text-left">{cleanTopicName(topic.name)}</span>
            <Badge variant="secondary" className="border-none bg-card font-normal">{topic.count} items</Badge>
          </div>
        </AccordionTrigger>
        <AccordionContent>
          <div className="space-y-4 p-1">
            {/* Word Cloud and Keywords with c-TF-IDF scores */}
            <TopicNgramsSection 
              topicId={topic.id}
              topicName={topic.name}
              attachedFiles={attachedFiles}
            />
            
            {loadingCompleteData && (
              <div className="text-xs text-muted-foreground italic">
                Loading examples...
              </div>
            )}
            
            {!loadingCompleteData && topicExamples.length > 0 && (
              <TopicExamplesSection examples={topicExamples} />
            )}
            
            {!loadingCompleteData && topicExamples.length === 0 && (
              <div className="text-xs text-muted-foreground italic">
                No examples available for this topic
              </div>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    );
  };

  const renderParentNode = (nodeId: number, depth: number = 0): React.ReactNode => {
    const parentNode = hierarchicalData.parent_nodes[nodeId];
    if (!parentNode) return null;

    const accordionValue = `parent-${nodeId}`;
    const isExpanded = expandedAccordions.includes(accordionValue);

    return (
      <AccordionItem 
        key={`parent-${nodeId}`} 
        value={accordionValue}
        className="mb-4"
        style={{ marginLeft: `${depth * 24}px` }}
      >
        <AccordionTrigger 
          className={`py-2 px-3 rounded-lg transition-colors ${
            isExpanded ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/50'
          }`}
        >
          <div className="flex items-center justify-between w-full pr-4">
            <div className="flex items-center gap-2">
              <Network className={`h-4 w-4 ${isExpanded ? 'text-primary-foreground' : 'text-muted-foreground'}`} />
              <span className="font-medium text-left">
                {cleanTopicName(parentNode.name)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={isExpanded ? "secondary" : "outline"} className={`text-xs ${isExpanded ? 'border-none bg-card font-normal' : ''}`}>
                {parentNode.children.length} sub-topics
              </Badge>
              {parentNode.distance !== undefined && (
                <Badge variant={isExpanded ? "secondary" : "outline"} className={`text-xs ${isExpanded ? 'border-none bg-card font-normal' : ''}`}>
                  {(1 - parentNode.distance).toFixed(2)} similar
                </Badge>
              )}
            </div>
          </div>
        </AccordionTrigger>
        <AccordionContent>
          <div className="pt-2 space-y-2">
            {/* Recursively render children */}
            <Accordion 
              type="multiple" 
              value={expandedAccordions}
              onValueChange={handleAccordionChange}
            >
              {parentNode.children.map(childId => renderNode(childId, depth + 1))}
            </Accordion>
          </div>
        </AccordionContent>
      </AccordionItem>
    );
  };

  const renderNode = (nodeId: number, depth: number = 0): React.ReactNode => {
    // Check if it's a leaf topic first
    if (hierarchicalData.leaf_topics[nodeId]) {
      return renderLeafTopic(nodeId, depth);
    }
    // Otherwise it's a parent node
    return renderParentNode(nodeId, depth);
  };

  const rootNodeId = findRootNode();

  // If no parent nodes exist, show all leaf topics in a flat list
  if (!rootNodeId) {
    const leafTopicIds = Object.keys(hierarchicalData.leaf_topics)
      .map(Number)
      .sort((a, b) => {
        const topicA = topicMap.get(a);
        const topicB = topicMap.get(b);
        return (topicB?.count || 0) - (topicA?.count || 0);
      });
    
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
          <Badge variant="secondary" className="ml-2">
            {hierarchicalData.metadata.total_leaf_topics} topics
          </Badge>
        </div>

        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Click on any topic to see word clouds, keyword scores, and examples.
          </p>
          <Accordion 
            type="multiple" 
            value={expandedAccordions}
            onValueChange={handleAccordionChange}
          >
            {leafTopicIds.map(topicId => renderLeafTopic(topicId, 0))}
          </Accordion>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <MessagesSquare className="h-5 w-5" />
        <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        <Badge variant="secondary" className="ml-2">
          {hierarchicalData.metadata.total_leaf_topics} topics
        </Badge>
      </div>

      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          Topics are organized hierarchically. Parent nodes (with <Network className="h-3 w-3 inline" /> icon) group similar topics together. 
          Expand any leaf topic to see word clouds, keyword scores, and examples.
        </p>
        <Accordion 
          type="multiple" 
          value={expandedAccordions}
          onValueChange={handleAccordionChange}
        >
          {renderNode(rootNodeId, 0)}
        </Accordion>
      </div>
    </div>
  );
};
