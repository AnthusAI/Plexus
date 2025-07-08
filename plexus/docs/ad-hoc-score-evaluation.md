# Ad-Hoc Score evaluation

Here's how you can test score results to see if score configurations are working, and if they're producing the expected values.

## Single Prediction

You can check one score prediction with the `plexus predict` command, like this:

```
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "d0971986-3838-4066-80ea-548b90a27f4d"
```

## Multiple Predictions

If you want to run an ad-hoc evaluation to check more than one label at once, then you can grep the `predict` command for the `"value"` part of the output:

```
echo "Should be Yes (1/3): 6ded9491-5909-4a7c-8642-c9a4a61db404:" && plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "6ded9491-5909-4a7c-8642-c9a4a61db404" --format json 2>/dev/null | grep '"value"' | head -1
echo "Should be Yes (2/3): a312c48c-d2bd-4e5c-bd2a-126e4a992ee6:" && plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "a312c48c-d2bd-4e5c-bd2a-126e4a992ee6" --format json 2>/dev/null | grep '"value"' | head -1
echo "Should be Yes (3/3): 3e9ac926-c376-44b7-8e70-12a6202958bb:" && plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "3e9ac926-c376-44b7-8e70-12a6202958bb" --format json 2>/dev/null | grep '"value"' | head -1
```

```
Should be Yes (1/3): 6ded9491-5909-4a7c-8642-c9a4a61db404:
      "value": "No",
Should be Yes (2/3): a312c48c-d2bd-4e5c-bd2a-126e4a992ee6:
      "value": "No",
Should be Yes (3/3): 3e9ac926-c376-44b7-8e70-12a6202958bb:
      "value": "Yes",
```

## Ground-Truth Labels From Feedback Items

We might show you feedback items that indicate that one of our predictions was correct or incorrect.  The correct answer value is the 'final answer value'.  Our original answer is the initial answer value and the iniital answer comment.  If the edit comment contradicts the answer comment then the edit comment is correct.

Use this information as hints to understand why a score configuration made the wrong decisions.

```
[
  {
    "id": "ee30c3d0-04b8-4a81-abe7-55f1be896361",
    "initialAnswerValue": "No",
    "finalAnswerValue": "Yes",
    "initialCommentValue": "The agent made several statements that could be considered misleading or misrepresentative regarding the services being offered:1. **Claims about medication costs or patient copays**: The agent stated, \"With this the prices when it comes to SelectRX, they are just determined by your insurance carrier as far as if you have co pays.\" Final classification: **No**",
    "finalCommentValue": "",
    "editCommentValue": "Agent did not promise no copays and did mention copays. ",
    "editedAt": "2025-06-10 07:14:58.267000+00:00",
    "editorName": "SQ KKunkle",
    "isAgreement": false,
    "scorecardId": "59125ba2-670c-4aa5-b796-c2085cf38a0c",
    "scoreId": "69e2adba-553e-49a3-9ede-7f9a679a08f3",
    "itemId": "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
    "cacheKey": "69e2adba-553e-49a3-9ede-7f9a679a08f3:57011537",
    "createdAt": "2025-07-08 15:40:09.929000+00:00",
    "updatedAt": "2025-07-08 15:40:09.929000+00:00",
    "item": {
      "id": "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
      "identifiers": "[{\"name\":\"form ID\",\"id\":\"57011537\",\"url\":\"https://app.callcriteria.com/r/57011537\"},{\"name\":\"XCC ID\",\"id\":\"45813\"},{\"name\":\"session ID\",\"id\":\"D9DDBDC405EA402EB0C3E5E7A8919C27\"}]",
      "externalId": "57011537"
    }
  },
  ```