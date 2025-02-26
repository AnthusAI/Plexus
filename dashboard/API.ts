/* tslint:disable */
/* eslint-disable */
//  This file was automatically generated and should not be edited.

export type Account = {
  __typename: "Account",
  createdAt: string,
  description?: string | null,
  id: string,
  key: string,
  name: string,
  scorecards?: ModelScorecardConnection | null,
  updatedAt: string,
};

export type ModelScorecardConnection = {
  __typename: "ModelScorecardConnection",
  items:  Array<Scorecard | null >,
  nextToken?: string | null,
};

export type Scorecard = {
  __typename: "Scorecard",
  account?: Account | null,
  accountId: string,
  createdAt: string,
  description?: string | null,
  externalId: string,
  id: string,
  key: string,
  name: string,
  sections?: ModelScorecardSectionConnection | null,
  updatedAt: string,
};

export type ModelScorecardSectionConnection = {
  __typename: "ModelScorecardSectionConnection",
  items:  Array<ScorecardSection | null >,
  nextToken?: string | null,
};

export type ScorecardSection = {
  __typename: "ScorecardSection",
  createdAt: string,
  id: string,
  name: string,
  order: number,
  scorecard?: Scorecard | null,
  scorecardId: string,
  scores?: ModelScoreConnection | null,
  updatedAt: string,
};

export type ModelScoreConnection = {
  __typename: "ModelScoreConnection",
  items:  Array<Score | null >,
  nextToken?: string | null,
};

export type Score = {
  __typename: "Score",
  accuracy?: number | null,
  aiModel?: string | null,
  aiProvider?: string | null,
  configuration?: string | null,
  createdAt: string,
  distribution?: string | null,
  id: string,
  isFineTuned?: boolean | null,
  name: string,
  order: number,
  section?: ScorecardSection | null,
  sectionId: string,
  type: string,
  updatedAt: string,
  version?: string | null,
  versionHistory?: string | null,
};

export type ModelAccountFilterInput = {
  and?: Array< ModelAccountFilterInput | null > | null,
  createdAt?: ModelStringInput | null,
  description?: ModelStringInput | null,
  id?: ModelIDInput | null,
  key?: ModelStringInput | null,
  name?: ModelStringInput | null,
  not?: ModelAccountFilterInput | null,
  or?: Array< ModelAccountFilterInput | null > | null,
  updatedAt?: ModelStringInput | null,
};

export type ModelStringInput = {
  attributeExists?: boolean | null,
  attributeType?: ModelAttributeTypes | null,
  beginsWith?: string | null,
  between?: Array< string | null > | null,
  contains?: string | null,
  eq?: string | null,
  ge?: string | null,
  gt?: string | null,
  le?: string | null,
  lt?: string | null,
  ne?: string | null,
  notContains?: string | null,
  size?: ModelSizeInput | null,
};

export enum ModelAttributeTypes {
  _null = "_null",
  binary = "binary",
  binarySet = "binarySet",
  bool = "bool",
  list = "list",
  map = "map",
  number = "number",
  numberSet = "numberSet",
  string = "string",
  stringSet = "stringSet",
}


export type ModelSizeInput = {
  between?: Array< number | null > | null,
  eq?: number | null,
  ge?: number | null,
  gt?: number | null,
  le?: number | null,
  lt?: number | null,
  ne?: number | null,
};

export type ModelIDInput = {
  attributeExists?: boolean | null,
  attributeType?: ModelAttributeTypes | null,
  beginsWith?: string | null,
  between?: Array< string | null > | null,
  contains?: string | null,
  eq?: string | null,
  ge?: string | null,
  gt?: string | null,
  le?: string | null,
  lt?: string | null,
  ne?: string | null,
  notContains?: string | null,
  size?: ModelSizeInput | null,
};

export enum ModelSortDirection {
  ASC = "ASC",
  DESC = "DESC",
}


export type ModelAccountConnection = {
  __typename: "ModelAccountConnection",
  items:  Array<Account | null >,
  nextToken?: string | null,
};

