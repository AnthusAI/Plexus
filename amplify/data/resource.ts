import { type ClientSchema, a, defineData } from "@aws-amplify/backend";

/*== STEP 1 ===============================================================
The section below creates a Todo database table with a "content" field. Try
adding a new "isDone" field as a boolean. The authorization rule below
specifies that any user authenticated via an API key can "create", "read",
"update", and "delete" any "Todo" records.
=========================================================================*/
// const schema = a.schema({
//   Todo: a
//     .model({
//       content: a.string(),
//     })
//     .authorization((allow) => [allow.publicApiKey()]),
// });

// export type Schema = ClientSchema<typeof schema>;

// export const data = defineData({
//   schema,
//   authorizationModes: {
//     defaultAuthorizationMode: "apiKey",
//     apiKeyAuthorizationMode: {
//       expiresInDays: 30,
//     },
//   },
// });

/*== STEP 2 ===============================================================
Go to your frontend source code. From your client-side code, generate a
Data client to make CRUDL requests to your table. (THIS SNIPPET WILL ONLY
WORK IN THE FRONTEND CODE FILE.)

Using JavaScript or Next.js React Server Components, Middleware, Server 
Actions or Pages Router? Review how to generate Data clients for those use
cases: https://docs.amplify.aws/gen2/build-a-backend/data/connect-to-API/
=========================================================================*/

/*
"use client"
import { generateClient } from "aws-amplify/data";
import type { Schema } from "@/amplify/data/resource";

const client = generateClient<Schema>() // use this Data client for CRUDL requests
*/

/*== STEP 3 ===============================================================
Fetch records from the database and use them in your frontend component.
(THIS SNIPPET WILL ONLY WORK IN THE FRONTEND CODE FILE.)
=========================================================================*/

/* For example, in a React component, you can use this snippet in your
  function's RETURN statement */
// const { data: todos } = await client.models.Todo.list()

// return <ul>{todos.map(todo => <li key={todo.id}>{todo.content}</li>)}</ul>

const schema = a.schema({
  Account: a
    .model({
      name: a.string().required(),
      key: a.string().required(),
      description: a.string(),
      scorecards: a.hasMany('Scorecard', 'accountId'),
    })
    .authorization((allow) => [allow.authenticated()])
    .secondaryIndexes((idx) => [
      idx("key")
    ]),

  Scorecard: a
    .model({
      name: a.string().required(),
      key: a.string().required(),
      externalId: a.string().required(),
      description: a.string(),
      scoreDetails: a.json(),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      scores: a.hasMany('Score', 'scorecardId'),
    })
    .authorization((allow) => [allow.authenticated()])
    .secondaryIndexes((idx) => [
      idx("accountId"),
      idx("key"),
      idx("externalId")
    ]),

  Score: a
    .model({
      name: a.string().required(),
      type: a.string().required(),
      accuracy: a.float(),
      version: a.string(),
      scorecardId: a.string().required(),
      scorecard: a.belongsTo('Scorecard', 'scorecardId'),
    })
    .authorization((allow) => [allow.authenticated()])
    .secondaryIndexes((idx) => [
      idx("scorecardId")
    ]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool'
  },
});