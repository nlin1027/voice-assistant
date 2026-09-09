// Local-time date helpers for the month-grid calendar. No date library — the math here is
// intentionally simple (whole days, local timezone only) so it stays dependency-free.

export const toDateKey = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export const isSameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

export const addMonths = (date: Date, delta: number) => {
  const d = new Date(date);
  d.setMonth(d.getMonth() + delta);
  return d;
};

// Always 42 cells (6 full weeks) so the grid height doesn't jump between months.
export const getMonthGrid = (year: number, month: number): Date[] => {
  const firstOfMonth = new Date(year, month, 1);
  const gridStart = new Date(year, month, 1 - firstOfMonth.getDay());
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    return d;
  });
};
