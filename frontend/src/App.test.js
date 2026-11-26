import { fireEvent, render, screen } from '@testing-library/react';
  import App from './App';
  import { consultarJob, criarJob } from './services/api';
  import { carregarLimiteUpload } from './services/config';

  jest.mock('./services/api', () => ({
    criarJob: jest.fn(),
    consultarJob: jest.fn(),
    mensagemDeErro: () => 'Sem resposta do servidor.',
    urlDownload: (id) => `/api/jobs/${id}/download`,
  }));

  jest.mock('./services/config', () => ({
    carregarLimiteUpload: jest.fn(),
  }));

  const JOB_PRONTO = {
    status: 'DONE',
    created_at: '2026-11-25T12:00:00Z',
    finished_at: '2026-11-25T12:00:02Z',
    expires_at: '2099-01-01T00:00:00Z',
    files_purged_at: null,
    download_url: '/jobs/abc/download',
  };

  function arquivo(nome, bytes = 10) {
    return new File([new Uint8Array(bytes)], nome);
  }

  function escolherArquivo(container, novo) {
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [novo] } });
  }

  beforeEach(() => {
    sessionStorage.clear();
    criarJob.mockReset();
    consultarJob.mockReset();
    carregarLimiteUpload.mockResolvedValue(null);
  });

  test('converte o arquivo do envio ao download', async () => {
    criarJob.mockResolvedValue({ id: 'abc' });
    consultarJob.mockResolvedValue(JOB_PRONTO);
    const { container } = render(<App />);

    escolherArquivo(container, arquivo('foto.png'));
    fireEvent.click(screen.getByRole('button', { name: /Converter para JPG/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Converter' }));

    expect(await screen.findByRole('link', { name: 'Baixar resultado' })).toBeInTheDocument();
    expect(criarJob).toHaveBeenCalledWith(
      expect.any(File),
      'image.thumbnail',
      expect.objectContaining({ format: 'jpeg' }),
      expect.any(Function)
    );
    expect(JSON.parse(sessionStorage.getItem('conversor:job')).jobId).toBe('abc');
  });

  test('outra conversão volta às opções com o mesmo arquivo', async () => {
    criarJob.mockResolvedValue({ id: 'abc' });
    consultarJob.mockResolvedValue(JOB_PRONTO);
    const { container } = render(<App />);

    escolherArquivo(container, arquivo('foto.png'));
    fireEvent.click(screen.getByRole('button', { name: /Converter para JPG/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Converter' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Outra conversão deste arquivo' }));

    expect(screen.getByText('foto.png')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Converter para JPG/ })).toHaveAttribute('aria-pressed', 'true');
    expect(sessionStorage.getItem('conversor:job')).toBeNull();
  });

  test('erro no envio permite ajustar e tentar de novo', async () => {
    criarJob.mockRejectedValue(new Error('rede'));
    const { container } = render(<App />);

    escolherArquivo(container, arquivo('foto.png'));
    fireEvent.click(screen.getByRole('button', { name: /Converter para JPG/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Converter' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Sem resposta do servidor.');
    fireEvent.click(screen.getByRole('button', { name: 'Ajustar e tentar de novo' }));
    expect(screen.getByRole('button', { name: 'Converter' })).toBeEnabled();
  });

  test('job salvo na sessão volta depois do F5', async () => {
    sessionStorage.setItem(
      'conversor:job',
      JSON.stringify({ jobId: 'abc', nomeArquivo: 'relatorio.docx', titulo: 'Converter para PDF' })
    );
    consultarJob.mockResolvedValue(JOB_PRONTO);
    render(<App />);

    expect(screen.getByRole('heading', { name: 'relatorio.docx' })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Baixar resultado' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Outra conversão deste arquivo' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Converter outro arquivo' }));

    expect(screen.getByRole('button', { name: /Arraste um arquivo aqui/ })).toBeInTheDocument();
    expect(sessionStorage.getItem('conversor:job')).toBeNull();
  });

  test('arquivo acima do limite publicado pelo servidor não mostra as opções', async () => {
    carregarLimiteUpload.mockResolvedValue(1024);
    const { container } = render(<App />);
    expect(await screen.findByText(/Até 1/)).toBeInTheDocument();

    escolherArquivo(container, arquivo('foto.png', 2048));

    expect(screen.getByRole('alert')).toHaveTextContent(/o limite é/);
    expect(screen.queryByRole('button', { name: 'Converter' })).not.toBeInTheDocument();
  });