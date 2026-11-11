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

export function VideoTable() {
  const { vocab, videos } = useLibrary()
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = [
    col.accessor((v) => vocab.role[v.role], { id: 'role', header: '角色' }),
    col.accessor('name', {
      header: '名称',
      cell: ({ row }) => (
        <Link
          to='/videos/$id'
          params={{ id: row.original.id }}
          className='font-medium underline-offset-4 hover:underline'
        >
          {row.original.name}
        </Link>
      ),
    }),
    col.accessor('duration', {
      header: '时长',
      cell: ({ getValue }) => clock(getValue()),
    }),
    col.accessor('fps', {
      header: '帧率',
      cell: ({ getValue }) => +getValue().toFixed(2),
    }),
    col.accessor(
      (v) =>
        [...new Set(v.swings.flatMap((s) => s.label.camera ?? []))]
          .map((camera) => vocab.camera[camera] ?? camera)
          .join('、'),
      { id: 'cameras', header: '机位' }
    ),
    col.accessor((v) => v.swings.length, { id: 'swings', header: '拍数' }),
    col.accessor((v) => v.swings.filter((s) => s.label.usable).length, {
      id: 'usable',
      header: '可用',
    }),
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
    <Main>
      <h1 className='mb-4 text-2xl font-bold tracking-tight'>素材库</h1>
      <div className='overflow-hidden rounded-md border'>
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
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className='px-4'>
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