export type ModelScoreFilterInput = {
  accuracy?: ModelFloatInput | null,
  aiModel?: ModelStringInput | null,
  aiProvider?: ModelStringInput | null,
  and?: Array< ModelScoreFilterInput | null > | null,
  configuration?: ModelStringInput | null,
  createdAt?: ModelStringInput | null,
  distribution?: ModelStringInput | null,
  id?: ModelIDInput | null,
  isFineTuned?: ModelBooleanInput | null,
  name?: ModelStringInput | null,
  not?: ModelScoreFilterInput | null,
  or?: Array< ModelScoreFilterInput | null > | null,
  order?: ModelIntInput | null,
  sectionId?: ModelStringInput | null,
  type?: ModelStringInput | null,
  updatedAt?: ModelStringInput | null,
  version?: ModelStringInput | null,
  versionHistory?: ModelStringInput | null,
};

export type ModelFloatInput = {
  attributeExists?: boolean | null,
  attributeType?: ModelAttributeTypes | null,
  between?: Array< number | null > | null,
  eq?: number | null,
  ge?: number | null,
  gt?: number | null,
  le?: number | null,
  lt?: number | null,
  ne?: number | null,
};

export type ModelBooleanInput = {
  attributeExists?: boolean | null,
  attributeType?: ModelAttributeTypes | null,
  eq?: boolean | null,
  ne?: boolean | null,
};

export type ModelIntInput = {
  attributeExists?: boolean | null,
  attributeType?: ModelAttributeTypes | null,
  between?: Array< number | null > | null,
  eq?: number | null,
  ge?: number | null,
  gt?: number | null,
  le?: number | null,
  lt?: number | null,
  ne?: number | null,
};

export type ModelScorecardFilterInput = {
  accountId?: ModelStringInput | null,
  and?: Array< ModelScorecardFilterInput | null > | null,
  createdAt?: ModelStringInput | null,
  description?: ModelStringInput | null,
  externalId?: ModelStringInput | null,
  id?: ModelIDInput | null,
  key?: ModelStringInput | null,
  name?: ModelStringInput | null,
  not?: ModelScorecardFilterInput | null,
  or?: Array< ModelScorecardFilterInput | null > | null,
  updatedAt?: ModelStringInput | null,
};

export type ModelScorecardSectionFilterInput = {
  and?: Array< ModelScorecardSectionFilterInput | null > | null,
  createdAt?: ModelStringInput | null,
  id?: ModelIDInput | null,
  name?: ModelStringInput | null,
  not?: ModelScorecardSectionFilterInput | null,
  or?: Array< ModelScorecardSectionFilterInput | null > | null,
  order?: ModelIntInput | null,
  scorecardId?: ModelStringInput | null,
  updatedAt?: ModelStringInput | null,
};

export type ModelAccountConditionInput = {
  and?: Array< ModelAccountConditionInput | null > | null,
  createdAt?: ModelStringInput | null,
  description?: ModelStringInput | null,
  key?: ModelStringInput | null,
  name?: ModelStringInput | null,
  not?: ModelAccountConditionInput | null,
  or?: Array< ModelAccountConditionInput | null > | null,
  updatedAt?: ModelStringInput | null,
};

export type CreateAccountInput = {
  description?: string | null,
  id?: string | null,
  key: string,
  name: string,
};

export type ModelScoreConditionInput = {
  accuracy?: ModelFloatInput | null,
  aiModel?: ModelStringInput | null,
  aiProvider?: ModelStringInput | null,
  and?: Array< ModelScoreConditionInput | null > | null,
  configuration?: ModelStringInput | null,
  createdAt?: ModelStringInput | null,
  distribution?: ModelStringInput | null,
  isFineTuned?: ModelBooleanInput | null,
  name?: ModelStringInput | null,
  not?: ModelScoreConditionInput | null,
  or?: Array< ModelScoreConditionInput | null > | null,
  order?: ModelIntInput | null,
  sectionId?: ModelStringInput | null,
  type?: ModelStringInput | null,
  updatedAt?: ModelStringInput | null,
  version?: ModelStringInput | null,
  versionHistory?: ModelStringInput | null,
};

export type CreateScoreInput = {
  accuracy?: number | null,
  aiModel?: string | null,
  aiProvider?: string | null,
  configuration?: string | null,
  distribution?: string | null,
  id?: string | null,
  isFineTuned?: boolean | null,
  name: string,
  order: number,
  sectionId: string,
  type: string,
  version?: string | null,
  versionHistory?: string | null,
};

