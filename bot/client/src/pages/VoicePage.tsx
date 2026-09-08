import { useEffect } from 'react';

import type { PipecatBaseChildProps } from '@pipecat-ai/voice-ui-kit';
import {
  ConnectButton,
  UserAudioControl,
  VoiceVisualizer,
} from '@pipecat-ai/voice-ui-kit';

export const VoicePage = ({
  client,
  handleConnect,
  handleDisconnect,
}: PipecatBaseChildProps) => {
  useEffect(() => {
    client?.initDevices();
  }, [client]);

  return (
    <div className="flex flex-col items-center justify-center gap-16 w-full h-full px-6">
      <VoiceVisualizer
        participantType="bot"
        barColor="#ef4444"
        barCount={9}
        barWidth={10}
        barGap={8}
        barMaxHeight={180}
        barOrigin="center"
      />
      <div className="flex items-center flex-wrap justify-center gap-4">
        <UserAudioControl size="lg" noDevicePicker noVisualizer />
        <ConnectButton
          size="lg"
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      </div>
    </div>
  );
};
