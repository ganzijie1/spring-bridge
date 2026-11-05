import timeline from './timeline.json';

export const FPS = timeline.fps;
export const DURATION_SECONDS = timeline.duration_seconds;
export const DURATION_FRAMES = FPS * DURATION_SECONDS;

export const at = (seconds: number) => Math.round(seconds * FPS);
export const cue = (name: keyof typeof timeline.cues) => at(timeline.cues[name]);

export default timeline;