export type ModelScorecardConditionInput = {
  accountId?: ModelStringInput | null,
  and?: Array< ModelScorecardConditionInput | null > | null,
  createdAt?: ModelStringInput | null,
  description?: ModelStringInput | null,
  externalId?: ModelStringInput | null,
  key?: ModelStringInput | null,
  name?: ModelStringInput | null,
  not?: ModelScorecardConditionInput | null,
  or?: Array< ModelScorecardConditionInput | null > | null,
  updatedAt?: ModelStringInput | null,
};

export type CreateScorecardInput = {
  accountId: string,
  description?: string | null,
  externalId: string,
  id?: string | null,
  key: string,
  name: string,
};

export type ModelScorecardSectionConditionInput = {
  and?: Array< ModelScorecardSectionConditionInput | null > | null,
  createdAt?: ModelStringInput | null,
  name?: ModelStringInput | null,
  not?: ModelScorecardSectionConditionInput | null,
  or?: Array< ModelScorecardSectionConditionInput | null > | null,
  order?: ModelIntInput | null,
  scorecardId?: ModelStringInput | null,
  updatedAt?: ModelStringInput | null,
};

export type CreateScorecardSectionInput = {
  id?: string | null,
  name: string,
  order: number,
  scorecardId: string,
};

export type DeleteAccountInput = {
  id: string,
};

export type DeleteScoreInput = {
  id: string,
};

export type DeleteScorecardInput = {
  id: string,
};

export type DeleteScorecardSectionInput = {
  id: string,
};

export type UpdateAccountInput = {
  description?: string | null,
  id: string,
  key?: string | null,
  name?: string | null,
};

export type UpdateScoreInput = {
  accuracy?: number | null,
  aiModel?: string | null,
  aiProvider?: string | null,
  configuration?: string | null,
  distribution?: string | null,
  id: string,
  isFineTuned?: boolean | null,
  name?: string | null,
  order?: number | null,
  sectionId?: string | null,
  type?: string | null,
  version?: string | null,
  versionHistory?: string | null,
};

export type UpdateScorecardInput = {
  accountId?: string | null,
  description?: string | null,
  externalId?: string | null,
  id: string,
  key?: string | null,
  name?: string | null,
};

export type UpdateScorecardSectionInput = {
  id: string,
  name?: string | null,
  order?: number | null,
  scorecardId?: string | null,
};

export type ModelSubscriptionAccountFilterInput = {
  and?: Array< ModelSubscriptionAccountFilterInput | null > | null,
  createdAt?: ModelSubscriptionStringInput | null,
  description?: ModelSubscriptionStringInput | null,
  id?: ModelSubscriptionIDInput | null,
  key?: ModelSubscriptionStringInput | null,
  name?: ModelSubscriptionStringInput | null,
  or?: Array< ModelSubscriptionAccountFilterInput | null > | null,
  updatedAt?: ModelSubscriptionStringInput | null,
};

export type ModelSubscriptionStringInput = {
  beginsWith?: string | null,
  between?: Array< string | null > | null,
  contains?: string | null,
  eq?: string | null,
  ge?: string | null,
  gt?: string | null,
  in?: Array< string | null > | null,
  le?: string | null,
  lt?: string | null,
  ne?: string | null,
  notContains?: string | null,
  notIn?: Array< string | null > | null,
};

export type ModelSubscriptionIDInput = {
  beginsWith?: string | null,
  between?: Array< string | null > | null,
  contains?: string | null,
  eq?: string | null,
  ge?: string | null,
  gt?: string | null,
  in?: Array< string | null > | null,
  le?: string | null,
  lt?: string | null,
  ne?: string | null,
  notContains?: string | null,
  notIn?: Array< string | null > | null,
};

export type ModelSubscriptionScoreFilterInput = {
  accuracy?: ModelSubscriptionFloatInput | null,
  aiModel?: ModelSubscriptionStringInput | null,
  aiProvider?: ModelSubscriptionStringInput | null,
  and?: Array< ModelSubscriptionScoreFilterInput | null > | null,
  configuration?: ModelSubscriptionStringInput | null,
  createdAt?: ModelSubscriptionStringInput | null,
  distribution?: ModelSubscriptionStringInput | null,
  id?: ModelSubscriptionIDInput | null,
  isFineTuned?: ModelSubscriptionBooleanInput | null,
  name?: ModelSubscriptionStringInput | null,
  or?: Array< ModelSubscriptionScoreFilterInput | null > | null,
  order?: ModelSubscriptionIntInput | null,
  sectionId?: ModelSubscriptionStringInput | null,
  type?: ModelSubscriptionStringInput | null,
  updatedAt?: ModelSubscriptionStringInput | null,
  version?: ModelSubscriptionStringInput | null,
  versionHistory?: ModelSubscriptionStringInput | null,
};

