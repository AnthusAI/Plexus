import React, { useEffect, useState } from 'react';
import { API, graphqlOperation } from 'aws-amplify';
import { onUpdateScoringJob } from '../graphql/subscriptions';
import { listBatchJobScoringJobs, getScoringJob } from '../graphql/queries';

const BatchJobDetails = () => {
  const [batchJob, setBatchJob] = useState(null);
  const [scoringJobs, setScoringJobs] = useState([]);

  // Subscribe to scoring job updates without using relationships
  const subscribeToScoringJobUpdates = async (batchJobId: string) => {
    const subscription = API.graphql(
      graphqlOperation(onUpdateScoringJob)
    ).subscribe({
      next: async () => {
        // Don't use the payload - instead query for all associated jobs
        await refreshScoringJobs(batchJobId);
      },
      error: (error) => console.error('Subscription error:', error)
    });

    return subscription;
  };

  // Query for all scoring jobs associated with this batch
  const refreshScoringJobs = async (batchJobId: string) => {
    try {
      // First get all associations
      const linkResult = await API.graphql(
        graphqlOperation(listBatchJobScoringJobs, {
          filter: { batchJobId: { eq: batchJobId } }
        })
      );
      const links = linkResult.data.listBatchJobScoringJobs.items;
      
      // Then get all the scoring jobs
      const scoringJobIds = links.map(link => link.scoringJobId);
      const scoringJobs = await Promise.all(
        scoringJobIds.map(async (id) => {
          const result = await API.graphql(
            graphqlOperation(getScoringJob, { id })
          );
          return result.data.getScoringJob;
        })
      );

      setScoringJobs(scoringJobs);
    } catch (error) {
      console.error('Error refreshing scoring jobs:', error);
    }
  };

  useEffect(() => {
    if (batchJob?.id) {
      const subscription = subscribeToScoringJobUpdates(batchJob.id);
      return () => subscription.unsubscribe();
    }
  }, [batchJob?.id]);

  return (
    <div>
      {/* Render your component */}
    </div>
  );
};

export default BatchJobDetails; 