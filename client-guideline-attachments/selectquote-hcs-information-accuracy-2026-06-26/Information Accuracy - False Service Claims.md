# Information Accuracy: False Service Claims

## Objective

Evaluate whether the agent avoids unsupported factual promises about SelectRx or SPM service capabilities, delivery timing, communication expectations, packaging, insurance transition scripting, Care Navigator timing, explicit free/cost-free program or service claims, entitlement claims, trial-service framing, or other operational outcomes.

## Classes

- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Classify as "Yes" when the agent does not make one of this score's unsupported service-claim violations and stays within materially script-approved service language.

## Conditions for Yes

Classify as "Yes" when any of the following are true, provided the statement stays materially faithful to approved script or site language and is not strengthened into an unsupported absolute, guarantee, or certainty claim:

- The agent uses materially script-approved SelectRx value propositions without unsupported guarantees.
- The agent says customers will never have to wait in line, make pharmacy trips, or call doctors for refills.
- The agent says SelectRx or pharmacists are available 24/7.
- The agent says medications are automatically delivered to the door.
- The agent says medications are pre-sorted, individually wrapped, packaged by day and time, or delivered with timing instructions.
- The agent says SelectRx manages monthly refills and customers will not run out when this is clearly tied to automatic refill service.
- The agent uses script-approved timing language such as communication within the next day or two, "arrives on time, every time," "rain or shine," "within 24 hours," or "up to 4 weeks" for first shipment depending on prescription transfer timing.
- The agent says SelectRx uses a proactive delivery model and the box reaches the door before or well before the customer needs to start taking the medication, without promising tomorrow/next-day/overnight delivery.
- The agent mentions next-day or overnight delivery only as optional expedited shipping with additional customer-paid cost.
- The agent says enrollment, setup, or the call process may take 5-10 minutes when clearly referring to enrollment duration rather than medication delivery timing.
- The agent uses a garbled 5-10 minute phrase near "enroll into the program" and shipping/presorted language, but the timeframe most reasonably refers to enrollment/setup rather than guaranteed medication arrival.
- The transcript contains the reviewed phrase pattern "I could be as quick as 5 to 10 minutes as you enroll into the program and get your medication shipped/presorted" and no other explicit False Service violation.
- The agent says Healthcare Select membership itself is free or at no additional cost, or mentions free Medicare health plan monitoring, when not describing SelectRx/SPM medication management as a free/cost-free program or service.
- The agent uses loose "no additional cost" phrasing without explicitly calling SelectRx/SPM a free or cost-free program/service and without entitlement language; ambiguous cost handling belongs to the separate Ambiguous Cost Language score.
- The transcript contains the reviewed phrase pattern "take advantage of something that is no additional cost to you, helping you get it shipped to your door" and no other explicit False Service violation.

## Definition of No

Classify as "No" when the agent makes unsupported or false claims about service capabilities, guaranteed operational outcomes, explicit free/cost-free program or service status, entitlement, trial status, or definite delivery/start timing.

## Conditions for No

Classify as "No" when the agent says or clearly implies any of the following:

- Delivery will never be late as a standalone reliability guarantee.
- Next-day or overnight medication delivery is guaranteed, standard, or included, without clear optional paid-expedited qualification.
- The agent says SelectRx can overnight medication, ship it overnight, provide next-day delivery, or get medication to the customer right away without saying this is optional paid expedited shipping with additional customer-paid cost.
- The first delivery or medication start will definitely arrive or begin within a specific timeframe not supported by the approved "up to 4 weeks" transfer language, and the timeframe clearly modifies medication delivery, shipment, arrival, or start rather than enrollment/setup.
- SelectRx can provide DME supplies such as CGM devices, canes, wheelchairs, CPAP supplies, or incontinence supplies.
- A 90-day supply will come in compliance packaging strips rather than bottles.
- SPM will provide, replace, or arrange a new primary care provider.
- The pharmacy will call the customer in an unsupported context unrelated to enrollment or prescription transfer.
- SelectRx, SPM, or the medication management program/service is explicitly described as a free program, free service, no-cost program, no-cost service, cost-free program, or cost-free service.
- The customer is described as entitled to SelectRx or the medication management program through Healthcare Select membership, under their plan, or because of their plan.
- SelectRx is framed as a trial, temporary test, or something the customer should "try out and see how you feel," rather than a long-term pharmacy transfer for selected medications.
- The agent says "try it out and see how you feel" or similar trial language about SelectRx enrollment.
- The agent adds unsupported certainty words such as "definitely," "guaranteed," or similar absolutes to delivery timing/reliability or other operational promises covered by this score.

## Examples

Clear No examples:

- "Your package will never be late."
- "We guarantee next-day delivery for your meds."
- "SelectRx can overnight it to you if you need it right away" without paid-expedited cost qualification.
- "Your first shipment will definitely arrive next week."
- "You will start getting your medications next month onward" without transfer-timing qualification.
- "SelectRx can provide your wheelchair and CPAP supplies."
- "This is a cost-free medication management program called SelectRx."
- "You are entitled to this cost-free service under your plan."
- "Through your Healthcare Select membership, you are entitled to our medication management program with SelectRx."
- "You should at least try SelectRx and see how you feel about it."

Clear Yes examples:

- "It may take up to 4 weeks to receive your first shipment depending on how quickly we receive your prescriptions."
- "We use a proactive delivery model so your box reaches your door well before you need to start taking the medication."
- "Overnight delivery is available as expedited shipping for an additional fee."
- "This enrollment should take about 5-10 minutes" when the timeframe clearly refers only to enrollment/setup.
- "I could be as quick as 5 to 10 minutes as you enroll into the program and get your medication shipped/presorted" when the timeframe is garbled but tied to enrollment rather than a clear delivery-arrival promise.
- "Healthcare Select membership is offered at no additional cost" when not tied to SelectRx/SPM being free.
- "As part of your membership, we offer a free Medicare health plan monitoring service" when not tied to SelectRx/SPM being free.
- "Why wouldn't you take advantage of something that is no additional cost to you, helping you get it shipped to your door" when not explicitly framed as a free/cost-free SelectRx program/service or entitlement.

## Output Contract

The current score code uses a two-line response format:

- Line 1: only "Yes" or "No".
- Line 2: one brief explanation sentence.
- `parse_from_start` is `true`, so the first-line label maps to `output.value`, and the second-line explanation maps to `output.explanation`.

## Boundary Cases

Treat proactive box-arrival wording as compliant when it does not become a guaranteed accelerated date claim. Treat next-day/overnight language as noncompliant unless the transcript clearly frames it as optional paid expedited shipping with additional customer-paid cost. Treat Healthcare Select membership and Medicare health plan monitoring free/no-additional-cost language as compliant by itself. For this False Service score, fail explicit free/cost-free/no-cost SelectRx or medication-management program/service claims and entitlement claims; route looser no-additional-cost ambiguity to Ambiguous Cost Language. Treat 5-10 minute wording as compliant when it clearly or most reasonably refers to enrollment/setup duration, not medication arrival or shipment timing. If the only potential False Service issues are the reviewed garbled 5-10 minute enrollment phrase and the loose "something no additional cost" phrase, classify as "Yes." The reviewed exclusion does not apply when the call also contains unqualified overnight/next-day delivery or trial-framing language.
