# Information Accuracy: False Carrier Claims

## Objective

Evaluate whether the agent avoids falsely saying or clearly implying that SelectRx, the pharmacy service, enrollment, no-fee/service-fee status, or the customer's qualification for the service is provided by, part of, tailored through, or available because of the customer's carrier, Medicare Advantage plan, Medicare plan, or insurance plan.

## Classes

- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Classify as "Yes" when the agent does not misattribute the offered service, enrollment, pharmacy recommendation, or service-fee/no-fee status to the customer's carrier or plan.

## Conditions for Yes

Classify as "Yes" when any of the following are true:

- The agent accurately presents the service as offered by Healthcare Select, Population Health, SelectQuote, SelectRx, or affiliated partners without saying it is provided through the customer's carrier or Medicare plan.
- The agent says the customer's insurance or carrier determines copays, coverage, approval, network support, or patient responsibility.
- The agent clarifies that the customer's insurance is not changing.
- The agent says the customer may be eligible or qualified after a questionnaire or based on general criteria, as long as the agent does not say the service itself is through, because of, under, tailored through, or part of the carrier or plan.
- The agent references insurance only for coverage/payment mechanics, not as the source or sponsor of the service.

## Definition of No

Classify as "No" when the agent says or clearly implies that the offered service, enrollment, pharmacy recommendation, no-fee/service-fee status, or customer qualification is through, because of, under, tailored through, part of, or provided by the customer's carrier, Medicare plan, Medicare Advantage plan, or insurance plan.

## Conditions for No

Classify as "No" when the agent says or clearly implies any of the following:

- The service, enrollment, pharmacy, or medication management program is through the customer's Medicare plan, Medicare Advantage plan, carrier, or insurance plan.
- The customer qualifies for the service because of the plan in a way that makes the plan sound like the source of the service.
- The service is tailored through the customer's carrier or is the best pharmacy for the customer because of that carrier.
- There is no delivery fee or service fee because of the customer's plan.
- The customer would be missing out on a plan benefit if they do not enroll.
- The service itself is part of the customer's plan or a carrier-provided benefit.

## Examples

Clear No examples:

- "This is part of the new UHC plan you just signed up for."
- "With your Aetna plan, this is the pharmacy."
- "Your carrier provides this pharmacy service."
- "You qualify for this service through your Medicare plan."
- "This is tailored through your Anthem, so it is the best pharmacy for you."
- "There is no delivery fee or service fee because of the plan you have."
- "Because of your plan, if you do not have it you are missing out."

Clear Yes examples:

- The agent says the customer's carrier determines copays.
- The agent says coverage or patient responsibility depends on the customer's plan.
- The agent says the customer's insurance is not changing.
- The agent says the customer qualifies for a Healthcare Select service after the questionnaire, without tying the service to the carrier or plan.

## Boundary Cases

Do not infer carrier ownership from ordinary insurance, eligibility, coverage, copay, enrollment, approval, or "through your insurance" language alone. Do classify as "No" when the phrasing ties the service, pharmacy recommendation, fee status, or qualification to the plan as the source, sponsor, entitlement, or reason the customer should enroll.
