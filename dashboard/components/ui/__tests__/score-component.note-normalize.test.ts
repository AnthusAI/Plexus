import { normalizeScoreVersionNote } from "@/components/ui/score-component"

describe("normalizeScoreVersionNote", () => {
  it("returns undefined for blank notes", () => {
    expect(normalizeScoreVersionNote("")).toBeUndefined()
    expect(normalizeScoreVersionNote("   ")).toBeUndefined()
  })

  it("returns trimmed note text when provided", () => {
    expect(normalizeScoreVersionNote("  Updated configuration  ")).toBe("Updated configuration")
  })
})

