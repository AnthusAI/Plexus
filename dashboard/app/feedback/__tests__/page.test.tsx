import FeedbackPage from "../page";
import LabFeedbackQueuesPage from "../../lab/feedback-queues/page";
import { redirect } from "next/navigation";

jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
}));

const mockRedirect = redirect as jest.MockedFunction<typeof redirect>;

describe("feedback redirects", () => {
  beforeEach(() => {
    mockRedirect.mockReset();
  });

  it("redirects /feedback to the canonical lab feedback dashboard", () => {
    FeedbackPage();
    expect(mockRedirect).toHaveBeenCalledWith("/lab/feedback");
  });

  it("redirects /lab/feedback-queues to the canonical lab feedback dashboard", () => {
    LabFeedbackQueuesPage();
    expect(mockRedirect).toHaveBeenCalledWith("/lab/feedback");
  });
});
