import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { ThemeProvider } from '@pipecat-ai/voice-ui-kit';

import type { PipecatBaseChildProps } from '@pipecat-ai/voice-ui-kit';
import { ErrorCard, PipecatAppBase, SpinLoader } from '@pipecat-ai/voice-ui-kit';

import { Nav } from './components/Nav';
import { VoicePage } from './pages/VoicePage';
import { SchedulePage } from './pages/SchedulePage';
import { DEFAULT_TRANSPORT, TRANSPORT_PROPS } from './config';
import './index.css';

const VoiceRoute = () => {
  const transportProps = TRANSPORT_PROPS[DEFAULT_TRANSPORT];

  return (
    <PipecatAppBase {...transportProps} transportType={DEFAULT_TRANSPORT}>
      {({ client, handleConnect, handleDisconnect, error }: PipecatBaseChildProps) =>
        !client ? (
          <SpinLoader />
        ) : error ? (
          <ErrorCard>{error}</ErrorCard>
        ) : (
          <VoicePage client={client} handleConnect={handleConnect} handleDisconnect={handleDisconnect} />
        )
      }
    </PipecatAppBase>
  );
};

export const Main = () => (
  <ThemeProvider defaultTheme="system" disableStorage>
    <div className="w-full h-dvh bg-background flex flex-col">
      <BrowserRouter>
        <Nav />
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<VoiceRoute />} />
            <Route path="/schedule" element={<SchedulePage />} />
          </Routes>
        </main>
      </BrowserRouter>
    </div>
  </ThemeProvider>
);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Main />
  </StrictMode>
);
