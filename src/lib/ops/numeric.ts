// Small numeric helpers shared by the ops modules, written to match Python bit for bit.

/** Kahan-compensated sum, the algorithm pandas uses for groupby().sum() on floats. */
export function kahanSum(values: number[]): number {
  let sum = 0;
  let compensation = 0;
  for (const value of values) {
    const y = value - compensation;
    const t = sum + y;
    compensation = t - sum - y;
    sum = t;
  }
  return sum;
}

/** Index of the first maximum (numpy argmax). */
export function argmax(values: number[]): number {
  let best = 0;
  for (let i = 1; i < values.length; i++) if (values[i] > values[best]) best = i;
  return best;
}

/** Index of the first minimum (numpy argmin). */
export function argmin(values: number[]): number {
  let best = 0;
  for (let i = 1; i < values.length; i++) if (values[i] < values[best]) best = i;
  return best;
}

/** numpy.searchsorted(edges, value, side="right"): how many edges are <= value. */
export function searchsortedRight(edges: number[], value: number): number {
  let count = 0;
  for (const edge of edges) if (edge <= value) count++;
  return count;
}

/** String comparison by UTF-16 code units, like Python's default sort for ASCII ids. */
export function compareText(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Turn -0 into 0 so integer results compare equal to Python's. */
export function noNegativeZero(value: number): number {
  return value + 0;
}
