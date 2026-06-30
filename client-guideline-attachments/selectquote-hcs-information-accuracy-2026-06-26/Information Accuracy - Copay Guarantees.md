# Information Accuracy: Copay Guarantees

## Objective

Evaluate whether the agent avoids unsupported, definitive guarantees about medication costs, copay amounts, copay payment timing, coupon acceptance, hardship/payment relief, or whether copays will remain the same.

## Classes

- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Classify as "Yes" when the agent keeps medication cost and copay responsibility carrier/plan/network determined and does not make unsupported promises about amounts, sameness, payment timing, coupons, or affordability relief.

## Conditions for Yes

Classify as "Yes" when any of the following are true:

- The agent avoids definitive or guaranteed claims about medication costs, copay amounts, or copay payment terms.
- The agent uses hypothetical or clearly qualified future-cost language without turning it into a guarantee.
- The agent says the patient could have a copay depending on the plan, carrier, insurance, or network.
- The agent says packaging and standard delivery are provided at no additional cost while copays remain determined by the insurance plan as they are today.
- The agent describes standard payment methods for a bill without implying a guaranteed amount, fixed payment window, coupon acceptance, hardship eligibility, or optional payment.

## Definition of No

Classify as "No" when the agent states or guarantees as fact that medication costs or copays will be a certain amount, will stay the same, will not go up, will not exist, can be delayed for a specific unsupported period, can be offset by coupons or hardship programs, or are otherwise fixed without carrier-determined proof.

## Conditions for No

Classify as "No" when the agent says or clearly implies any of the following without approved carrier-determined support:

- The customer's copays will stay the same or should be the same.
- The service or medication will cost the same as now.
- The customer will only have a small copay as a definite fact.
- The customer will not have a copay, or if they do not currently have copays they will not have any.
- The customer does not need to pay copays upfront and will have a specific time period, such as 30 days, to pay them.
- SelectRx accepts coupons for copays or prescriptions.
- The customer can use a hardship program if they cannot afford copays.
- The agent can guarantee the price, copay, payment timing, or payment relief.

## Examples

Clear No examples:

- "Your copays will stay the same."
- "It should be the same."
- "You will only have a small copay."
- "You won't have a copay."
- "They bill you for copays and you have 30 days to pay them."
- "We accept coupons as well."
- "If you cannot afford them, use the hardship program."
- "If you do not have copays, you will not have any."

Clear Yes examples:

- "You could have a copay depending on your plan."
- "Packaging and standard delivery are provided at no additional cost, and any copays are determined by your insurance plan, as they are today."
- "Depending on your network, you will pay copays according to your insurance plan."
- "If you receive a bill, you can pay by phone, check, money order, or autopay" when not paired with unsupported amount, timing, coupon, or hardship claims.

## Boundary Cases

Hypothetical or clearly qualified future-cost phrasing is not enough to fail by itself. Cost language remains compliant when the agent keeps medication and copay responsibility dependent on insurance, the carrier, the plan, or the customer's network. Payment-method language is compliant only when it does not add unsupported guarantees about timing, coupons, hardship programs, affordability, or fixed/same/no copays.
