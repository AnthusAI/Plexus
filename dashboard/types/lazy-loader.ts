export type LazyLoader<T, AllowNull extends boolean = false> = {
  data: AllowNull extends true ? T | null : T;
  nextToken?: string | null;
}; 