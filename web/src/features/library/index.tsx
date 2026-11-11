import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import {
  type SortingState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { type Video, clock, useLibrary } from '@/lib/library'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DataTableColumnHeader } from '@/components/data-table'
import { Main } from '@/components/layout/main'

const col = createColumnHelper<Video>()

const count = (v: Video) => ({
  usable: v.swings.filter((s) => s.label.usable).length,
  reviewed: v.swings.filter((s) => s.label.source === 'human').length,
})

export function VideoTable() {
  const { vocab, videos } = useLibrary()
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = [
    col.accessor('name', {
      header: '视频',
      cell: ({ row }) => (
        <Link
          to='/videos/$id'
          params={{ id: row.original.id }}
          className='font-medium after:absolute after:inset-0'
        >
          {row.original.name}
        </Link>
      ),
    }),
    col.accessor((v) => vocab.role[v.role], {
      id: 'role',
      header: '角色',
      cell: ({ row, getValue }) => (
        <Badge variant={row.original.role === 'coach' ? 'default' : 'outline'}>
          {getValue()}
        </Badge>
      ),
    }),
    col.accessor(
      (v) =>
        [...new Set(v.swings.flatMap((s) => s.label.camera ?? []))]
          .map((camera) => vocab.camera[camera] ?? camera)
          .join(' · '),
      { id: 'cameras', header: '机位' }
    ),
    col.accessor('duration', {
      header: '时长',
      cell: ({ getValue }) => clock(getValue()).replace(/\.\d+$/, ''),
    }),
    col.accessor((v) => count(v).usable, {
      id: 'usable',
      header: '可用 / 拍数',
      cell: ({ row, getValue }) => (
        <>
          {getValue()}
          <span className='text-muted-foreground'>
            {' '}
            / {row.original.swings.length}
          </span>
        </>
      ),
    }),
    col.accessor((v) => count(v).reviewed, { id: 'reviewed', header: '已审' }),
  ]
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: videos,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <Main fluid className='flex flex-col gap-4 pt-2'>
      <h1 className='text-2xl font-bold tracking-tight'>素材库</h1>
      <div className='overflow-hidden rounded-lg border'>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id}>
                {group.headers.map((header) => (
                  <TableHead key={header.id}>
                    <DataTableColumnHeader
                      column={header.column}
                      title={header.column.columnDef.header as string}
                    />
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id} className='relative'>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className='px-4 tabular-nums'>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
            {videos.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className='h-24 text-center'
                >
                  库里还没有视频。先用 clean.py 清洗一个视频。
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </Main>
  )
}
