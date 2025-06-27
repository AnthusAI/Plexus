import { jest } from '@jest/globals';

export const graphqlRequest = jest.fn() as jest.Mock;

const mockGraphqlClient = {
  graphql: jest.fn() as jest.Mock
};

export const getClient = jest.fn(() => mockGraphqlClient);

export const amplifyClient = {
  Account: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  ScoreResult: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  FeedbackItem: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  }
};

export const handleGraphQLErrors = jest.fn(); 