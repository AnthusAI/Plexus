declare module 'aws-amplify' {
  export const API: {
    graphql: (operation: any) => Promise<any>;
  };
  export const graphqlOperation: (query: string, variables?: any) => any;
} 