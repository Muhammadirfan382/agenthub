/**
 * Demo timestamps are generated relative to when the app loads, so the demo
 * always looks recent. They do not describe real events.
 */
const loadedAt = Date.now();

export const minutesAgo = (minutes: number): string => new Date(loadedAt - minutes * 60_000).toISOString();
export const hoursAgo = (hours: number): string => minutesAgo(hours * 60);
export const daysAgo = (days: number): string => minutesAgo(days * 24 * 60);
