import { carregarLimiteUpload } from './config';

function responder(corpo, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    json: () => (corpo instanceof Error ? Promise.reject(corpo) : Promise.resolve(corpo)),
  });
}

afterEach(() => {
  delete global.fetch;
});

test('converte o limite em MB para bytes', async () => {
  responder({ maxUploadMb: 20 });
  await expect(carregarLimiteUpload()).resolves.toBe(20 * 1024 * 1024);
});

test('ignora resposta que não é JSON (index.html do dev server)', async () => {
  responder(new SyntaxError('Unexpected token <'));
  await expect(carregarLimiteUpload()).resolves.toBeNull();
});

test('ignora valor inválido', async () => {
  responder({ maxUploadMb: 'cem' });
  await expect(carregarLimiteUpload()).resolves.toBeNull();
});

test('ignora resposta de erro', async () => {
  responder({}, false);
  await expect(carregarLimiteUpload()).resolves.toBeNull();
});

test('ignora falha de rede', async () => {
  global.fetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));
  await expect(carregarLimiteUpload()).resolves.toBeNull();
});
