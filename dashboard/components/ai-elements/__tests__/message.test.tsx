import * as React from "react"
import { render, screen } from "@testing-library/react"

import { Message, MessageContent } from "../message"

describe("MessageContent", () => {
  it("keeps assistant message overflow visible while preserving user bubble clipping", () => {
    render(
      <>
        <Message from="assistant">
          <MessageContent>Assistant response</MessageContent>
        </Message>
        <Message from="user">
          <MessageContent>User prompt</MessageContent>
        </Message>
      </>
    )

    const assistantContent = screen.getByText("Assistant response")
    expect(assistantContent).toHaveClass("overflow-visible")
    expect(assistantContent).not.toHaveClass("overflow-hidden")

    const userMessage = screen.getByText("User prompt").closest(".is-user")
    expect(userMessage).toBeInTheDocument()
    expect(screen.getByText("User prompt")).toHaveClass("group-[.is-user]:overflow-hidden")
    expect(screen.getByText("User prompt")).toHaveClass("group-[.is-user]:rounded-lg")
  })
})
