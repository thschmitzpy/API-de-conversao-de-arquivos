import { fireEvent, render, screen } from '@testing-library/react';
import OpcoesConversao from './OpcoesConversao';
import { opcoesPara } from '../conversions';

function renderizar(props = {}) {
  const handlers = {
    onSelecionar: jest.fn(),
    onAlterarValor: jest.fn(),
    onConverter: jest.fn(),
  };
  render(
    <OpcoesConversao
      extensao="pdf"
      opcoes={opcoesPara('contrato.pdf')}
      selecionada={null}
      valores={{}}
      {...handlers}
      {...props}
    />
  );
  return handlers;
}

test('converter fica desabilitado sem opcao escolhida', () => {
  renderizar();
  expect(screen.getByRole('button', { name: 'Converter' })).toBeDisabled();
});

test("marca d'agua sem texto nao deixa converter", () => {
  const marca = opcoesPara('contrato.pdf').find((o) => o.operation === 'pdf.watermark');
  renderizar({ selecionada: marca, valores: { text: '  ' } });
  expect(screen.getByRole('button', { name: 'Converter' })).toBeDisabled();
});

test('clicar num card informa a opcao escolhida', () => {
  const { onSelecionar } = renderizar();
  fireEvent.click(screen.getByRole('radio', { name: /Extrair texto \(OCR\)/ }));
  expect(onSelecionar).toHaveBeenCalledWith(expect.objectContaining({ operation: 'ocr.extract' }));
});

test('opcao pronta dispara a conversao', () => {
  const texto = opcoesPara('contrato.pdf').find((o) => o.id === 'pdf-texto');
  const { onConverter } = renderizar({ selecionada: texto });
  fireEvent.click(screen.getByRole('button', { name: 'Converter' }));
  expect(onConverter).toHaveBeenCalledTimes(1);
});

test('extensao sem conversao mostra os formatos aceitos', () => {
  renderizar({ extensao: 'csv', opcoes: [] });
  expect(screen.getByText(/Ainda não convertemos arquivos \.csv/)).toBeInTheDocument();
});