export type ModelSubscriptionFloatInput = {
  between?: Array< number | null > | null,
  eq?: number | null,
  ge?: number | null,
  gt?: number | null,
  in?: Array< number | null > | null,
  le?: number | null,
  lt?: number | null,
  ne?: number | null,
  notIn?: Array< number | null > | null,
};

export type ModelSubscriptionBooleanInput = {
  eq?: boolean | null,
  ne?: boolean | null,
};

export type ModelSubscriptionIntInput = {
  between?: Array< number | null > | null,
  eq?: number | null,
  ge?: number | null,
  gt?: number | null,
  in?: Array< number | null > | null,
  le?: number | null,
  lt?: number | null,
  ne?: number | null,
  notIn?: Array< number | null > | null,
};

export type ModelSubscriptionScorecardFilterInput = {
  accountId?: ModelSubscriptionStringInput | null,
  and?: Array< ModelSubscriptionScorecardFilterInput | null > | null,
  createdAt?: ModelSubscriptionStringInput | null,
  description?: ModelSubscriptionStringInput | null,
  externalId?: ModelSubscriptionStringInput | null,
  id?: ModelSubscriptionIDInput | null,
  key?: ModelSubscriptionStringInput | null,
  name?: ModelSubscriptionStringInput | null,
  or?: Array< ModelSubscriptionScorecardFilterInput | null > | null,
  updatedAt?: ModelSubscriptionStringInput | null,
};

export type ModelSubscriptionScorecardSectionFilterInput = {
  and?: Array< ModelSubscriptionScorecardSectionFilterInput | null > | null,
  createdAt?: ModelSubscriptionStringInput | null,
  id?: ModelSubscriptionIDInput | null,
  name?: ModelSubscriptionStringInput | null,
  or?: Array< ModelSubscriptionScorecardSectionFilterInput | null > | null,
  order?: ModelSubscriptionIntInput | null,
  scorecardId?: ModelSubscriptionStringInput | null,
  updatedAt?: ModelSubscriptionStringInput | null,
};

export type GetAccountQueryVariables = {
  id: string,
};

