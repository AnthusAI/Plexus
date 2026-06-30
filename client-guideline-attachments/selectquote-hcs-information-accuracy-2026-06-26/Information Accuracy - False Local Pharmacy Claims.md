# Information Accuracy: False Local Pharmacy Claims

## Objective

Evaluate whether the agent correctly explains SelectRx pharmacy transition and uses compliant short-term local-pharmacy bridge language without implying that the customer may use a local pharmacy interchangeably for the same medications being moved to SelectRx.

## Classes

- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Classify as "Yes" when the agent correctly represents that SelectRx becomes the pharmacy for selected medications and any local-pharmacy bridge guidance is short-term and compliant.

## Conditions for Yes

Classify as "Yes" when any of the following are true:

- The agent correctly explains that SelectRx becomes the pharmacy for medications the customer elects to fill through SelectRx.
- The agent says SelectRx will become the customer's primary pharmacy.
- The agent explains that some medications may remain at a local pharmacy, as long as the same medication is not represented as being filled both locally and through SelectRx.
- The agent gives temporary local refill guidance framed as a short bridge while SelectRx synchronizes medications, such as "within the next 5 days," "next few days," or "within a week."
- The agent avoids language that implies local-pharmacy use continues until first SelectRx delivery or that the customer can keep using local pharmacy interchangeably for selected ongoing medications.

## Definition of No

Classify as "No" when the agent implies dual-fill or interchangeable use for the same selected medications, uses noncompliant extended bridge language, or frames SelectRx as only a delivery layer for the local pharmacy.

## Conditions for No

Classify as "No" when the agent says or clearly implies any of the following:

- The customer will use both pharmacies for the same medications being moved to SelectRx.
- The customer can continue using Walgreens, CVS, Walmart, or another local pharmacy while primarily receiving the same selected medications from SelectRx.
- The agent says "you can still use Walgreens/CVS/Walmart/local pharmacy" and then says the customer will primarily get medications at home, without clearly limiting local pharmacy use to non-transferred medications or a one-time short bridge.
- The customer can continue local pharmacy use for medications being moved to SelectRx until first delivery/first box/first shipment arrives.
- A noncompliant local-pharmacy statement appears earlier in the call; later compliant "within 5 days" recap language does not cure that earlier violation.
- The customer should keep using local pharmacy beyond about one week for medications being moved to SelectRx.
- SelectRx only delivers medications that the local pharmacy fills.
- The same selected medication will be filled both locally and through SelectRx.

## Examples

Clear No examples:

- "Use your local pharmacy until your first SelectRx delivery arrives."
- "Keep filling those same meds locally until your first box shows up."
- "You will use both pharmacies for those same medications."
- "You can still use Walgreens, but you will primarily get your medications delivered at home" when it implies interchangeable use for the same selected medications.

Clear Yes examples:

- "SelectRx will become your primary pharmacy."
- "If you need an immediate refill, pick it up at your local pharmacy within the next 5 days while we synchronize your meds."
- "Use your local pharmacy in the next few days, but not as an ongoing replacement for meds being moved to SelectRx."
- "Some medications may remain at your local pharmacy" when the agent clearly means medications not being transferred to SelectRx.

## Output Contract

The score code uses a two-line response format:

- Line 1: one brief explanation sentence.
- Line 2: only "Yes" or "No".
- The model is instructed not to output "Yes" or "No" anywhere except Line 2.

Because `parse_from_start` is `false`, the final-line label maps to `output.value`, and the explanation maps to `output.explanation`.

## Boundary Cases

"Within a week" is treated as the maximum compliant short bridge for local refill wording in this score. "Until first delivery" or any longer/effectively open-ended bridge wording for medications being moved to SelectRx is noncompliant. Saying the customer can still use a local pharmacy is compliant only when it clearly refers to medications not being moved to SelectRx or to a one-time short bridge such as the next 5 days; it is noncompliant when it implies interchangeable ongoing use for the same selected medications. Do not let a later compliant recap erase an earlier confusing or noncompliant local-pharmacy statement.
