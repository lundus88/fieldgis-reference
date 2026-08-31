import React from 'react';
import { createRoot } from 'react-dom/client';
function App(){return <main><h1>VL sandbox regression</h1><p>Build succeeded inside isolated sandbox.</p></main>}
createRoot(document.getElementById('root')).render(<App/>);
