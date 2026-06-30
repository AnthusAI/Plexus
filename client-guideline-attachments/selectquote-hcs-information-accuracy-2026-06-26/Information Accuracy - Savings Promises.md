# Information Accuracy: Savings Promises

## Objective

Evaluate whether the agent avoids promising that enrolling in SelectRx will make medications free, lower copays, save money, price match, or otherwise reduce medication expense. This guideline mirrors the current champion score prompt and does not add new scoring behavior.

## Classes

- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Classify as "Yes" when the agent does not promise that enrolling in SelectRx will make medications free, lower the patient's copays, save the patient money, price match, or otherwise reduce medication expense.

## Conditions for Yes

Classify as "Yes" when any of the following are true:

- The agent avoids claims that SelectRx or SRx enrollment will reduce medication spending or provide free medications.
- The agent only says Healthcare Select membership, packaging, or delivery are free or available at no additional cost, without saying SelectRx or SRx will reduce medication prices, lower copays, save money, or cover medication costs.
- The agent uses scripted HCS Discount Rx Card language in an SPM or non-SRx flow, including that a free prescription discount card can help the customer save money off the pharmacy's retail or resale price on eligible prescriptions.
- The agent discusses generic affordability, carrier-determined copays, eligibility checks, or estimates that remain subject to the plan and are not tied to SelectRx or SRx enrollment.
- The agent says a copay or price is "best" or "lowest" but clearly attributes that to the carrier, plan, or eligibility rather than SelectRx.
- Hypothetical copay language remains hypothetical and is not turned into an explicit savings promise.

## Definition of No

Classify as "No" when the agent claims or strongly implies that enrolling in SelectRx will reduce medication spending or provide free medications.

## Conditions for No

Classify as "No" when the agent says or clearly implies any of the following:

- SelectRx or SRx will save the customer money.
- The customer will pay less than what they pay now because of SelectRx or SRx.
- The customer's medications will be free because of SelectRx or SRx.
- The customer's copays will be lower because of SelectRx or SRx.
- SelectRx or SRx provides price matching.
- SelectRx or SRx is the customer's preferred pharmacy in a savings or cost-reduction context.
- SelectRx or SRx will cover the medication cost for the customer.
- The HCS Discount Rx Card savings are tied to SelectRx enrollment or presented as SelectRx or SRx lowering medication costs.

## Examples

Clear No examples:

- "SRx will save you money."
- "You'll pay less than what you pay now."
- "Your medications will be free."
- "Your copays will be lower."
- "We do price matching."
- "SelectRx will cover the cost for you."

Clear Yes examples:

- The agent says Healthcare Select membership is free.
- The agent says packaging or delivery are available at no additional cost without promising medication savings.
- In an SPM or non-SRx flow, the agent offers a free HCS Discount Rx Card that may help save money off eligible prescriptions at the pharmacy's retail or resale price.
- The agent says copays are carrier-determined or plan-based.

## Boundary Cases

Do not use this score for hypothetical copay language unless the agent turns that language into an explicit savings promise. Cost outcomes that remain carrier-determined are compliant. Do not treat HCS Discount Rx Card language as a SelectRx savings promise unless the agent ties the savings to SelectRx enrollment or says SelectRx or SRx itself will lower medication costs.

Current output contract: the classifier is instructed to return one brief explanation sentence first and a final line containing only Yes or No. The graph maps the parsed classification to output.value and the parsed explanation to output.explanation; this is the current parser contract, not a separate scoring rule.

The target and default class entries in these guidelines are rubric metadata for review and validation. The current score code does not encode a separate default-label fallback beyond the classifier's valid labels and prompt instructions.
