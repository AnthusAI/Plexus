import { defineFunction } from "@aws-amplify/backend";

export const startConsoleRunFunction = defineFunction({
  name: "startConsoleRun",
  entry: "../../data/resolvers/startConsoleRun.ts",
  runtime: 20,
});
