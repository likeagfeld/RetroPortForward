import React, { useState } from 'react';


// Mock PyWebView API for development
if (process.env.NODE_ENV === 'development' && !window.pywebview) {
  window.pywebview = {
    api: {
      start_port_forward: async (config) => {
        console.log('MOCK: start_port_forward called with', config);
        // Simulate a successful response for testing
        return {
          success: true,
          ip: '192.168.1.100',
          ports: ['TCP 65432', 'UDP 20001', 'UDP 20002']
        };
      }
    }
  };
}

const testBackendConnection = async () => {
  try {
    console.log("Testing backend connection...");
    const response = await window.pywebview.api.echo("Testing connection");
    console.log("Backend response:", response);
    return true;
  } catch (error) {
    console.error("Backend connection test failed:", error);
    return false;
  }
};

const GameControllerIcon = () => (
  <svg 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className="w-12 h-12"
  >
    <rect x="2" y="6" width="20" height="12" rx="2"/>
    <path d="M6 12h4"/>
    <path d="M8 10v4"/>
    <circle cx="16" cy="12" r="1"/>
    <circle cx="18" cy="10" r="1"/>
  </svg>
);

const RouterIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="w-8 h-8"
  >
    <rect x="4" y="6" width="16" height="12" rx="2"/>
    <line x1="12" y1="2" x2="12" y2="6"/>
    <line x1="8" y1="10" x2="8" y2="10"/>
    <line x1="12" y1="10" x2="12" y2="10"/>
    <line x1="16" y1="10" x2="16" y2="10"/>
  </svg>
);

interface RouterConfig {
  console: string;
  targetDevice?: string;
  routerType: string;
  routerIP?: string;
  credentials: {
    username: string;
    password: string;
  };
}

interface SetupResponse {
  success: boolean;
  error?: string;
  ip?: string;
  ports?: string[];
}

declare global {
  interface Window {
    pywebview?: {
      api?: {
        start_port_forward?: (config: RouterConfig) => Promise<SetupResponse>;
      };
    };
  }
}

