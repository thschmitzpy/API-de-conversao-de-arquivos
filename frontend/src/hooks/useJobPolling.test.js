import { act, renderHook } from '@testing-library/react';
import { consultarJob } from '../services/api';
import useJobPolling from './useJobPolling';

jest.mock('../services/api', () => ({
  consultarJob: jest.fn(),
  mensagemDeErro: () => 'erro da API',
}));

const MEIA_HORA_MS = 30 * 60 * 1000;

async function avancar(ms) {
  const fim = Date.now() + ms;
  while (Date.now() < fim) {
    await act(async () => {
      jest.advanceTimersByTime(1500);
    });
  }
}

beforeEach(() => {
  jest.useFakeTimers();
  consultarJob.mockReset();
});

afterEach(() => {
  jest.useRealTimers();
});

test('para de consultar quando o job termina', async () => {
  consultarJob
    .mockResolvedValueOnce({ status: 'PROCESSING' })
    .mockResolvedValue({ status: 'DONE' });

  const { result } = renderHook(() => useJobPolling('abc'));
  await avancar(10000);

  expect(result.current.job.status).toBe('DONE');
  expect(consultarJob).toHaveBeenCalledTimes(2);
});

test('continua consultando antes de atingir o limite', async () => {
  consultarJob.mockResolvedValue({ status: 'PENDING' });

  const { result } = renderHook(() => useJobPolling('abc'));
  await avancar(MEIA_HORA_MS - 10000);

  expect(result.current.erro).toBeNull();
});

test('desiste com erro claro quando o job nunca termina', async () => {
  consultarJob.mockResolvedValue({ status: 'PROCESSING' });

  const { result } = renderHook(() => useJobPolling('abc'));
  await avancar(MEIA_HORA_MS + 2000);
  const chamadas = consultarJob.mock.calls.length;
  await avancar(10000);

  expect(result.current.erro).toMatch(/demorando mais que o esperado/);
  expect(consultarJob).toHaveBeenCalledTimes(chamadas);
});

test('consultarDeNovo retoma a consulta depois de um erro', async () => {
  consultarJob
      .mockRejectedValueOnce({response: {status: 404}})
      .mockResolvedValue({status: 'DONE'});

  const {result} = renderHook(() => useJobPolling('abc'));
  await avancar(3000);
  expect(result.current.erro).toBe('erro da API');

  await act(async () => {
    result.current.consultarDeNovo();
  });
  await avancar(3000);

  expect(result.current.erro).toBeNull();
  expect(result.current.job.status).toBe('DONE');
  expect(consultarJob).toHaveBeenCalledTimes(2);
});
