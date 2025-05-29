import { type ClientSchema, a, defineData, defineFunction } from "@aws-amplify/backend";
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
    "externalId";
type ScorecardSectionIndexFields = "name" | "scorecardId" | "order";
type ScoreIndexFields = "name" | "order" | "sectionId" | "type" | "accuracy" | 
    "version" | "aiProvider" | "aiModel" | "externalId" | "key";
type EvaluationIndexFields = "accountId" | "scorecardId" | "type" | "accuracy" | 
    "scoreId" | "status" | "updatedAt" | "createdAt" | "startedAt" | "elapsedSeconds" | 
    "estimatedRemainingSeconds" | "totalItems" | "processedItems" | "errorMessage" | 
    "scoreGoal" | "metricsExplanation" | "inferences" | "cost";
type BatchJobIndexFields = "accountId" | "scorecardId" | "type" | "scoreId" | 
    "status" | "modelProvider" | "modelName" | "batchId";
type ItemIndexFields = "name" | "description" | "accountId" | "evaluationId" | "updatedAt" | "createdAt" | "isEvaluation";
type ScoringJobIndexFields = "accountId" | "scorecardId" | "itemId" | "status" | 
    "scoreId" | "evaluationId" | "startedAt" | "completedAt" | "errorMessage" | "updatedAt" | "createdAt";
type ScoreResultIndexFields = "accountId" | "scorecardId" | "itemId" | 
    "scoringJobId" | "evaluationId" | "scoreVersionId" | "updatedAt" | "createdAt" | "scoreId";
type BatchJobScoringJobIndexFields = "batchJobId" | "scoringJobId";
type TaskIndexFields = "accountId" | "type" | "status" | "target" | 
    "currentStageId" | "updatedAt" | "scorecardId" | "scoreId";
type TaskStageIndexFields = "taskId" | "name" | "order" | "status";
type DatasetIndexFields = "scorecardId" | "scoreId";
type DatasetVersionIndexFields = "datasetId";
type DatasetProfileIndexFields = "datasetId" | "datasetVersionId";
type ShareLinkIndexFields = "token" | "resourceType" | "resourceId" | "accountId";
type ScoreVersionIndexFields = "scoreId" | "versionNumber" | "isFeatured";
type ReportConfigurationIndexFields = "accountId" | "name";
type ReportIndexFields = "accountId" | "reportConfigurationId" | "createdAt" | "updatedAt" | "taskId";
type ReportBlockIndexFields = "reportId" | "name" | "position";
type FeedbackItemIndexFields = "accountId" | "scorecardId" | "scoreId" | "cacheKey" | "updatedAt" | "itemId"; // UPDATED: Renamed externalId to cacheKey and added itemId
type ScorecardExampleItemIndexFields = "scorecardId" | "itemId" | "addedAt";
type ScorecardProcessedItemIndexFields = "scorecardId" | "itemId" | "processedAt";
type IdentifierIndexFields = "accountId" | "value" | "name" | "itemId";

// New index types for Feedback Analysis
// type FeedbackAnalysisIndexFields = "accountId" | "scorecardId" | "createdAt"; // REMOVED

