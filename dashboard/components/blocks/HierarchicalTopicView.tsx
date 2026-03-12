"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { ChevronDown, ChevronRight, Network, MessagesSquare } from 'lucide-react';
import { PieChart, Pie, Cell, Label, ResponsiveContainer, Sector } from 'recharts';
import { PieSectorDataItem } from 'recharts/types/polar/Pie';

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
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);

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

  // Build a path from root to a specific leaf topic
  const findPathToLeaf = (targetLeafId: number): string[] => {
    const path: string[] = [];
    
    // Helper function to search for the leaf in a subtree
    const searchNode = (nodeId: number): boolean => {
      // If this is the target leaf, we found it
      if (nodeId === targetLeafId) {
        path.push(`leaf-${nodeId}`);
        return true;
      }
      
      // If this is a parent node, check its children
      const parentNode = hierarchicalData.parent_nodes[nodeId];
      if (parentNode) {
        for (const childId of parentNode.children) {
          if (searchNode(childId)) {
            // Found the target in this subtree, add this parent to the path
            path.unshift(`parent-${nodeId}`);
            return true;
          }
        }
      }
      
      return false;
    };
    
    // Start search from root
    const rootId = findRootNode();
    if (rootId !== null) {
      searchNode(rootId);
    }
    
    return path;
  };

  const handleAccordionChange = (value: string[]) => {
    setExpandedAccordions(value);
    // Load complete data when any topic is expanded
    if (value.length > 0 && fetchCompleteTopicsData) {
      fetchCompleteTopicsData();
    }
  };

  // Handle topic selection from donut chart
  const handleTopicSelect = (topicId: number) => {
    if (selectedTopicId === topicId) {
      // Deselect - collapse all
      setSelectedTopicId(null);
      setExpandedAccordions([]);
    } else {
      // Select - expand path to this topic
      setSelectedTopicId(topicId);
      const path = findPathToLeaf(topicId);
      setExpandedAccordions(path);
      
      // Load complete data
      if (fetchCompleteTopicsData) {
        fetchCompleteTopicsData();
      }
    }
  };

  const renderLeafTopic = (nodeId: number, depth: number = 0, isLastSibling: boolean = false): React.ReactNode => {
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
        className="mb-4 relative"
      >
        {/* Tree lines */}
        {depth > 0 && (
          <div 
            className="absolute left-0 top-0 flex pointer-events-none z-10"
            style={{ 
              width: `${depth * 20}px`,
              height: isExpanded ? 'calc(100% + 1rem)' : 'calc(100% + 1rem)' // Extend through margin and content
            }}
          >
            {Array.from({ length: depth }).map((_, i) => {
              // Parent-level lines (not the deepest) always run full height
              // Deepest level line: if last sibling, stop at connector (L shape)
              //                     otherwise, continue through (T shape)
              const isDeepestLevel = i === depth - 1;
              const lineHeight = isDeepestLevel && isLastSibling ? '1.25rem' : '100%';
              
              return (
                <div
                  key={i}
                  className="relative"
                  style={{ width: '20px' }}
                >
                  {/* Vertical line - continues through for T shape, stops for L shape */}
                  <div 
                    className="absolute left-2 top-0 w-px bg-border"
                    style={{ height: lineHeight }}
                  />
                  {/* Horizontal connector line */}
                  {isDeepestLevel && (
                    <div className="absolute left-2 top-[1.25rem] w-2 h-px bg-border" />
                  )}
                </div>
              );
            })}
          </div>
        )}
        
        <AccordionTrigger 
          className={`py-2 px-3 rounded-lg transition-colors ${
            isExpanded ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/50'
          }`}
          style={{ marginLeft: depth > 0 ? `${depth * 20}px` : '0' }}
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
        <AccordionContent style={{ marginLeft: depth > 0 ? `${depth * 20}px` : '0' }}>
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

  const renderParentNode = (nodeId: number, depth: number = 0, isLastSibling: boolean = false): React.ReactNode => {
    const parentNode = hierarchicalData.parent_nodes[nodeId];
    if (!parentNode) return null;

    const accordionValue = `parent-${nodeId}`;
    const isExpanded = expandedAccordions.includes(accordionValue);

    return (
      <AccordionItem 
        key={`parent-${nodeId}`} 
        value={accordionValue}
        className="mb-4 relative"
      >
        {/* Tree lines */}
        {depth > 0 && (
          <div 
            className="absolute left-0 top-0 flex pointer-events-none z-10"
            style={{ 
              width: `${depth * 20}px`,
              height: 'calc(100% + 1rem)' // Always extend through margin
            }}
          >
            {Array.from({ length: depth }).map((_, i) => {
              // Parent-level lines (not the deepest) always run full height
              // Deepest level line: if last sibling, stop at connector (L shape)
              //                     otherwise, continue through (T shape)
              const isDeepestLevel = i === depth - 1;
              const lineHeight = isDeepestLevel && isLastSibling ? '1.25rem' : '100%';
              
              return (
                <div
                  key={i}
                  className="relative"
                  style={{ width: '20px' }}
                >
                  {/* Vertical line - continues through for T shape, stops for L shape */}
                  <div 
                    className="absolute left-2 top-0 w-px bg-border"
                    style={{ height: lineHeight }}
                  />
                  {/* Horizontal connector line */}
                  {isDeepestLevel && (
                    <div className="absolute left-2 top-[1.25rem] w-2 h-px bg-border" />
                  )}
                </div>
              );
            })}
          </div>
        )}
        
        <AccordionTrigger 
          className={`py-2 px-3 rounded-lg transition-colors ${
            isExpanded ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/50'
          }`}
          style={{ marginLeft: depth > 0 ? `${depth * 20}px` : '0' }}
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
              className="[&>*]:border-0"
            >
              {parentNode.children.map((childId, index) => 
                renderNode(childId, depth + 1, index === parentNode.children.length - 1)
              )}
            </Accordion>
          </div>
        </AccordionContent>
      </AccordionItem>
    );
  };

  const renderNode = (nodeId: number, depth: number = 0, isLastSibling: boolean = false): React.ReactNode => {
    // Check if it's a leaf topic first
    if (hierarchicalData.leaf_topics[nodeId]) {
      return renderLeafTopic(nodeId, depth, isLastSibling);
    }
    // Otherwise it's a parent node
    return renderParentNode(nodeId, depth, isLastSibling);
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
    
    // Prepare data for donut chart
    const flatLeafTopics = leafTopicIds
      .map(id => topicMap.get(id))
      .filter((topic): topic is Topic => topic !== undefined);

    const flatChartData = flatLeafTopics.map(topic => ({
      name: cleanTopicName(topic.name),
      value: topic.count,
      id: topic.id,
    }));

    const handleFlatPieClick = (data: any, index: number) => {
      const topicId = flatLeafTopics[index].id;
      handleTopicSelect(topicId);
    };

    const flatSelectedIndex = selectedTopicId !== null 
      ? flatLeafTopics.findIndex(t => t.id === selectedTopicId)
      : -1;
    
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
          <Badge variant="secondary" className="ml-2">
            {hierarchicalData.metadata.total_leaf_topics} topics
          </Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-8 items-start">
          {/* Donut Chart - Left Side */}
          <div className="sticky top-4 sm:col-span-2">
            <div className="w-full mx-auto aspect-square">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={flatChartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius="60%"
                    outerRadius="80%"
                    strokeWidth={2}
                    stroke="hsl(var(--background))"
                    paddingAngle={2}
                    activeIndex={flatSelectedIndex >= 0 ? flatSelectedIndex : undefined}
                    activeShape={({
                      outerRadius = 0,
                      ...props
                    }: PieSectorDataItem) => (
                      <Sector {...props} outerRadius={outerRadius + 20} />
                    )}
                    onClick={handleFlatPieClick}
                  >
                    {flatChartData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={`var(--chart-${(index % 7) + 1})`}
                        style={{ cursor: 'pointer', outline: 'none' }}
                      />
                    ))}
                    <Label
                      content={({ viewBox }) => {
                        if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                          return (
                            <text
                              x={viewBox.cx}
                              y={viewBox.cy}
                              textAnchor="middle"
                              dominantBaseline="middle"
                            >
                              <tspan
                                x={viewBox.cx}
                                y={viewBox.cy}
                                className="fill-foreground text-3xl font-bold"
                              >
                                {flatLeafTopics.length.toLocaleString()}
                              </tspan>
                              <tspan
                                x={viewBox.cx}
                                y={(viewBox.cy || 0) + 24}
                                className="fill-muted-foreground"
                              >
                                Topics
                              </tspan>
                            </text>
                          );
                        }
                        return null;
                      }}
                      position="center"
                    />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Topic List - Right Side */}
          <div className="sm:col-span-3">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Click on the chart or any topic to see word clouds, keyword scores, and examples.
              </p>
              <Accordion 
                type="multiple" 
                value={expandedAccordions}
                onValueChange={handleAccordionChange}
              >
                {leafTopicIds.map((topicId, index) => 
                  renderLeafTopic(topicId, 0, index === leafTopicIds.length - 1)
                )}
              </Accordion>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Prepare data for donut chart - only leaf topics
  const leafTopics = Object.keys(hierarchicalData.leaf_topics)
    .map(Number)
    .map(id => topicMap.get(id))
    .filter((topic): topic is Topic => topic !== undefined)
    .sort((a, b) => b.count - a.count); // Sort by count descending

  const chartData = leafTopics.map(topic => ({
    name: cleanTopicName(topic.name),
    value: topic.count,
    id: topic.id,
  }));

  const handlePieClick = (data: any, index: number) => {
    const topicId = leafTopics[index].id;
    handleTopicSelect(topicId);
  };

  // Find the index of the selected topic for highlighting in the chart
  const selectedChartIndex = selectedTopicId !== null 
    ? leafTopics.findIndex(t => t.id === selectedTopicId)
    : -1;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <MessagesSquare className="h-5 w-5" />
        <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        <Badge variant="secondary" className="ml-2">
          {hierarchicalData.metadata.total_leaf_topics} topics
        </Badge>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-8 items-start">
        {/* Donut Chart - Left Side */}
        <div className="sticky top-4 sm:col-span-2">
          <div className="w-full mx-auto aspect-square">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="60%"
                  outerRadius="80%"
                  strokeWidth={2}
                  stroke="hsl(var(--background))"
                  paddingAngle={2}
                  activeIndex={selectedChartIndex >= 0 ? selectedChartIndex : undefined}
                  activeShape={({
                    outerRadius = 0,
                    ...props
                  }: PieSectorDataItem) => (
                    <Sector {...props} outerRadius={outerRadius + 20} />
                  )}
                  onClick={handlePieClick}
                >
                  {chartData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={`var(--chart-${(index % 7) + 1})`}
                      style={{ cursor: 'pointer', outline: 'none' }}
                    />
                  ))}
                  <Label
                    content={({ viewBox }) => {
                      if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                        return (
                          <text
                            x={viewBox.cx}
                            y={viewBox.cy}
                            textAnchor="middle"
                            dominantBaseline="middle"
                          >
                            <tspan
                              x={viewBox.cx}
                              y={viewBox.cy}
                              className="fill-foreground text-3xl font-bold"
                            >
                              {leafTopics.length.toLocaleString()}
                            </tspan>
                            <tspan
                              x={viewBox.cx}
                              y={(viewBox.cy || 0) + 24}
                              className="fill-muted-foreground"
                            >
                              Topics
                            </tspan>
                          </text>
                        );
                      }
                      return null;
                    }}
                    position="center"
                  />
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hierarchical Topic List - Right Side */}
        <div className="sm:col-span-3">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Topics are organized hierarchically. Parent nodes (with <Network className="h-3 w-3 inline" /> icon) group similar topics together. 
              Click on the chart to expand a specific topic.
            </p>
            <Accordion 
              type="multiple" 
              value={expandedAccordions}
              onValueChange={handleAccordionChange}
              className="[&>*]:border-0"
            >
              {renderNode(rootNodeId, 0, true)}
            </Accordion>
          </div>
        </div>
      </div>
    </div>
  );
};
