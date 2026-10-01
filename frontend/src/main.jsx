import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import AccountGate from './AccountGate';
import './styles.css';
import './platform.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AccountGate />
  </StrictMode>,
);