export type GetAccountQuery = {
  getAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type GetScoreQueryVariables = {
  id: string,
};

export type GetScoreQuery = {
  getScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type GetScorecardQueryVariables = {
  id: string,
};

export type GetScorecardQuery = {
  getScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type GetScorecardSectionQueryVariables = {
  id: string,
};

export type GetScorecardSectionQuery = {
  getScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type ListAccountByKeyQueryVariables = {
  filter?: ModelAccountFilterInput | null,
  key: string,
  limit?: number | null,
  nextToken?: string | null,
  sortDirection?: ModelSortDirection | null,
};

export type ListAccountByKeyQuery = {
  listAccountByKey?:  {
    __typename: "ModelAccountConnection",
    items:  Array< {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListAccountsQueryVariables = {
  filter?: ModelAccountFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
};

export type ListAccountsQuery = {
  listAccounts?:  {
    __typename: "ModelAccountConnection",
    items:  Array< {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScoreBySectionIdQueryVariables = {
  filter?: ModelScoreFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
  sectionId: string,
  sortDirection?: ModelSortDirection | null,
};

export type ListScoreBySectionIdQuery = {
  listScoreBySectionId?:  {
    __typename: "ModelScoreConnection",
    items:  Array< {
      __typename: "Score",
      accuracy?: number | null,
      aiModel?: string | null,
      aiProvider?: string | null,
      configuration?: string | null,
      createdAt: string,
      distribution?: string | null,
      id: string,
      isFineTuned?: boolean | null,
      name: string,
      order: number,
      sectionId: string,
      type: string,
      updatedAt: string,
      version?: string | null,
      versionHistory?: string | null,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScorecardByAccountIdQueryVariables = {
  accountId: string,
  filter?: ModelScorecardFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
  sortDirection?: ModelSortDirection | null,
};

export type ListScorecardByAccountIdQuery = {
  listScorecardByAccountId?:  {
    __typename: "ModelScorecardConnection",
    items:  Array< {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScorecardByExternalIdQueryVariables = {
  externalId: string,
  filter?: ModelScorecardFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
  sortDirection?: ModelSortDirection | null,
};

export type ListScorecardByExternalIdQuery = {
  listScorecardByExternalId?:  {
    __typename: "ModelScorecardConnection",
    items:  Array< {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScorecardByKeyQueryVariables = {
  filter?: ModelScorecardFilterInput | null,
  key: string,
  limit?: number | null,
  nextToken?: string | null,
  sortDirection?: ModelSortDirection | null,
};

export type ListScorecardByKeyQuery = {
  listScorecardByKey?:  {
    __typename: "ModelScorecardConnection",
    items:  Array< {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScorecardSectionByScorecardIdQueryVariables = {
  filter?: ModelScorecardSectionFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
  scorecardId: string,
  sortDirection?: ModelSortDirection | null,
};

export type ListScorecardSectionByScorecardIdQuery = {
  listScorecardSectionByScorecardId?:  {
    __typename: "ModelScorecardSectionConnection",
    items:  Array< {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScorecardSectionsQueryVariables = {
  filter?: ModelScorecardSectionFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
};

export type ListScorecardSectionsQuery = {
  listScorecardSections?:  {
    __typename: "ModelScorecardSectionConnection",
    items:  Array< {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScorecardsQueryVariables = {
  filter?: ModelScorecardFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
};

export type ListScorecardsQuery = {
  listScorecards?:  {
    __typename: "ModelScorecardConnection",
    items:  Array< {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type ListScoresQueryVariables = {
  filter?: ModelScoreFilterInput | null,
  limit?: number | null,
  nextToken?: string | null,
};

export type ListScoresQuery = {
  listScores?:  {
    __typename: "ModelScoreConnection",
    items:  Array< {
      __typename: "Score",
      accuracy?: number | null,
      aiModel?: string | null,
      aiProvider?: string | null,
      configuration?: string | null,
      createdAt: string,
      distribution?: string | null,
      id: string,
      isFineTuned?: boolean | null,
      name: string,
      order: number,
      sectionId: string,
      type: string,
      updatedAt: string,
      version?: string | null,
      versionHistory?: string | null,
    } | null >,
    nextToken?: string | null,
  } | null,
};

export type CreateAccountMutationVariables = {
  condition?: ModelAccountConditionInput | null,
  input: CreateAccountInput,
};

export type CreateAccountMutation = {
  createAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type CreateScoreMutationVariables = {
  condition?: ModelScoreConditionInput | null,
  input: CreateScoreInput,
};

export type CreateScoreMutation = {
  createScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type CreateScorecardMutationVariables = {
  condition?: ModelScorecardConditionInput | null,
  input: CreateScorecardInput,
};

export type CreateScorecardMutation = {
  createScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type CreateScorecardSectionMutationVariables = {
  condition?: ModelScorecardSectionConditionInput | null,
  input: CreateScorecardSectionInput,
};

export type CreateScorecardSectionMutation = {
  createScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type DeleteAccountMutationVariables = {
  condition?: ModelAccountConditionInput | null,
  input: DeleteAccountInput,
};

export type DeleteAccountMutation = {
  deleteAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type DeleteScoreMutationVariables = {
  condition?: ModelScoreConditionInput | null,
  input: DeleteScoreInput,
};

export type DeleteScoreMutation = {
  deleteScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type DeleteScorecardMutationVariables = {
  condition?: ModelScorecardConditionInput | null,
  input: DeleteScorecardInput,
};

export type DeleteScorecardMutation = {
  deleteScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type DeleteScorecardSectionMutationVariables = {
  condition?: ModelScorecardSectionConditionInput | null,
  input: DeleteScorecardSectionInput,
};

export type DeleteScorecardSectionMutation = {
  deleteScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type UpdateAccountMutationVariables = {
  condition?: ModelAccountConditionInput | null,
  input: UpdateAccountInput,
};

export type UpdateAccountMutation = {
  updateAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type UpdateScoreMutationVariables = {
  condition?: ModelScoreConditionInput | null,
  input: UpdateScoreInput,
};

export type UpdateScoreMutation = {
  updateScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type UpdateScorecardMutationVariables = {
  condition?: ModelScorecardConditionInput | null,
  input: UpdateScorecardInput,
};

export type UpdateScorecardMutation = {
  updateScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type UpdateScorecardSectionMutationVariables = {
  condition?: ModelScorecardSectionConditionInput | null,
  input: UpdateScorecardSectionInput,
};

export type UpdateScorecardSectionMutation = {
  updateScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnCreateAccountSubscriptionVariables = {
  filter?: ModelSubscriptionAccountFilterInput | null,
};

export type OnCreateAccountSubscription = {
  onCreateAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnCreateScoreSubscriptionVariables = {
  filter?: ModelSubscriptionScoreFilterInput | null,
};

export type OnCreateScoreSubscription = {
  onCreateScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type OnCreateScorecardSubscriptionVariables = {
  filter?: ModelSubscriptionScorecardFilterInput | null,
};

export type OnCreateScorecardSubscription = {
  onCreateScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnCreateScorecardSectionSubscriptionVariables = {
  filter?: ModelSubscriptionScorecardSectionFilterInput | null,
};

export type OnCreateScorecardSectionSubscription = {
  onCreateScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnDeleteAccountSubscriptionVariables = {
  filter?: ModelSubscriptionAccountFilterInput | null,
};

export type OnDeleteAccountSubscription = {
  onDeleteAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnDeleteScoreSubscriptionVariables = {
  filter?: ModelSubscriptionScoreFilterInput | null,
};

export type OnDeleteScoreSubscription = {
  onDeleteScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type OnDeleteScorecardSubscriptionVariables = {
  filter?: ModelSubscriptionScorecardFilterInput | null,
};

export type OnDeleteScorecardSubscription = {
  onDeleteScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnDeleteScorecardSectionSubscriptionVariables = {
  filter?: ModelSubscriptionScorecardSectionFilterInput | null,
};

export type OnDeleteScorecardSectionSubscription = {
  onDeleteScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnUpdateAccountSubscriptionVariables = {
  filter?: ModelSubscriptionAccountFilterInput | null,
};

export type OnUpdateAccountSubscription = {
  onUpdateAccount?:  {
    __typename: "Account",
    createdAt: string,
    description?: string | null,
    id: string,
    key: string,
    name: string,
    scorecards?:  {
      __typename: "ModelScorecardConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnUpdateScoreSubscriptionVariables = {
  filter?: ModelSubscriptionScoreFilterInput | null,
};

export type OnUpdateScoreSubscription = {
  onUpdateScore?:  {
    __typename: "Score",
    accuracy?: number | null,
    aiModel?: string | null,
    aiProvider?: string | null,
    configuration?: string | null,
    createdAt: string,
    distribution?: string | null,
    id: string,
    isFineTuned?: boolean | null,
    name: string,
    order: number,
    section?:  {
      __typename: "ScorecardSection",
      createdAt: string,
      id: string,
      name: string,
      order: number,
      scorecardId: string,
      updatedAt: string,
    } | null,
    sectionId: string,
    type: string,
    updatedAt: string,
    version?: string | null,
    versionHistory?: string | null,
  } | null,
};

export type OnUpdateScorecardSubscriptionVariables = {
  filter?: ModelSubscriptionScorecardFilterInput | null,
};

export type OnUpdateScorecardSubscription = {
  onUpdateScorecard?:  {
    __typename: "Scorecard",
    account?:  {
      __typename: "Account",
      createdAt: string,
      description?: string | null,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    accountId: string,
    createdAt: string,
    description?: string | null,
    externalId: string,
    id: string,
    key: string,
    name: string,
    sections?:  {
      __typename: "ModelScorecardSectionConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};

export type OnUpdateScorecardSectionSubscriptionVariables = {
  filter?: ModelSubscriptionScorecardSectionFilterInput | null,
};

export type OnUpdateScorecardSectionSubscription = {
  onUpdateScorecardSection?:  {
    __typename: "ScorecardSection",
    createdAt: string,
    id: string,
    name: string,
    order: number,
    scorecard?:  {
      __typename: "Scorecard",
      accountId: string,
      createdAt: string,
      description?: string | null,
      externalId: string,
      id: string,
      key: string,
      name: string,
      updatedAt: string,
    } | null,
    scorecardId: string,
    scores?:  {
      __typename: "ModelScoreConnection",
      nextToken?: string | null,
    } | null,
    updatedAt: string,
  } | null,
};
