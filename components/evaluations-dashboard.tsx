// ... existing code ...
  const task: AmplifyTask | null = rawTask ? {
    id: rawTask.id,
    command: rawTask.command,
    type: rawTask.type,
    status: rawTask.status,
    target: rawTask.target,
    stages: { 
      data: { 
        items: (rawStages?.data || []).map(stage => ({
          id: stage.id,
          name: stage.name,
          order: stage.order,
          status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
          processedItems: stage.processedItems ?? undefined,
          totalItems: stage.totalItems ?? undefined,
          startedAt: stage.startedAt ?? undefined,
          completedAt: stage.completedAt ?? undefined,
          estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
          statusMessage: stage.statusMessage ?? undefined
        }))
      }
    }
  } : null;
// ... existing code ...