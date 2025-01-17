import React from 'react';
import ReactDOM from 'react-dom/client';
import PortForwardUI from './components/port-forward-ui';
import './styles/globals.css';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <div className="min-h-screen bg-gray-100">
      <PortForwardUI />
    </div>
  </React.StrictMode>
);