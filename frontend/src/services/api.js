// Base URL du backend — VITE_API_URL en prod, localhost en dev
const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000') + '/api';

export const fetchOrders = async () => {
  const response = await fetch(`${BASE_URL}/orders/`);
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.json();
};

export const fetchOrderDetail = async (id) => {
  const response = await fetch(`${BASE_URL}/orders/${id}`);
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.json();
};

export const refreshOrders = async () => {
  const response = await fetch(`${BASE_URL}/orders/refresh`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.json();
};

export const fetchPriceHistory = async (ticker, days = 10) => {
  const response = await fetch(`${BASE_URL}/prices/${ticker}?days=${days}`);
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.json();
};
