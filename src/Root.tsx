import React from 'react';
import {Composition} from 'remotion';
import {Shanghai1976} from './Shanghai1976';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Shanghai1976"
    component={Shanghai1976}
    durationInFrames={2400}
    fps={30}
    width={1920}
    height={1080}
  />
);
