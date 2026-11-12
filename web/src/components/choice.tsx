import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Radix Select has no empty value, so "nothing chosen" is an item of its own.
const NONE = '__none__'

type ChoiceProps<K extends string> = {
  value: K | undefined
  options: Record<K, string>
  /** Name of "nothing chosen". Left out, something is always chosen. */
  none?: string
  onChange: (value: K | undefined) => void
  id?: string
  'aria-label'?: string
}

export function Choice<K extends string>({
  value,
  options,
  none,
  onChange,
  ...props
}: ChoiceProps<K>) {
  return (
    <Select
      value={value ?? NONE}
      onValueChange={(v) => onChange(v === NONE ? undefined : (v as K))}
    >
      <SelectTrigger className='w-full' {...props}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {none && <SelectItem value={NONE}>{none}</SelectItem>}
        {Object.entries<string>(options).map(([key, name]) => (
          <SelectItem key={key} value={key}>
            {name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
