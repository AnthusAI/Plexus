import React from "react"
import { FilterControl, FilterConfig } from "@/components/filter-control"
import { TimeRangeSelector } from "@/components/time-range-selector"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ChevronDown } from "lucide-react"

interface ItemContextProps {
  handleFilterChange: (newFilters: FilterConfig) => void;
  handleSampleChange: (method: string, count: number) => void;
  handleTimeRangeChange: (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => void;
  availableFields: Array<{ value: string; label: string }>;
  timeRangeOptions: Array<{ value: string; label: string }>;
}

const SampleControl = ({ onSampleChange }: { onSampleChange: (method: string, count: number) => void }) => {
  const [method, setMethod] = React.useState("All")
  const [count, setCount] = React.useState(100)

  const handleMethodChange = (value: string) => {
    setMethod(value)
    onSampleChange(value, count)
  }

  const handleCountChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newCount = parseInt(event.target.value, 10)
    setCount(newCount)
    onSampleChange(method, newCount)
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="w-[200px] h-10 justify-start text-left font-normal">
          <span>Sample: {method}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label>Sampling Method</Label>
            <Select value={method} onValueChange={handleMethodChange}>
              <SelectTrigger className="w-full h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                <SelectItem value="Random">Random</SelectItem>
                <SelectItem value="Sequential">Sequential</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Item Count</Label>
            <Input
              type="number"
              value={count}
              onChange={handleCountChange}
              min={1}
              max={1000}
              className="h-10"
            />
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

const ItemContext: React.FC<ItemContextProps> = ({
  handleFilterChange,
  handleSampleChange,
  handleTimeRangeChange,
  availableFields,
  timeRangeOptions
}) => {
  // Ensure timeRangeOptions is always an array
  const safeTimeRangeOptions = Array.isArray(timeRangeOptions) ? timeRangeOptions : [];

  return (
    <div className="flex flex-wrap gap-2">
      <FilterControl onFilterChange={handleFilterChange} availableFields={availableFields} />
      <SampleControl onSampleChange={handleSampleChange} />
      {safeTimeRangeOptions.length > 0 && (
        <TimeRangeSelector onTimeRangeChange={handleTimeRangeChange} options={safeTimeRangeOptions} />
      )}
    </div>
  )
}

export default ItemContext
