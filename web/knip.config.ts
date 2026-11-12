import type { KnipConfig } from 'knip'

const config: KnipConfig = {
  // vendored shadcn files keep their full export list; an unused file still fails
  ignoreIssues: { 'src/components/ui/**': ['exports', 'types'] },
}

export default config
