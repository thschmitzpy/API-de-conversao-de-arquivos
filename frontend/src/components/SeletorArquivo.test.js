import { fireEvent, render, screen } from '@testing-library/react';
  import SeletorArquivo from './SeletorArquivo';

  const LIMITE = 100 * 1024 * 1024;

  function renderizar(props = {}) {
    const onSelecionar = jest.fn();
    const utils = render(
      <SeletorArquivo arquivo={null} limiteBytes={LIMITE} onSelecionar={onSelecionar} {...props} />
    );
    return { ...utils, onSelecionar };
  }

  test('soltar arquivos escolhe só o primeiro', () => {
    const { container, onSelecionar } = renderizar();
    const primeiro = new File(['a'], 'a.pdf');

    fireEvent.drop(container.querySelector('.seletor'), {
      dataTransfer: { files: [primeiro, new File(['b'], 'b.pdf')] },
    });

    expect(onSelecionar).toHaveBeenCalledTimes(1);
    expect(onSelecionar).toHaveBeenCalledWith(primeiro);
  });

  test('arrastar por cima destaca a área até o arquivo sair dela', () => {
    const { container } = renderizar();
    const area = container.querySelector('.seletor');

    fireEvent.dragOver(area);
    expect(area).toHaveClass('seletor--arrastando');

    fireEvent.dragLeave(area, { relatedTarget: null });
    expect(area).not.toHaveClass('seletor--arrastando');
  });

  test('clicar na área abre o explorador de arquivos', () => {
    const { container } = renderizar();
    const input = container.querySelector('input[type="file"]');
    const abrir = jest.spyOn(input, 'click');

    fireEvent.click(screen.getByRole('button', { name: /Arraste um arquivo aqui/ }));

    expect(abrir).toHaveBeenCalled();
  });

  test('o input é limpo para aceitar o mesmo arquivo de novo', () => {
    const { container, onSelecionar } = renderizar();
    const input = container.querySelector('input[type="file"]');
    const novo = new File(['a'], 'a.pdf');

    fireEvent.change(input, { target: { files: [novo] } });

    expect(onSelecionar).toHaveBeenCalledWith(novo);
    expect(input.value).toBe('');
  });

  test('com arquivo escolhido mostra nome, tamanho e o botão de trocar', () => {
    renderizar({ arquivo: new File([new Uint8Array(2048)], 'planilha.xlsx') });

    expect(screen.getByText('planilha.xlsx')).toBeInTheDocument();
    expect(screen.getByText('xlsx')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Trocar arquivo' })).toBeInTheDocument();
  });