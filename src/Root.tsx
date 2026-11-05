import React from 'react';
import {Composition} from 'remotion';
import {Shanghai1976} from './Shanghai1976';
import {
  COUNTERFACTUAL_DURATION_FRAMES,
  COUNTERFACTUAL_FPS,
  Shanghai1976Counterfactual,
} from './Shanghai1976Counterfactual';
import {DURATION_FRAMES, FPS} from './timeline';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Shanghai1976Counterfactual"
      component={Shanghai1976Counterfactual}
      durationInFrames={COUNTERFACTUAL_DURATION_FRAMES}
      fps={COUNTERFACTUAL_FPS}
      width={1920}
      height={1080}
    />
    <Composition
      id="Shanghai1976"
      component={Shanghai1976}
      durationInFrames={DURATION_FRAMES}
      fps={FPS}
      width={1920}
      height={1080}
    />
  </>
);