const PortForwardUI: React.FC = () => {
  const [step, setStep] = useState('console-select');
  const [selectedConsole, setSelectedConsole] = useState<string | null>(null);
  const [targetDevice, setTargetDevice] = useState<string | null>(null);
  const [routerType, setRouterType] = useState<string | null>(null);
  const [manualIP, setManualIP] = useState('');
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [setupStatus, setSetupStatus] = useState({ 
    state: 'pending', 
    message: '', 
    details: null as SetupResponse | null 
  });

  // Router types available
  const routerTypes = [
    'ASUS', 'TP-Link', 'Netgear', 'Linksys', 
    'D-Link', 'Cisco', 'Belkin', 'Buffalo', 
    'Huawei', 'Fios-G1100', 'Generic'
  ];
  const handleSetup = async () => {
  // Validate inputs
  if (!credentials.username || !credentials.password) {
    setSetupStatus({
      state: 'error',
      message: 'Please enter router username and password',
      details: null
    });
    return;
  }

  const config: RouterConfig = {
    console: selectedConsole || '',
    targetDevice,
    routerType: routerType || '',
    routerIP: manualIP || undefined,
    credentials
  };

  console.log('Starting setup with config:', JSON.stringify(config, null, 2));

  // First switch to setup progress step
  setStep('setup-progress');
  setSetupStatus({ 
    state: 'progress', 
    message: 'Configuring port forwarding...', 
    details: null 
  });

  try {
    const response = await window.pywebview.api.start_port_forward(config);
    console.log('Setup response:', JSON.stringify(response, null, 2));

    if (response && typeof response === 'object') {
      if (response.success) {
        setSetupStatus({
          state: 'success',
          message: 'Port forwarding configured successfully!',
          details: response
        });
      } else {
        setSetupStatus({
          state: 'error',
          message: response.error || 'Unknown error occurred',
          details: response
        });
      }
    } else {
      throw new Error('Invalid response from backend');
    }
  } catch (error) {
    console.error('Complete error object:', error);

    if (error.message.includes('Unsupported router type')) {
      setSetupStatus({
        state: 'error',
        message: `The router type "${config.routerType}" is not supported.`,
        details: { error: String(error) } as SetupResponse
      });
    } else {
      setSetupStatus({
        state: 'error',
        message: error instanceof Error 
          ? error.message 
          : 'An unexpected error occurred',
        details: { error: String(error) } as SetupResponse
      });
    }
  }
};

  
  
  const renderConsoleSelect = () => (
    <div className="space-y-6">
      <p className="text-gray-600 text-center">
        Select your console to begin setup
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => {
            setSelectedConsole('saturn');
            setStep('target-select');
          }}
          className="p-6 rounded-lg border-2 hover:border-blue-500 hover:bg-blue-50 transition-all"
        >
          <div className="text-gray-600">
            <GameControllerIcon />
          </div>
          <h3 className="text-lg font-semibold mt-2">Sega Saturn</h3>
          <p className="text-sm text-gray-500">Setup Saturn online gaming</p>
        </button>

        <button
          onClick={() => {
            setSelectedConsole('dreamcast');
            setStep('router-select');
          }}
          className="p-6 rounded-lg border-2 hover:border-blue-500 hover:bg-blue-50 transition-all"
        >
          <div className="text-gray-600">
            <GameControllerIcon />
          </div>
          <h3 className="text-lg font-semibold mt-2">Sega Dreamcast</h3>
          <p className="text-sm text-gray-500">Setup Dreamcast online gaming</p>
        </button>
      </div>
    </div>
  );

  const renderTargetSelect = () => (
    <div className="space-y-6">
      <p className="text-gray-600 text-center">
        Where would you like to forward the ports?
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => {
            setTargetDevice('dreampi');
            setStep('router-select');
          }}
          className="p-6 rounded-lg border-2 hover:border-blue-500 hover:bg-blue-50 transition-all"
        >
          <h3 className="text-lg font-semibold">DreamPi</h3>
          <p className="text-sm text-gray-500">Forward ports to a DreamPi device</p>
        </button>

        <button
          onClick={() => {
            setTargetDevice('pc');
            setStep('router-select');
          }}
          className="p-6 rounded-lg border-2 hover:border-blue-500 hover:bg-blue-50 transition-all"
        >
          <h3 className="text-lg font-semibold">This PC</h3>
          <p className="text-sm text-gray-500">Forward ports to this computer</p>
        </button>
      </div>
      <div className="flex justify-center">
        <button
          onClick={() => setStep('console-select')}
          className="px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          Back
        </button>
      </div>
    </div>
  );

  const renderRouterSelect = () => (
    <div className="space-y-6">
      <p className="text-gray-600 text-center mb-4">
        Select your router type
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {routerTypes.map((type) => (
          <button
            key={type}
            onClick={() => {
              setRouterType(type);
              setStep('router-login');
            }}
            className="p-4 rounded-lg border-2 hover:border-blue-500 hover:bg-blue-50 transition-all"
          >
            <div className="flex flex-col items-center">
              <RouterIcon />
              <span className="mt-2 text-sm font-medium">{type}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-6">
        <p className="text-sm text-gray-600 mb-2">Or enter router IP manually:</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={manualIP}
            onChange={(e) => setManualIP(e.target.value)}
            placeholder="192.168.1.1"
            className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => {
              if (manualIP.match(/^(\d{1,3}\.){3}\d{1,3}$/)) {
                setRouterType('manual');
                setStep('router-login');
              }
            }}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            Continue
          </button>
        </div>
      </div>

      <div className="flex justify-center">
        <button
          onClick={() => setStep(selectedConsole === 'saturn' ? 'target-select' : 'console-select')}
          className="px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          Back
        </button>
      </div>
    </div>
  );

  const handlePortForward = async (data) => {
  try {
    // Test connection first
    const isConnected = await testBackendConnection();
    if (!isConnected) {
      throw new Error("Backend connection test failed");
    }

    // Make the actual port forward call
    console.log("Sending data to backend:", data);
    const response = await window.pywebview.api.start_port_forward(data);
    console.log("Received response:", response);

    if (response.success) {
      // Handle success
      console.log("Port forwarding successful");
      return response;
    } else {
      // Handle error
      console.error("Port forwarding failed:", response.error);
      throw new Error(response.error);
    }
  } catch (error) {
    console.error("Error in port forwarding:", error);
    throw error;
  }
};

  const renderRouterLogin = () => (
    <div className="max-w-md mx-auto space-y-6">
      <p className="text-gray-600 text-center">
        Enter your router's admin credentials
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Username
          </label>
          <input
            type="text"
            value={credentials.username}
            onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="admin"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            type="password"
            value={credentials.password}
            onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter router password"
          />
        </div>

        <div className="flex justify-center space-x-4 pt-4">
          <button
            onClick={() => setStep('router-select')}
            className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Back
          </button>
          <button
            onClick={handleSetup}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            Configure Port Forwarding
          </button>
        </div>
      </div>
    </div>
  );

  const renderSetupProgress = () => (
    <div className="max-w-md mx-auto space-y-6 text-center">
      {(setupStatus.state === 'progress' || setupStatus.state === 'pending') && (
        <>
          <div className="animate-spin text-blue-500 mx-auto">
            <RouterIcon />
          </div>
          <p className="text-gray-600">{setupStatus.message}</p>
        </>
      )}

      {setupStatus.state === 'success' && (
        <>
          <div className="text-green-500 mx-auto">
            <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-xl font-semibold">{setupStatus.message}</p>
          {setupStatus.details && (
            <div className="bg-gray-50 p-4 rounded-lg text-left">
              <p className="text-sm text-gray-600">Configured IP: {setupStatus.details.ip}</p>
              <p className="text-sm text-gray-600">
                Ports: {setupStatus.details.ports?.join(', ')}
              </p>
            </div>
          )}
          <button
            onClick={() => window.close()}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            Close
          </button>
        </>
      )}

      {setupStatus.state === 'error' && (
        <>
          <div className="text-red-500 mx-auto">
            <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <p className="text-xl font-semibold text-red-600">Setup Failed</p>
          <p className="text-gray-600">{setupStatus.message}</p>
          <div className="space-y-3">
            <button
              onClick={() => setStep('router-login')}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 w-full"
            >
              Try Again
            </button>
            <button
              onClick={() => window.close()}
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 w-full"
            >
              Close
            </button>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-gray-800">
              Retro Console Port Forward Setup
            </h1>
            <div className="mt-2 text-sm text-gray-500">
              <div>Version 0.5</div>
              <div>Created by @LikeAGFeld</div>
            </div>
          </div>

          {step === 'console-select' && renderConsoleSelect()}
          {step === 'target-select' && renderTargetSelect()}
          {step === 'router-select' && renderRouterSelect()}
          {step === 'router-login' && renderRouterLogin()}
          {step === 'setup-progress' && renderSetupProgress()}
        </div>
      </div>
    </div>
  );
};

export default PortForwardUI;