// Define the share token handler function
const getResourceByShareTokenHandler = defineFunction({
    entry: './resolvers/getResourceByShareToken.ts'
});

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
            reportConfigurations: a.hasMany('ReportConfiguration', 'accountId'),
            reports: a.hasMany('Report', 'accountId'),
            feedbackItems: a.hasMany('FeedbackItem', 'accountId'),
            identifiers: a.hasMany('Identifier', 'accountId'),
        })
        .authorization((allow) => [
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
            feedbackItems: a.hasMany('FeedbackItem', 'scorecardId'),
            externalId: a.string(),
            exampleItems: a.hasMany('ScorecardExampleItem', 'scorecardId'),
            processedItems: a.hasMany('ScorecardProcessedItem', 'scorecardId'),
        })
        .authorization((allow) => [
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
        .authorization((allow) => [
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
            targetAgreement: a.float(),
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
            items: a.hasMany('Item', 'scoreId'),
            scoreResults: a.hasMany('ScoreResult', 'scoreId'),
            feedbackItems: a.hasMany('FeedbackItem', 'scoreId'),
            championVersionId: a.string(),
            championVersion: a.belongsTo('ScoreVersion', 'championVersionId'),
            externalId: a.string().required()
        })
        .authorization((allow) => [
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
            configuration: a.string().required(),
            isFeatured: a.boolean().required(),
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
            note: a.string(),
            scoreResults: a.hasMany('ScoreResult', 'scoreVersionId'),
            scoresAsChampion: a.hasMany('Score', 'championVersionId'),
            parentVersionId: a.string(),
            parentVersion: a.belongsTo('ScoreVersion', 'parentVersionId'),
            childVersions: a.hasMany('ScoreVersion', 'parentVersionId'),
            evaluations: a.hasMany('Evaluation', 'scoreVersionId')
        })
        .authorization((allow) => [
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
            task: a.belongsTo('Task', 'taskId'),
            universalCode: a.string()
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
            // Public access removed - use API key authentication for unauthenticated access
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
        .authorization((allow) => [
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
            externalId: a.string(),
            description: a.string(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scoringJobs: a.hasMany('ScoringJob', 'itemId'),
            scoreResults: a.hasMany('ScoreResult', 'itemId'),
            evaluationId: a.string(),
            evaluation: a.belongsTo('Evaluation', 'evaluationId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            updatedAt: a.datetime(),
            createdAt: a.datetime(),
            isEvaluation: a.boolean().required(),
            identifiers: a.json(),
            feedbackItems: a.hasMany('FeedbackItem', 'itemId'),
            attachedFiles: a.string().array(),
            text: a.string(),
            metadata: a.json(),
            asExampleFor: a.hasMany('ScorecardExampleItem', 'itemId'),
            processedFor: a.hasMany('ScorecardProcessedItem', 'itemId'),
            itemIdentifiers: a.hasMany('Identifier', 'itemId'),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("accountId").sortKeys(["createdAt"]),
            idx("externalId"),
            idx("scoreId").sortKeys(["updatedAt"]),
            idx("scoreId").sortKeys(["createdAt"]),
            // Composite GSI for accountId+externalId to enforce uniqueness within an account
            idx("accountId").sortKeys(["externalId"]).name("byAccountAndExternalId"),
        ]),

    Identifier: a
        .model({
            itemId: a.string().required(),
            name: a.string().required(),      // e.g., "Customer ID", "Order ID"
            value: a.string().required(),     // e.g., "CUST-123456", "ORD-789012"
            url: a.string(),                  // Optional clickable link
            accountId: a.string().required(), // For data isolation
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
            
            // Relationships
            item: a.belongsTo('Item', 'itemId'),
            account: a.belongsTo('Account', 'accountId'),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: IdentifierIndexFields) => any) => [
            idx("accountId").sortKeys(["value"]).name("byAccountAndValue"),  // PRIMARY: Direct-hit search by exact value
            idx("accountId").sortKeys(["name", "value"]).name("byAccountNameAndValue"), // Search within identifier type
            idx("itemId"),  // Get all identifiers for an item
            idx("value").name("byValue"), // Global value lookup (if cross-account search needed)
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
            updatedAt: a.datetime(),
            createdAt: a.datetime(),
        })
        .authorization((allow) => [
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
            trace: a.json(),
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
            scoreVersion: a.belongsTo('ScoreVersion', 'scoreVersionId'),
            scoreId: a.string(),
            score: a.belongsTo('Score', 'scoreId'),
            updatedAt: a.datetime(),
            createdAt: a.datetime(),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScoreResultIndexFields) => any) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("itemId"),
            idx("scoringJobId"),
            idx("scorecardId").sortKeys(["updatedAt"]),
            idx("evaluationId"),
            idx("scoreVersionId"),
            idx("scoreId"),
            // Composite GSI for efficient cache lookups by scorecard + score + item
            idx("scorecardId").sortKeys(["scoreId", "itemId"]).name("byScorecardScoreItem")
        ]),

    BatchJobScoringJob: a
        .model({
            batchJobId: a.string().required(),
            scoringJobId: a.string().required(),
            batchJob: a.belongsTo('BatchJob', 'batchJobId'),
            scoringJob: a.belongsTo('ScoringJob', 'scoringJobId'),
        })
        .authorization((allow) => [
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
            evaluation: a.hasOne('Evaluation', 'taskId'),
            report: a.hasOne('Report', 'taskId')
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
            // Public access removed - use API key authentication for unauthenticated access
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
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
            // Public access removed - use API key authentication for unauthenticated access
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
        .authorization((allow) => [
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
        .authorization((allow) => [
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
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: DatasetProfileIndexFields) => any) => [
            idx("datasetId"),
            idx("datasetVersionId")
        ]),
        
    ShareLink: a
        .model({
            token: a.string().required(),
            resourceType: a.string().required(),
            resourceId: a.string().required(),
            createdBy: a.string().required(),
            accountId: a.string().required(),
            expiresAt: a.datetime(),
            viewOptions: a.json(),
            lastAccessedAt: a.datetime(),
            accessCount: a.integer(),
            isRevoked: a.boolean()
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ShareLinkIndexFields) => any) => [
            idx("token"),
            idx("accountId"),
            idx("resourceType"),
            idx("resourceId")
        ]),

    ResourceByShareTokenResponse: a.customType({
        shareLink: a.customType({
            token: a.string(),
            resourceType: a.string(),
            resourceId: a.string(),
            viewOptions: a.json()
        }),
        data: a.json()
    }),
    
    getResourceByShareToken: a
        .query()
        .arguments({ token: a.string().required() })
        .returns(a.ref('ResourceByShareTokenResponse'))
        .authorization(allow => [
            allow.guest(),
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .handler(a.handler.function(getResourceByShareTokenHandler)),

    ReportConfiguration: a
        .model({
            name: a.string().required(),
            description: a.string(),
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            configuration: a.string().required(),
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
            reports: a.hasMany('Report', 'reportConfigurationId'),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
            // Public access removed - use API key authentication for unauthenticated access
        ])
        .secondaryIndexes((idx: (field: ReportConfigurationIndexFields) => any) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("accountId").sortKeys(["name"])
        ]),

    Report: a
        .model({
            name: a.string(), // Can be auto-generated or user-defined
            createdAt: a.datetime().required(),
            parameters: a.json(), // Parameters used for this specific run
            output: a.string(), // Generated report output (original markdown template)
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            reportConfigurationId: a.string().required(),
            reportConfiguration: a.belongsTo('ReportConfiguration', 'reportConfigurationId'),
            reportBlocks: a.hasMany('ReportBlock', 'reportId'), // Link to ReportBlock
            updatedAt: a.datetime().required(),
            taskId: a.string(), // Add foreign key for Task
            task: a.belongsTo('Task', 'taskId'), // Add relationship to Task
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
            // Public access removed - use API key authentication for unauthenticated access
        ])
        .secondaryIndexes((idx: (field: ReportIndexFields) => any) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("reportConfigurationId").sortKeys(["createdAt"]),
            idx("taskId") // Add index by taskId
        ]),

    ReportBlock: a
        .model({
            reportId: a.string().required(),
            report: a.belongsTo('Report', 'reportId'),
            name: a.string(), // Optional name for the block
            position: a.integer().required(), // Required position for ordering
            type: a.string().required(), // Required type for the block
            output: a.json().required(), // JSON output from the block's execution
            log: a.string(), // Optional log output from the block
            warning: a.string(), // Optional warning message (styled as 'false' alert)
            error: a.string(), // Optional error message (styled as red 'danger' alert)
            attachedFiles: a.string().array(), // This is the corrected field name and type
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
            // Public access removed - use API key authentication for unauthenticated access
        ])
        .secondaryIndexes((idx: (field: ReportBlockIndexFields) => any) => [
            idx("reportId").sortKeys(["name"]).name("byReportAndName"),
            idx("reportId").sortKeys(["position"]).name("byReportAndPosition")
        ]),

    FeedbackItem: a
        .model({
            accountId: a.string().required(),
            account: a.belongsTo('Account', 'accountId'),
            scorecardId: a.string().required(),
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            cacheKey: a.string().required(),
            scoreId: a.string().required(),
            score: a.belongsTo('Score', 'scoreId'),
            itemId: a.string().required(),
            item: a.belongsTo('Item', 'itemId'),
            initialAnswerValue: a.string(),
            finalAnswerValue: a.string(),
            initialCommentValue: a.string(),
            finalCommentValue: a.string(),
            editCommentValue: a.string(),
            editedAt: a.datetime(),
            editorName: a.string(),
            isAgreement: a.boolean(),
            createdAt: a.datetime().required(),
            updatedAt: a.datetime().required(),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: FeedbackItemIndexFields) => any) => [
            idx("accountId").sortKeys(["updatedAt"]),
            idx("accountId").sortKeys(["editedAt"]),
            idx("accountId").sortKeys(["scorecardId", "scoreId", "updatedAt"]).name("byAccountScorecardScoreUpdatedAt"),
            idx("accountId").sortKeys(["scorecardId", "scoreId", "editedAt"]).name("byAccountScorecardScoreEditedAt"),
            idx("itemId")
        ]),

    ScorecardExampleItem: a
        .model({
            scorecardId: a.id().required(),
            itemId: a.id().required(),
            addedAt: a.datetime(),
            addedBy: a.string(),
            notes: a.string(),
            
            // Relationships to both ends
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            item: a.belongsTo('Item', 'itemId'),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScorecardExampleItemIndexFields) => any) => [
            idx("scorecardId"),
            idx("itemId"),
            idx("scorecardId").sortKeys(["addedAt"]),
        ]),

    ScorecardProcessedItem: a
        .model({
            scorecardId: a.id().required(),
            itemId: a.id().required(),
            processedAt: a.datetime(),
            lastScoreResultId: a.string(), // Reference to most recent result
            
            // Relationships to both ends
            scorecard: a.belongsTo('Scorecard', 'scorecardId'),
            item: a.belongsTo('Item', 'itemId'),
        })
        .authorization((allow) => [
            allow.publicApiKey(),
            allow.authenticated()
        ])
        .secondaryIndexes((idx: (field: ScorecardProcessedItemIndexFields) => any) => [
            idx("scorecardId"),
            idx("itemId"),
            idx("scorecardId").sortKeys(["processedAt"]),
        ]),
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