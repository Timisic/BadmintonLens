import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Radix Select has no empty value, so "nothing chosen" is an item of its own.
const NONE = '__none__'

type ChoiceProps = {
  value: string | undefined
  options: Record<string, string>
  none: string
  onChange: (value: string | undefined) => void
  id?: string
  'aria-label'?: string
}

export function Choice({
  value,
  options,
  none,
  onChange,
  ...props
}: ChoiceProps) {
  return (
    <Select
      value={value ?? NONE}
      onValueChange={(v) => onChange(v === NONE ? undefined : v)}
    >
      <SelectTrigger className='w-full' {...props}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>{none}</SelectItem>
        {Object.entries(options).map(([key, name]) => (
          <SelectItem key={key} value={key}>
            {name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
