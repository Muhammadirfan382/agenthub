import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { applyTheme, useUiStore } from './stores/uiStore';
import './styles/index.css';

// Apply the saved theme before the first render to avoid a flash of the wrong theme.
applyTheme(useUiStore.getState().theme);

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('AgentHub could not start: the #root element is missing from index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
