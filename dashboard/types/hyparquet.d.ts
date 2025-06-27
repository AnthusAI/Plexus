declare module 'hyparquet' {
  export interface ParquetSchema {
    children: Array<{
      element: {
        name: string
      }
    }>
  }

  export interface ParquetMetadata {
    num_rows: bigint | number
  }

  export function parquetMetadataAsync(buffer: ArrayBuffer): Promise<ParquetMetadata>
  export function parquetSchema(metadata: ParquetMetadata): ParquetSchema
  export function parquetReadObjects(options: {
    file: ArrayBuffer
    compressors?: any
    rowStart?: number
    rowEnd?: number
  }): Promise<Record<string, any>[]>
}

declare module 'hyparquet-compressors' {
  export const compressors: any
} 