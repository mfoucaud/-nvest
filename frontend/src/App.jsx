import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import OrderDetail from './pages/OrderDetail';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/orders/:id" element={<OrderDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
