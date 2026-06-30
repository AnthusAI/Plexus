# Information Accuracy: Ambiguous Cost Language

## Objective

Evaluate whether the agent handles SelectRx or SPM no-cost language and billing language without obscuring medication copays, member payment responsibility, due-date expectations, or expedited-delivery cost qualification.

## Classes

- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Classify as "Yes" when service-level no-cost language and billing language preserve that member responsibility remains insurance/plan/network determined and billed with standard due-date expectations.

## Conditions for Yes

Classify as "Yes" when any of the following are true:

- No SelectRx/SPM no-cost or billing ambiguity appears.
- The agent uses service-level no-cost language and, in the same answer or immediately adjacent explanation, preserves insurance-determined copay/member responsibility.
- The agent says packaging and standard delivery are at no additional cost while clarifying copays or patient responsibility are still insurance-determined.
- The agent states that bills are still due and must be paid according to due-date expectations.
- The agent discusses next-day/overnight only as optional expedited shipping with additional customer-paid cost.
- The agent only says Healthcare Select membership is free without blurring into SelectRx/SPM service or medication payment responsibility.
- The agent uses approved non-SRx HCS Discount Rx Card language without blurring into SelectRx/SPM service-cost responsibility.

## Definition of No

Classify as "No" when no-cost language or billing language obscures patient responsibility, due-date expectations, or expedited-delivery cost qualification.

## Conditions for No

Classify as "No" when any of the following are true:

- A customer asks about cost and the agent answers that SelectRx/SPM, the program, or the service has no cost, is free, or costs nothing without clarifying in that same answer or immediately adjacent explanation that medication copays/member payment responsibility may still apply.
- The agent directly answers a customer cost question with only "No," "there is no cost," "no cost to use the service," or equivalent no-cost reassurance, even if the transcript contains generic copay language elsewhere.
- SelectRx/SPM is described as free/no-cost without preserving that member payment responsibility remains insurance/plan/network determined.
- SelectRx/SPM no-cost language is paired with explicit dollar amount, "same copay," or fixed-payment wording without explicit insurance-determined qualification.
- The agent implies the customer does not need to pay the bill, can skip payment if unable to pay, or can pay whenever with no due-date expectation.
- The agent presents next-day/overnight medication delivery as free/included/no-cost.
- The agent uses free-delivery language without clarifying that expedited next-day/overnight delivery has additional customer-paid cost.

## Examples

Clear No examples:

- Customer asks, "Does it cost anything?" and the agent answers, "No, there is no cost to use the service," without clarifying possible medication copays in that same answer.
- Customer asks about cost and the agent says, "No. There is no cost," while copay language appears elsewhere in the call.
- "You don't have to worry about paying that bill if you can't."
- "Just pay whenever you can; there is no real due date."
- "Delivery is free and we can overnight it tomorrow" without additional cost qualification.
- "SelectRx is free to you" without preserving insurance-determined patient responsibility.

Clear Yes examples:

- "Packaging and standard delivery are at no additional cost, and your copays are still determined by your insurance plan."
- Customer asks about cost and the agent answers, "There is no additional fee for the service or standard delivery, but your medication copays are still determined by your insurance."
- "You will still receive a bill and it has a due date."
- "Overnight delivery is available as expedited shipping for an additional fee."
- "Healthcare Select membership is free" when not tied to SelectRx/SPM medication/payment responsibility.

## Boundary Cases

Do not fail statements that only say Healthcare Select membership is free unless they are blurred into SelectRx/SPM medication/payment responsibility. A later general statement about copays does not cure a direct misleading answer to a cost question if the agent answers "no cost" without a same-answer or immediately adjacent distinction between service/standard delivery and medication copays. Billing language is noncompliant when it suggests payment is optional or due dates do not matter.
