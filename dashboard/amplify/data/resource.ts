import { type ClientSchema, a, defineData } from "@aws-amplify/backend";
import * as aws_dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

// Define types for authorization callback
type AuthorizationCallback = {
    publicApiKey: () => any;
    authenticated: () => any;
};

// Define model-specific index types
type AccountIndexFields = "name" | "key" | "description";
type ScorecardIndexFields = "name" | "key" | "description" | "accountId" | 
    "externalId" | "itemId";
type ScorecardSectionIndexFields = "name" | "scorecardId" | "order";
type ScoreIndexFields = "name" | "order" | "sectionId" | "type" | "accuracy" | 
    "version" | "aiProvider" | "aiModel" | "externalId" | "key";
type EvaluationIndexFields = "accountId" | "scorecardId" | "type" | "accuracy" | 
    "scoreId" | "status" | "updatedAt" | "createdAt" | "startedAt" | "elapsedSeconds" | 
    "estimatedRemainingSeconds" | "totalItems" | "processedItems" | "errorMessage" | 
    "scoreGoal" | "metricsExplanation" | "inferences" | "cost";
type BatchJobIndexFields = "accountId" | "scorecardId" | "type" | "scoreId" | 
    "status" | "modelProvider" | "modelName" | "batchId";
type ItemIndexFields = "name" | "description" | "accountId";
type ScoringJobIndexFields = "accountId" | "scorecardId" | "itemId" | "status" | 
    "scoreId";
type ScoreResultIndexFields = "accountId" | "scorecardId" | "itemId" | 
    "scoringJobId" | "evaluationId" | "scoreVersionId";
type BatchJobScoringJobIndexFields = "batchJobId" | "scoringJobId";
type TaskIndexFields = "accountId" | "type" | "status" | "target" | 
    "currentStageId" | "updatedAt" | "scorecardId" | "scoreId";
type TaskStageIndexFields = "taskId" | "name" | "order" | "status";
type DatasetIndexFields = "scorecardId" | "scoreId";
type DatasetVersionIndexFields = "datasetId";
type DatasetProfileIndexFields = "datasetId" | "datasetVersionId";
type ScoreVersionIndexFields = "scoreId" | "versionNumber" | "isFeatured";

