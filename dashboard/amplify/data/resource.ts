import { type ClientSchema, a, defineData } from "@aws-amplify/backend";

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
    "version" | "aiProvider" | "aiModel";
type EvaluationIndexFields = "accountId" | "scorecardId" | "type" | "accuracy" | 
    "scoreId" | "status" | "updatedAt";
type BatchJobIndexFields = "accountId" | "scorecardId" | "type" | "scoreId" | 
    "status" | "modelProvider" | "modelName" | "batchId";
type ItemIndexFields = "name" | "description" | "accountId" | "evaluationId";
type ScoringJobIndexFields = "accountId" | "scorecardId" | "itemId" | "status" | 
    "evaluationId" | "scoreId";
type ScoreResultIndexFields = "accountId" | "scorecardId" | "itemId" | 
    "evaluationId" | "scoringJobId";
type BatchJobScoringJobIndexFields = "batchJobId" | "scoringJobId";
type ActionIndexFields = "accountId" | "type" | "status" | "target" | 
    "currentStageId";
type ActionStageIndexFields = "actionId" | "name" | "order" | "status";

const schema = a.schema({
    Account: a
        .model({
            name: a.string().required(),
            key: a.string().required(),
            description: a.string(),
            scorecards: a.hasMany('Scorecard', 'accountId'),
            evaluations: a.hasMany('Evaluation', 'accountId'),
            batchJobs: a.hasMany('BatchJob', 'accountId'),
            items: a.hasMany('Item', 'accountId'),
            scoringJobs: a.hasMany('ScoringJob', 'accountId'),
            scoreResults: a.hasMany('ScoreResult', 'accountId'),
            actions: a.hasMany('Action', 'accountId'),
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
            externalId: a.string().required(),
            description: a.string(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            sections: a.hasMany('ScorecardSection', 'scorecardId'),
            evaluations: a.hasMany('Evaluation', 'scorecardId'),
            batchJobs: a.hasMany('BatchJob', 'scorecardId'),
            itemId: a.string(),
            item: a.belongsTo('Item', 'itemId'),
            scoringJobs: a.hasMany('ScoringJob', 'scorecardId'),
            scoreResults: a.hasMany('ScoreResult', 'scorecardId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScorecardIndexFields) => any) => [
            idx("accountId"),
            idx("key"),
            idx("externalId")
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
            externalId: a.string(),
            type: a.string().required(),
            order: a.integer().required(),
            accuracy: a.float(),
            version: a.string(),
            sectionId: a.string().required(),
            section: a.belongsTo('ScorecardSection', 'sectionId'),
            aiProvider: a.string(),
            aiModel: a.string(),
            isFineTuned: a.boolean(),
            configuration: a.json(),
            distribution: a.json(),
            versionHistory: a.json(),
            evaluations: a.hasMany('Evaluation', 'scoreId'),
            batchJobs: a.hasMany('BatchJob', 'scoreId'),
            scoringJobs: a.hasMany('ScoringJob', 'scoreId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScoreIndexFields) => any) => [
            idx("sectionId")
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
            confusionMatrix: a.json(),
            items: a.hasMany('Item', 'evaluationId'),
            scoreResults: a.hasMany('ScoreResult', 'evaluationId'),
            scoringJobs: a.hasMany('ScoringJob', 'evaluationId'),
            scoreGoal: a.string(),
            datasetClassDistribution: a.json(),
            isDatasetClassDistributionBalanced: a.boolean(),
            predictedClassDistribution: a.json(),
            isPredictedClassDistributionBalanced: a.boolean(),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId" as EvaluationIndexFields),
            idx("scorecardId" as EvaluationIndexFields),
            idx("scoreId" as EvaluationIndexFields),
            idx("updatedAt" as EvaluationIndexFields)
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
            idx("accountId" as ItemIndexFields)
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
            idx("accountId" as ScoringJobIndexFields),
            idx("itemId" as ScoringJobIndexFields),
            idx("scorecardId" as ScoringJobIndexFields),
            idx("evaluationId" as ScoringJobIndexFields),
            idx("scoreId" as ScoringJobIndexFields)
        ]),

    ScoreResult: a
        .model({
            value: a.string().required(),
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
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScoreResultIndexFields) => any) => [
            idx("accountId"),
            idx("itemId"),
            idx("scoringJobId"),
            idx("evaluationId"),
            idx("scorecardId")
        ]),

    Action: a
        .model({
            accountId: a.string().required(),
            type: a.string().required(),
            status: a.string().required(),
            target: a.string().required(),
            command: a.string().required(),
            metadata: a.json(),
            createdAt: a.datetime().required(),
            startedAt: a.datetime(),
            completedAt: a.datetime(),
            estimatedCompletionAt: a.datetime(),
            errorMessage: a.string(),
            errorDetails: a.json(),
            stdout: a.string(),
            stderr: a.string(),
            currentStageId: a.string(),
            currentStage: a.belongsTo('ActionStage', 'currentStageId'),
            stages: a.hasMany('ActionStage', 'actionId'),
            account: a.belongsTo('Account', 'accountId'),
            celeryTaskId: a.string(),
            workerNodeId: a.string(),
            dispatchStatus: a.string(),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ActionIndexFields) => any) => [
            idx("accountId"),
            idx("type"),
            idx("status"),
            idx("target"),
            idx("currentStageId")
        ]),

    ActionStage: a
        .model({
            actionId: a.string().required(),
            action: a.belongsTo('Action', 'actionId'),
            name: a.string().required(),
            order: a.integer().required(),
            status: a.string().required(),
            statusMessage: a.string(),
            startedAt: a.datetime(),
            completedAt: a.datetime(),
            estimatedCompletionAt: a.datetime(),
            processedItems: a.integer(),
            totalItems: a.integer(),
            actionsAsCurrentStage: a.hasMany('Action', 'currentStageId'),
        })
        .authorization((allow: AuthorizationCallback) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ActionStageIndexFields) => any) => [
            idx("actionId"),
            idx("name"),
            idx("order"),
            idx("status")
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
            idx("batchJobId" as BatchJobScoringJobIndexFields)
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
    },
});