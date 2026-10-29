import { formatarBytes, formatarDuracao } from './formatar';

test.each([
  [512, '512 B'],
  [1536, '1,5 KB'],
  [100 * 1024 * 1024, '100 MB'],
])('formatarBytes(%i) -> %s', (bytes, esperado) => {
  expect(formatarBytes(bytes)).toBe(esperado);
});

test('formatarDuracao cobre subsegundo, segundos e minutos', () => {
  const inicio = '2026-10-29T12:00:00.000Z';
  expect(formatarDuracao(inicio, '2026-10-29T12:00:00.400Z')).toBe('menos de 1 s');
  expect(formatarDuracao(inicio, '2026-10-29T12:00:07.600Z')).toBe('8 s');
  expect(formatarDuracao(inicio, '2026-10-29T12:02:05.000Z')).toBe('2 min 5 s');
});

test('formatarDuracao devolve null para datas invalidas ou invertidas', () => {
  expect(formatarDuracao('lixo', '2026-10-29T12:00:00Z')).toBeNull();
  expect(formatarDuracao('2026-10-29T12:00:05Z', '2026-10-29T12:00:00Z')).toBeNull();
});