const schema = a.schema({
    Account: a
        .model({
            name: a.string().required(),
            key: a.string().required(),
            description: a.string(),
            settings: a.json(),
            scorecards: a.hasMany('Scorecard', 'accountId'),
            evaluations: a.hasMany('Evaluation', 'accountId'),
            batchJobs: a.hasMany('BatchJob', 'accountId'),
            items: a.hasMany('Item', 'accountId'),
            scoringJobs: a.hasMany('ScoringJob', 'accountId'),
            scoreResults: a.hasMany('ScoreResult', 'accountId'),
            tasks: a.hasMany('Task', 'accountId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: AccountIndexFields) => any) => [
            idx("key")
        ]),

    Scorecard: a
        .model({
            name: a.string().required(),
            key: a.string().required(),
            description: a.string(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            sections: a.hasMany('ScorecardSection', 'scorecardId'),
            evaluations: a.hasMany('Evaluation', 'scorecardId'),
            batchJobs: a.hasMany('BatchJob', 'scorecardId'),
            scoringJobs: a.hasMany('ScoringJob', 'scorecardId'),
            scoreResults: a.hasMany('ScoreResult', 'scorecardId'),
            tasks: a.hasMany('Task', 'scorecardId'),
            datasets: a.hasMany('Dataset', 'scorecardId'),
            externalId: a.string(),
            itemId: a.string(),
            item: a.belongsTo('Item', 'itemId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScorecardIndexFields) => any) => [
            idx("accountId"),
            idx("key"),
            idx("externalId"),
            idx("name")
        ]),

    ScorecardSection: a
        .model({
            name: a.string().required(),
            order: a.integer().required(),
            scorecardId: a.string().required(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            scores: a.hasMany('Score', 'sectionId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScorecardSectionIndexFields) => any) => [
            idx("scorecardId")
        ]),

    Score: a
        .model({
            name: a.string().required(),
            key: a.string(),
            description: a.string(),
            order: a.integer().required(),
            type: a.string().required(),
            accuracy: a.float(),
            version: a.string(),
            aiProvider: a.string(),
            aiModel: a.string(),
            sectionId: a.string().required(),
            section: a.belongsTo('ScorecardSection', 'sectionId'),
            evaluations: a.hasMany('Evaluation', 'scoreId'),
            batchJobs: a.hasMany('BatchJob', 'scoreId'),
            scoringJobs: a.hasMany('ScoringJob', 'scoreId'),
            datasets: a.hasMany('Dataset', 'scoreId'),
            tasks: a.hasMany('Task', 'scoreId'),
            versions: a.hasMany('ScoreVersion', 'scoreId'),
            championVersionId: a.string(),
            championVersion: a.belongsTo('ScoreVersion', 'championVersionId'),
            externalId: a.string().required()
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScoreIndexFields) => any) => [
            idx("sectionId"),
            idx("externalId"),
            idx("key"),
            idx("name")
        ]),

    ScoreVersion: a
        .model({
            scoreId: a.string().required(),
            score: a.belongsTo('Score', 'scoreId'),
            configuration: a.json().required(),
            isFeatured: a.boolean().required(),
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
            scoreResults: a.hasMany('ScoreResult', 'scoreVersionId'),
            scoresAsChampion: a.hasMany('Score', 'championVersionId'),
            parentVersionId: a.string(),
            parentVersion: a.belongsTo('ScoreVersion', 'parentVersionId'),
            childVersions: a.hasMany('ScoreVersion', 'parentVersionId'),
            evaluations: a.hasMany('Evaluation', 'scoreVersionId')
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("scoreId").sortKeys(["createdAt"]),
            idx("updatedAt")
        ]),

    Evaluation: a
        .model({
            type: a.string().required(),
            parameters: a.json(),
            metrics: a.json(),
            metricsExplanation: a.string(),
            inferences: a.integer(),
            accuracy: a.float().required(),
            cost: a.float(),
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
            status: a.string().required(),
            startedAt: a.datetime(),
            elapsedSeconds: a.integer(),
            estimatedRemainingSeconds: a.integer(),
            totalItems: a.integer(),
            processedItems: a.integer(),
            errorMessage: a.string(),
            errorDetails: a.json(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scorecardId: a.string(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            scoreVersionId: a.string(),
            scoreVersion: a.belongsTo('ScoreVersion', 'scoreVersionId'),
            confusionMatrix: a.json(),
            items: a.hasMany('Item', 'evaluationId'),
            scoreResults: a.hasMany('ScoreResult', 'evaluationId'),
            scoringJobs: a.hasMany('ScoringJob', 'evaluationId'),
            scoreGoal: a.string(),
            datasetClassDistribution: a.json(),
            isDatasetClassDistributionBalanced: a.boolean(),
            predictedClassDistribution: a.json(),
            isPredictedClassDistributionBalanced: a.boolean(),
            taskId: a.string(),
            task: a.belongsTo('Task', 'taskId')
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("scorecardId").sortKeys(["updatedAt"]),
            idx("scoreId").sortKeys(["updatedAt"]),
            idx("scoreVersionId").sortKeys(["createdAt"])
        ]),

    BatchJob: a
        .model({
            type: a.string().required(),
            batchId: a.string().required(),
            status: a.string().required(),
            startedAt: a.datetime(),
            estimatedEndAt: a.datetime(),
            completedAt: a.datetime(),
            totalRequests: a.integer(),
            completedRequests: a.integer(),
            failedRequests: a.integer(),
            errorMessage: a.string(),
            errorDetails: a.json(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scorecardId: a.string(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            scoringJobs: a.hasMany('BatchJobScoringJob', 'batchJobId'),
            scoringJobCountCache: a.integer(),
            modelProvider: a.string().required(),
            modelName: a.string().required(),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId" as BatchJobIndexFields),
            idx("scorecardId" as BatchJobIndexFields),
            idx("scoreId" as BatchJobIndexFields),
            idx("batchId" as BatchJobIndexFields)
        ]),

    Item: a
        .model({
            name: a.string().required(),
            description: a.string(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scoringJobs: a.hasMany('ScoringJob', 'itemId'),
            scoreResults: a.hasMany('ScoreResult', 'itemId'),
            scorecards: a.hasMany('Scorecard', 'itemId'),
            evaluationId: a.string(),
            evaluation: a.belongsTo('Evaluation', 'evaluationId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId")
        ]),

    ScoringJob: a
        .model({
            status: a.string().required(),
            startedAt: a.datetime(),
            completedAt: a.datetime(),
            errorMessage: a.string(),
            errorDetails: a.json(),
            metadata: a.json(),
            itemId: a.string().required(),
            item: a.belongsTo('Item', 'itemId'),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scorecardId: a.string().required(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            evaluationId: a.string(),
            evaluation: a.belongsTo('Evaluation', 'evaluationId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            batchJobLinks: a.hasMany('BatchJobScoringJob', 'scoringJobId'),
            scoreResults: a.hasMany('ScoreResult', 'scoringJobId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId"),
            idx("itemId"),
            idx("scorecardId"),
            idx("scoreId"),
            idx("evaluationId")
        ]),

    ScoreResult: a
        .model({
            value: a.string().required(),
            explanation: a.string(),
            confidence: a.float(),
            metadata: a.json(),
            correct: a.boolean(),
            itemId: a.string().required(),
            item: a.belongsTo('Item', 'itemId'),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scoringJobId: a.string(),
            scoringJob: a.belongsTo('ScoringJob', 'scoringJobId'),
            evaluationId: a.string(),
            evaluation: a.belongsTo('Evaluation', 'evaluationId'),
            scorecardId: a.string().required(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            scoreVersionId: a.string(),
            scoreVersion: a.belongsTo('ScoreVersion', 'scoreVersionId')
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScoreResultIndexFields) => any) => [
            idx("accountId"),
            idx("itemId"),
            idx("scoringJobId"),
            idx("scorecardId"),
            idx("evaluationId"),
            idx("scoreVersionId")
        ]),

    BatchJobScoringJob: a
        .model({
            batchJobId: a.string().required(),
            scoringJobId: a.string().required(),
            batchJob: a.belongsTo('BatchJob', 'batchJobId'),
            scoringJob: a.belongsTo('ScoringJob', 'scoringJobId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("batchJobId")
        ]),

    Task: a
        .model({
            accountId: a.string().required(),
            type: a.string().required(),
            status: a.string().required(),
            target: a.string().required(),
            command: a.string().required(),
            description: a.string(),
            dispatchStatus: a.string(),
            metadata: a.json(),
            createdAt: a.datetime(),
            startedAt: a.datetime(),
            completedAt: a.datetime(),
            estimatedCompletionAt: a.datetime(),
            errorMessage: a.string(),
            errorDetails: a.json(),
            stdout: a.string(),
            stderr: a.string(),
            currentStageId: a.string(),
            scorecardId: a.string(),
            account: a.belongsTo('Account', 'accountId'),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            stages: a.hasMany('TaskStage', 'taskId'),
            currentStage: a.belongsTo('TaskStage', 'currentStageId'),
            celeryTaskId: a.string(),
            workerNodeId: a.string(),
            updatedAt: a.datetime(),
            evaluation: a.hasOne('Evaluation', 'taskId')
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("scorecardId").sortKeys(["updatedAt"]),
            idx("scoreId"),
            idx("updatedAt")
        ]),

    TaskStage: a
        .model({
            taskId: a.string().required(),
            task: a.belongsTo('Task', 'taskId'),
            name: a.string().required(),
            order: a.integer().required(),
            status: a.string().required(),
            statusMessage: a.string(),
            startedAt: a.datetime(),
            completedAt: a.datetime(),
            estimatedCompletionAt: a.datetime(),
            processedItems: a.integer(),
            totalItems: a.integer(),
            tasksAsCurrentStage: a.hasMany('Task', 'currentStageId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: TaskStageIndexFields) => any) => [
            idx("taskId"),
            idx("name"),
            idx("order"),
            idx("status")
        ]),

    Dataset: a
        .model({
            name: a.string().required(),
            description: a.string(),
            scorecardId: a.string().required(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            currentVersionId: a.string(),
            currentVersion: a.belongsTo('DatasetVersion', 'currentVersionId'),
            versions: a.hasMany('DatasetVersion', 'datasetId'),
            profiles: a.hasMany('DatasetProfile', 'datasetId'),
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: DatasetIndexFields) => any) => [
            idx("scorecardId"),
            idx("scoreId")
        ]),

    DatasetVersion: a
        .model({
            datasetId: a.string().required(),
            dataset: a.belongsTo('Dataset', 'datasetId'),
            versionNumber: a.integer().required(),
            configuration: a.json().required(),
            createdAt: a.datetime().required(),
            profiles: a.hasMany('DatasetProfile', 'datasetVersionId'),
            datasetsAsCurrentVersion: a.hasMany('Dataset', 'currentVersionId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: DatasetVersionIndexFields) => any) => [
            idx("datasetId")
        ]),

    DatasetProfile: a
        .model({
            datasetId: a.string().required(),
            dataset: a.belongsTo('Dataset', 'datasetId'),
            datasetVersionId: a.string().required(),
            datasetVersion: a.belongsTo('DatasetVersion', 'datasetVersionId'),
            columnList: a.string().array().required(),
            recordCounts: a.json().required(),
            answerDistribution: a.json().required(),
            createdAt: a.datetime().required(),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: DatasetProfileIndexFields) => any) => [
            idx("datasetId"),
            idx("datasetVersionId")
        ])
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
    schema,
    authorizationModes: {
        defaultAuthorizationMode: 'userPool',
        apiKeyAuthorizationMode: {
            expiresInDays: 0  // Never expires
        }
    }
});