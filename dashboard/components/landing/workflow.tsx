"use client"

import { CircleNode } from "../workflow/nodes"
import { Check } from "lucide-react"
import React from "react"
import WorkflowBase from "../workflow/base/workflow-base"

const Workflow = React.forwardRef<SVGGElement>((props, ref) => {
  return <WorkflowBase ref={ref} />
})

Workflow.displayName = 'Workflow'

export default React.memo(Workflow)

